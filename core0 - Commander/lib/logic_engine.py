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
        
        # [Spec 4.2] Part Tracking Memory
        # Stores {timestamp, pulse_count} from Gatekeeper to match with Vision Results.
        # This FIFO ensures that parts are sorted in the exact order they were seen.
        self.part_fifo = collections.deque(maxlen=100)
        
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
                
                # 2. Consume Vision Results (AI Classification)
                if not self.coord.from_brain.empty():
                    vision_result = self.coord.from_brain.get()
                    await self.handle_vision_result(vision_result)

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
        pulse_count = 0
        try:
            # Parse the odometer reading from the Gatekeeper (Pico 2)
            if "pulse_count=" in payload:
                parts = payload.split("pulse_count=")
                pulse_count = int(parts[1].split(',')[0])
        except Exception as e:
            logger.error(f"[Logic] Malformed PART_DETECTED payload: {e}")
            return

        self.stats["parts_detected"] += 1

        # 1. Inform the Vision Core to analyze the latest image
        self.coord.to_brain.put({
            "type": "ANALYZE_PART", 
            "req_id": time.time(),
            "pulse_count": pulse_count
        })
        
        # 2. Store in FIFO to await the asynchronous vision result
        self.part_fifo.append({
            "ts": time.time(),
            "pulse_count": pulse_count
        })

    # --------------------------------------------------------------------------
    # VISION FUSION & KINETIC DISPATCH
    # --------------------------------------------------------------------------
    async def handle_vision_result(self, result):
        """
        [Spec 11.3] Vision result matching and kinetic routing.
        
        Matches a classification result from Core 1 with the oldest part in 
        the FIFO. Calculates a position-fused sort command based on the 
        part's original capture pulse.
        """
        if not self.part_fifo:
            logger.warning("[Logic] Vision result orphaned: Part FIFO empty (Sync Lost).")
            self.stats["vision_sync_errors"] += 1
            return

        # Pop the oldest part pulse count to match the oldest AI result
        part_data = self.part_fifo.popleft()
        start_pulse = part_data.get('pulse_count', 0)
        
        # Extract classification from the Vision Brain
        target_bin = result.get('target_bin', 10) # 10 is the fallback Reject bin
        impulse = result.get('impulse', 1.0)
        
        # [Spec 16.3] Position-Fused Sort Command
        # Dispatched to Pico 3 (Distributor). Uses the 'at=' spatial target.
        payload = f"ACT:SORT:bin={target_bin}:at={start_pulse}:str={impulse}"
        
        if GLOBAL_TWIN.host_state == ms.STATE_FLOW:
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, payload)
            self.stats["parts_sorted"] += 1
            logger.info(f"[Logic] Sort Executed: Bin {target_bin} for part at Pulse {start_pulse}")

    def reset_logic(self):
        """
        [Spec 15.3] Clears memory and tracking state to recover from system errors.
        Ensures a clean slate for the FIFO and W-Protocol registries after a reset.
        """
        self.part_fifo.clear()
        for pid in self.sighted_ids:
            self.sighted_ids[pid].clear()
        logger.info("[Logic] Logic Engine state purged.")