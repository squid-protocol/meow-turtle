# lib/logic_engine.py - Ninelives Core 0 (v6.1 Architectural Migration)
# ROLE: The Frontal Lobe. Intelligence, part-tracking, and vision-to-hardware fusion.
# COMPLIANCE: Spec 4.2 (Pulse Sync), 11.3 (Kinetic Pipeline), 4.3.6.3 (W-Protocol Verification)
# VERSION: v6.1.0 - Enhanced W-Protocol Verification and Robust Telemetry Parsing.

"""
[Spec 6.0] Ninelives Logic Engine (The Frontal Lobe).

The LogicEngine is responsible for high-level decision making and the 
synchronization of asynchronous data streams. It bridges the gap between 
physical hardware events (breakbeams) and high-latency computer vision results.

Key Architectural Roles:
1. Vision Fusion (Spec 11.3): Matches asynchronous AI results to specific parts in the FIFO.
2. W-Protocol Verifier (Spec 4.3.6.3): Inspects telemetry to confirm that Picos have cleared persistent error memory.
3. Pulse Synchronization (Spec 4.2): Uses the Global Odometer to assign 'Spatial Birth Certificates' to parts.
4. Kinetic Pipeline: Translates vision classifications into position-fused sort commands.
"""

import asyncio
import time
import collections
import zmq
import zmq.asyncio
from lib.rp5_logger import logger
from lib.digital_twin import GLOBAL_TWIN
from lib import meowprotocol
from lib import machine_states as ms

class LogicEngine:
    """
    [Spec 6.0] The Frontal Lobe.
    
    Handles high-speed event processing and synchronization between physical 
    breakbeam events and asynchronous vision results. It serves as the primary 
    verifier for reliable transport acknowledgments.
    """

    def __init__(self, coordinator):
        """
        Initializes the Logic Engine and its internal memory structures.
        
        :param coordinator: Reference to the SystemCoordinator (The Hub).
        """
        self.coord = coordinator
        self.running = True
        
        # [Spec 4.2 & 11.3] The Reconciliation Engine Queues
        self.part_located = collections.deque(maxlen=100)     # Physical parts detected by Pico 2
        self.part_identified = collections.deque(maxlen=100)  # AI classifications from Core 1
        self.pending_sort = collections.deque(maxlen=100)     # Married data awaiting execution
    
        self.zmq_context = zmq.asyncio.Context()
        self.vision_socket = self.zmq_context.socket(zmq.SUB)
        self.vision_socket.connect("tcp://127.0.0.1:5555") # Core 1 will publish to this port
        self.vision_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # [Spec 4.3.6.3] W-Protocol Tracking Registry
        # Tracks persistent IDs that have been sighted in the re-broadcast stream.
        # Format: {pid: {seq_id1, seq_id2, ...}}
        self.sighted_ids = {pid: set() for pid in coordinator.config_ports}
        
        # Performance and Audit Statistics
        self.stats = {
            "parts_detected": 0,
            "parts_sorted": 0,
            "vision_sync_errors": 0,
            "wipes_confirmed": 0
        }

        logger.info("[Logic] LogicEngine Initialized with W-Verification Logic.")

    # --------------------------------------------------------------------------
    # INDESTRUCTIBLE LOOPS
    # --------------------------------------------------------------------------
    async def run_loop(self):
        """
        [Spec 10.1] Main Event Processing Loop.
        
        Consumes hardware events from the fleet and vision results from Core 1.
        Uses non-blocking queue polling to maintain a high processing frequency
        without saturating the CPU.
        """
        logger.info("[Logic] Event Processor Loop Active.")
        while self.running:
            try:
                # 1. Consume Hardware Events (Telemetry, Alarms, Breakbeams)
                if not self.coord.logic_queue.empty():
                    evt = await self.coord.logic_queue.get()
                    await self.handle_hardware_event(evt)
                
                # 2. Consume Vision Results via Synapse Bus (ZeroMQ IPC)
                try:
                    # Non-blocking check for incoming AI vision data
                    vision_msg = await self.vision_socket.recv_json(flags=zmq.NOBLOCK)
                    await self.handle_vision_result(vision_msg)
                except zmq.Again:
                    pass # No vision data waiting this millisecond

                # High-frequency resolution (200Hz) to prevent FIFO pileups
                await asyncio.sleep(0.005) 
                
            except Exception as e:
                logger.critical(f"[Logic] Loop Crash: {e}")
                await asyncio.sleep(1.0)

    # --------------------------------------------------------------------------
    # EVENT HANDLING & W-PROTOCOL VERIFICATION
    # --------------------------------------------------------------------------
    async def handle_hardware_event(self, evt):
        """
        Parses raw payloads from Picos and translates them into logical actions.
        
        Fulfills the 'Verification of Success' requirement (Spec 4.3.6.3.B) by 
        monitoring incoming status reports to confirm that persistent events 
        have been successfully wiped from hardware memory.
        """
        payload = evt.get('payload', "")
        source_id = evt.get('source', 0)
        msg_type = evt.get('mtype', 0)
        seq = evt.get('seq', 0)
        
        # --- PHASE 1: W-PROTOCOL SIGHTING ---
        # Every Event (0x40) or Alarm (0x48) is treated as a persistent re-broadcast.
        # We notify the Hub to start the piggyback wipe injection.
        if msg_type in [meowprotocol.MSG_TYPE_EVT, meowprotocol.MSG_TYPE_ALARM]:
            # Register in the Hub's global registry for Switchboard injection
            self.coord.register_receipt(source_id, seq)
            # Add to local 'judge' list for verification via Status Reports
            self.sighted_ids[source_id].add(seq)

        # --- PHASE 2: WIPE VERIFICATION (Spec 4.3.6.3.B) ---
        # When a Status Report (0x41) arrives, we check if our sighted IDs are 
        # still in the Pico's 'Un-Acknowledged' (UA) list.
        if msg_type == meowprotocol.MSG_TYPE_STS:
            await self._verify_wipe_success(source_id, payload)

        # --- PHASE 3: KINETIC LOGIC PERCOLATION ---
        if "PART_DETECTED" in payload:
            await self._process_part_detected(payload)
            
        elif "HOPPER_EMPTY" in payload:
            self.coord._notify("Loader Hopper is Empty! Add more bricks.", type='warning')
            
        elif "GATE_JAMMED" in payload:
            logger.error("[Logic] Gatekeeper Jammed! Initiating clearing routine.")
            await self.coord.send_manual_command(1, "feeder", -0.5)
            
        elif "SORT_ACK" in payload:
            self.stats["parts_sorted"] += 1
            
        elif "STALL" in payload:
            logger.warning(f"[Logic] Hardware Stall on Pico {source_id}: {payload}")

    async def _verify_wipe_success(self, pid, payload):
        """
        [Spec 4.3.6.3] Verification of Success.
        
        Parses the 'UA' (Un-Acknowledged) list from hardware telemetry. If a 
        previously sighted ID is missing from the list, the LogicEngine confirms 
        that the Pico has successfully received the wipe command and processed it.
        """
        un_acked = set()
        if "UA=" in payload:
            try:
                # Robust extraction: find segment between 'UA=' and the next key or end
                ua_part = payload.split("UA=")[1]
                ua_tokens = []
                for token in ua_part.split(","):
                    token = token.strip()
                    if "=" in token: # Reached next key (e.g., ,V=24.0)
                        break
                    if token.isdigit():
                        ua_tokens.append(int(token))
                un_acked = set(ua_tokens)
            except Exception as e:
                logger.error(f"[Logic] UA Parsing Error: {e}")

        # ID Tracking Logic: 
        # If a SeqID was sighted but is no longer in the Pico's UA list, it's wiped!
        confirmed = []
        for seq in list(self.sighted_ids[pid]):
            if seq not in un_acked:
                confirmed.append(seq)
                self.sighted_ids[pid].remove(seq)

        if confirmed:
            # Tell the Hub to stop the piggyback injection for these IDs
            self.coord._clear_confirmed_wipes(pid, confirmed)
            self.stats["wipes_confirmed"] += len(confirmed)
            logger.debug(f"[Logic] W-Verification Success: P{pid} cleared IDs {confirmed}")

    async def _process_part_detected(self, payload):
        """
        [Spec 4.2] Odometer Synchronization.
        
        Extracts the Global Pulse Count from a PART_DETECTED event and triggers 
        the Vision Process. Assigns the 'Birth Certificate' to the part by 
        storing its pulse count in the FIFO.
        """
        try:
            # [FIX] Use the hardened central parser instead of fragile string splitting
            from lib import protocol_parser
            parsed_data = protocol_parser.parse_kv_payload(payload)
            pulse_count = int(parsed_data.get('pulse_count', 0))
        except Exception as e:
            logger.error(f"[Logic] Malformed PART_DETECTED payload: {e}")
            return

        self.stats["parts_detected"] += 1

        # 1. Store in Reconciliation Queue
        self.part_located.append({
            "pulse": pulse_count,
            "ts": time.time()
        })
        
        # 2. Trigger UI Flash via Digital Twin (Pico 2 is the Gatekeeper)
        if 2 in GLOBAL_TWIN.limbs:
            GLOBAL_TWIN.limbs[2].ui_flash_trigger = True
            
        # 3. Attempt Reconciliation (In case Vision beat Physics to the punch)
        await self.reconcile_queues()

    # --------------------------------------------------------------------------
    # VISION FUSION & KINETIC DISPATCH
    # --------------------------------------------------------------------------
    async def handle_vision_result(self, result):
        """
        [Spec 11.3] Vision result ingestion from Synapse Bus.
        """
        self.part_identified.append(result)
        await self.reconcile_queues()

    async def reconcile_queues(self):
        """
        The Marriage Process. Matches the oldest physical location with the 
        oldest vision ID, and dispatches the compiled command to Pico 3.
        """
        # We need AT LEAST ONE physical location and ONE vision ID to make a match
        if len(self.part_located) > 0 and len(self.part_identified) > 0:
            
            # The newest physical location gets the oldest vision ID
            physical_data = self.part_located.popleft() 
            vision_data = self.part_identified.popleft()
            
            target_bin = vision_data.get('target_bin', 10)
            impulse = vision_data.get('impulse', 1.0)
            start_pulse = physical_data["pulse"]
            
            # [Spec 16.3] Position-Fused Sort Command
            payload = f"ACT:SORT:bin={target_bin}:at={start_pulse}:str={impulse}"
            
            if GLOBAL_TWIN.host_state == ms.STATE_FLOW:
                await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, payload)
                self.stats["parts_sorted"] += 1
                logger.info(f"[Logic] Synapse Match: Bin {target_bin} for part at Pulse {start_pulse}")

    def reset_logic(self):
        """
        [Spec 15.3] Clears memory and tracking state to recover from system errors.
        """
        self.part_located.clear()
        self.part_identified.clear()
        self.pending_sort.clear()
        for pid in self.sighted_ids:
            self.sighted_ids[pid].clear()
        logger.info("[Logic] Logic Engine state purged.")