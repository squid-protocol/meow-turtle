# lib/coordinator.py - Ninelives Core 0 (v6.9.7 Industrial Hub)
# ROLE: The Hub / Orchestrator. Central routing, math, and domain lifecycle.
# COMPLIANCE: Spec 15 (Safety Hierarchy), Spec 18.2 (Dual-Interlock Arming)
# VERSION: v6.9.7 - Phase 2: Calibration Intent Integration.

"""
[Spec 5.0] The System Coordinator (The Hub).

The Coordinator serves as the central brain of the Core 0 environment. It is 
responsible for the orchestration of specialized domains (Safety, Logic, Jobs, 
and Alarms) and manages the lifecycle of the distributed hardware fleet.

Key Architectural Roles:
1. Command Routing (Spec 15): Manages the flow of intents from the HMI to limbs.
2. Safety Interlock (Spec 18.2): Enforces dual-interlock arming requirements.
3. Health Driver (Spec 21.0): Actively polls Host OS metrics to update the Twin.
4. Transport Accountability (Spec 20): Performs RTT math and LQI aggregation.
5. Self-Healing (Spec 4.3.11): Implements the command deduplication registry.
6. Dynamic Fleet (Rectification 3.B): Populates the Digital Twin based on active ports.

Design Note: Following the 'Passive Mirror' and 'Dynamic Registry' rectifications, 
this module now handles both host-level measurements and the instantiation of 
the digital fleet models in the Twin.
"""

import asyncio
import time
import multiprocessing as mp
import collections
import logging
import os
import re
import json
import psutil # [Spec 21.0] Required for active Host Health monitoring

from lib.rp5_logger import logger, scan_local_versions
from lib.digital_twin import GLOBAL_TWIN
from lib.switchboard import operator
from lib.telemetry_router import STREAM_ROUTER
from lib import meowprotocol
from lib import machine_states as ms

# Domain Logic Imports (Specialized Orchestration)
from lib.safety_tasks import SafetyManager
from lib.logic_engine import LogicEngine
from lib.job_manager import JobManager
from lib.alarm_manager import AlarmManager 

class SystemCoordinator:
    """
    The Hub. Maintains the lifecycle of all specialized domains.
    
    Responsibilities:
    - Route commands from GUI to Hardware/Logic.
    - Enforce Safety Hierarchy (Reflexes vs. Monitoring).
    - Maintain the central W-Protocol Wipe Registry.
    - [Spec 4.3.11] Self-Healing Command Deduplication.
    - [Spec 21.0] Active Host Health Measurement.
    - [Rectification 3.B] Dynamic Limb Registration.
    """

    def __init__(self, config_ports):
        """
        Initializes the central orchestrator and populates the Digital Twin.

        Args:
            config_ports (dict): Mapping of Port IDs to device paths.
        """
        # 1. PRIMARY COMMUNICATION PIPES
        # Internal queues for cross-domain signaling
        self.logic_queue = asyncio.Queue()            
        self.warning_queue = asyncio.Queue()          
        self.ui_notification_queue = asyncio.Queue()     
        
        # 2. Inter-Core Pipelines (Multiprocessing Brain Link)
        # Queues for future vision/inference core synchronization
        self.to_brain = mp.Queue()                    
        self.from_brain = mp.Queue()                  
        
        # 3. STATE & INFRASTRUCTURE REGISTRY
        self.running = True
        self.config_ports = config_ports
        self.fleet = None                             
        
        # [Rectification 3.B] Dynamic Limb Registration
        # This resolves the Static Hardcoding in digital_twin.py.
        # We populate the Passive Mirror based on the provided serial config.
        for pid in self.config_ports:
            # Traditional role mapping for standard industrial setups
            role_map = {1: "LOADER", 2: "GATEKEEPER", 3: "DISTRIBUTOR"}
            name = role_map.get(pid, f"LIMB_{pid}")
            GLOBAL_TWIN.register_limb(pid, name)
            logger.info(f"[Hub] Registered Dynamic Limb: {name} on Port {pid}")
        
        # [Spec 4.3.11] Self-Healing Command Registry
        # Stores the last commanded state to ensure persistence across link drops.
        self.cmd_dedupe_cache = {}                
        self.REFRESH_INTERVAL = 60.0 # Transmit interval for cached states
        
        # [Spec 4.3.6.3] W-Protocol Wipe Registry
        # Tracks pending flash wipes on downstream hardware.
        self.pending_wipes = {pid: set() for pid in config_ports}
        
        # [Spec 20] Network Health tracking
        # Stores transmit timestamps for RTT (Round Trip Time) calculations.
        self.rtt_pending = {pid: {} for pid in config_ports}
        
        # 4. DOMAIN ORCHESTRATORS (Specialized Managers)
        # Spec 18.1: AlarmManager tracks environmental/evaluative health.
        self.alarms = AlarmManager(GLOBAL_TWIN)
        # Spec 15.1: SafetyManager tracks hardware reflexes and hard stops.
        self.safety = SafetyManager(self)             
        self.logic = LogicEngine(self)               
        self.jobs = JobManager(self)                 

        # Watchdog registry for hardware log retrieval
        self.pending_log_requests = {}                

        logger.info("[Hub] Coordinator v6.9.7 Online. Safety Hierarchy established.")

    # --------------------------------------------------------------------------
    # 3.2 LIFECYCLE MANAGEMENT & BOOTSTRAP
    # --------------------------------------------------------------------------
    async def start(self):
        """
        Orchestrates the formal bootstrap sequence (Spec 7.2).
        
        Initiates fleet communication, performs hardware discovery handshakes, 
        synchronizes clocks, and launches all background domain tasks.
        """
        logger.info("[Hub] Starting System Bootstrap...")

        try:
            # Step 1: Initialize Fleet Comms
            # Switchboard (operator) handles the raw serial transport layer.
            self.fleet = operator(self.config_ports, self.logic_queue, self.warning_queue, self)
            await self.fleet.start()
            
            # Step 2: Discovery Handshake
            # Request version and actuator manifests from every configured port.
            for pid in self.config_ports:
                await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_VER, "")
                await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_ACT, "")
                
            # Step 3: Boot Interlock
            # Wait for all limbs to reach a minimum viable state (IDLE or BOOT).
            retries = 0
            while retries < 20: 
                ready = True
                for pid in self.config_ports:
                    state = GLOBAL_TWIN.limbs[pid].remote_state
                    if state not in [ms.STATE_IDLE, ms.STATE_BOOT]:
                        ready = False
                if ready: break
                await asyncio.sleep(0.5)
                retries += 1
            
            if not ready:
                logger.warning("[Hub] Bootstrap: Some limbs failed to report ready state.")
                
            # Step 4: Diagnostic Audit & Time Sync
            # Sync local version database and push current epoch to hardware.
            scan_local_versions()
            await self._broadcast_time_sync()

            # Step 5: Launch Specialized Domain Tasks
            # Monitoring tasks (Host, Log requests, Network, Deduplication)
            asyncio.create_task(self.host_health_monitor())
            asyncio.create_task(self.log_request_watchdog())
            asyncio.create_task(self.network_health_aggregator())
            asyncio.create_task(self.dedupe_cache_refresher())      
            
            # High-Frequency Domain Loops
            asyncio.create_task(self.logic.run_loop())
            asyncio.create_task(self.safety.monitor_loop())
            asyncio.create_task(self.safety.watchdog_task())
            asyncio.create_task(self.alarm_check_loop()) # Evaluative Health (1Hz)
            
            GLOBAL_TWIN.set_state(ms.STATE_IDLE)
            logger.info("[Hub] Bootstrap Complete. Global State: IDLE")

        except Exception as e:
            logger.critical(f"[Hub] Bootstrap Failed: {e}")
            GLOBAL_TWIN.set_state(ms.STATE_ERROR)

    async def alarm_check_loop(self):
        """
        [Spec 18.1] Periodic health check and alarm evaluation loop.
        
        Monitors the Passive Twin for environmental or evaluative health issues
        and triggers Tier 2 state transitions (IDLE/PAUSE) if safety thresholds
        are exceeded.
        """
        while self.running:
            try:
                # AlarmManager reads the Passive Twin, decides if we are safe.
                # It handles Tier 2 (Pause/IDLE) transitions.
                self.alarms.check_health()
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Hub] Alarm Loop Error: {e}")
                await asyncio.sleep(1.0)

    # --------------------------------------------------------------------------
    # COMMAND ROUTING & INTERLOCKS
    # --------------------------------------------------------------------------
    async def send_cmd(self, command_name):
        """
        Routes GUI Intents while enforcing the Dual-Interlock Safety Hierarchy.

        Validates current system health via SafetyManager (Reflexes) and 
        AlarmManager (Environmental) before allowing state transitions.

        Args:
            command_name (str): The identifier of the action requested.
        """
        logger.info(f"[Hub] Routing GUI Intent: {command_name}")
        
        if command_name == "STOP":
            # Priority Safety Halt: Force ERROR state and broadcast hard stops.
            GLOBAL_TWIN.set_state(ms.STATE_ERROR) 
            await self.broadcast_stop()

        elif command_name == "START":
            # Clear dedupe cache to ensure fresh starts reach hardware.
            self.cmd_dedupe_cache.clear() 
            
            # --- DUAL INTERLOCK CHECK (Spec 18.2) ---
            # 1. Check SafetyManager for Hardware Reflex issues (Stalls/Ghosts)
            safety_ok = self.safety.is_safe_to_arm()
            
            # 2. Check AlarmManager for Environmental issues (Overheat/UnderVolt)
            alarm_ok, alarm_msg = self.alarms.check_arming_safety()
            
            if safety_ok and alarm_ok:
                logger.info("[Hub] Safety Interlocks Clear. Transitioning to ARMING.")
                # Run the specific Arming Sequence via JobManager
                await self.jobs.run_arming_sequence(ms.PROFILE_SCAN)
            else:
                reason = "Hardware Fault" if not safety_ok else alarm_msg
                logger.warning(f"[Hub] START BLOCKED: {reason}")
                self._notify(f"START BLOCKED: {reason}", type='negative')

        elif command_name == "RESET":
            self.cmd_dedupe_cache.clear()
            await self.broadcast_reset()

        elif command_name == "IDLE":
            # Graceful transition to standby via JobManager
            await self.jobs.enter_idle_sequence()

        elif command_name == "FETCH_LOGS":
            # [Spec 9.3] Manual log retrieval.
            self._notify("Polling fleet crash logs...", type='info')
            for pid in self.config_ports:
                self.pending_log_requests[pid] = time.time()
                await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_LOG, "")

        elif command_name == "FETCH_CONFIG":
            # Synchronize remote flash config with Digital Twin Limb meta-data.
            for pid in self.config_ports:
                await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_CFG, "")

        elif command_name == "FETCH_VERSIONS":
            # [Migrated from GUI] Fleet-wide Version Audit
            await self.fetch_fleet_versions()

        elif command_name == "START_CALIBRATION":
            # [PHASE 2] Route high-precision calibration intent to JobManager.
            self._notify("Initiating Calibration Wizard...", type='info')
            await self.jobs.run_calibration_sequence()

        elif command_name == "DEV_TOGGLE":
            # [Spec 10.3] Manual override mode for maintenance.
            if GLOBAL_TWIN.host_state == ms.STATE_IDLE:
                GLOBAL_TWIN.set_state(ms.STATE_DEV)
                self._notify("DEV MODE ACTIVE", type='warning')
            elif GLOBAL_TWIN.host_state == ms.STATE_DEV:
                GLOBAL_TWIN.set_state(ms.STATE_IDLE)
                self._notify("System Secured (IDLE).")

        elif command_name.startswith("RESET_P"):
            # Target specific reset for a single limb port.
            try:
                pid = int(command_name.replace("RESET_P", ""))
                await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_RST, "")
            except Exception as e:
                logger.error(f"[Hub] Manual Reset Failed for P{pid}: {e}")

    async def fetch_fleet_versions(self):
        """
        [Spec 9.3] Triggers a fleet-wide 'Version Manifest' audit.
        Moved from GUI to Hub for role separation and Digital Twin consistency.
        """
        self._notify("Requesting Fleet Versions...", type='info')
        # Synchronize local database of known versions before auditing
        scan_local_versions()
        for pid in self.config_ports.keys():
            await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_VER, "")

    async def broadcast_reset(self):
        """
        Executes a synchronized system-wide reset.
        
        Clears active alarms, triggers safety recovery grace periods, and 
        signals all downstream limbs to perform hardware-level resets.
        """
        logger.info("[Hub] Executing System-Wide Reset...")
        GLOBAL_TWIN.set_state(ms.STATE_BOOT)
        self.cmd_dedupe_cache.clear() 
        
        # Clear evaluative alarms and active hard-stop logic
        self.alarms.active_alarms.clear()
        self.alarms.acknowledged_alarms.clear()
        
        # Trigger Safety Grace (Inhibits immediate ERROR loops for 10s)
        self.safety.trigger_recovery_grace()
        
        for pid in self.config_ports:
            await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_RST, "")

    async def broadcast_stop(self):
        """
        Priority Hard Stop.
        
        Bypasses normal command queues to immediately broadcast 0x00 STOP 
        signals to all limbs, forcing them into safe hardware states.
        """
        self.cmd_dedupe_cache.clear()
        for pid in self.config_ports:
            # Bypass regular queues to ensure 0x00 STOP is prioritized
            await self.send_physical(pid, meowprotocol.MSG_TYPE_CMD_STOP, "")
        logger.critical("[Hub] PRIORITY BROADCAST STOP EXECUTED.")

    # --------------------------------------------------------------------------
    # NETWORK HEALTH & ACCOUNTABILITY
    # --------------------------------------------------------------------------
    def record_ack(self, pid, seq):
        """
        [Spec 20.1] Centralized RTT calculation.
        
        Computes Round-Trip Time for a specific packet sequence and updates 
        exponentially weighted moving average (EWMA) in the Digital Twin.

        Args:
            pid (int): The limb ID that acknowledged the packet.
            seq (int): The sequence ID of the acknowledged packet.
        """
        if pid in self.rtt_pending and seq in self.rtt_pending[pid]:
            start_time = self.rtt_pending[pid].pop(seq)
            rtt = (time.time() - start_time) * 1000.0
            
            limb = GLOBAL_TWIN.limbs.get(pid)
            if limb:
                alpha = 0.2
                limb.host_rtt_avg = (alpha * rtt) + (1 - alpha) * limb.host_rtt_avg
                limb.host_rtt_max = max(limb.host_rtt_max, rtt)
                limb.last_acked_seq = seq
                limb.packet_count += 1

    async def network_health_aggregator(self):
        """
        [Spec 20.2] Centralized LQI scoring based on transport counters.
        
        Evaluates Link Quality Indicators by analyzing packet loss, sequence 
        skips, and RTT volatility across all active limb connections.
        """
        while self.running:
            try:
                for pid, limb in GLOBAL_TWIN.limbs.items():
                    total = limb.packet_count
                    skips = limb.host_seq_skips
                    prior = 200 
                    # LQI = 100 - Penalty for skips relative to volume
                    lqi = 100.0 - (skips / (total + prior) * 1000.0)
                    limb.lqi = max(0.0, min(100.0, lqi)) 
                
                # Prune RTT pending dict for stale packets (>5s)
                now = time.time()
                for pid in self.rtt_pending:
                    self.rtt_pending[pid] = {s: t for s, t in self.rtt_pending[pid].items() if now - t < 5.0}
                    
                # Fix: Synchronized frequency (2Hz) to support 1Hz Evaluator loop
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Hub] LQI Aggregator Error: {e}")
                await asyncio.sleep(1.0)

    # --------------------------------------------------------------------------
    # INTERNAL UTILITIES
    # --------------------------------------------------------------------------
    def register_receipt(self, pid, seq):
        """Registers a packet sequence ID for the W-Protocol Wipe Registry."""
        if pid in self.pending_wipes:
            self.pending_wipes[pid].add(seq)

    def _clear_confirmed_wipes(self, pid, confirmed_seqs):
        """Clears confirmed packet sequence IDs from the Wipe Registry."""
        if pid in self.pending_wipes:
            for seq in confirmed_seqs:
                if seq in self.pending_wipes[pid]:
                    self.pending_wipes[pid].remove(seq)

    async def send_physical(self, pid, msg_type, payload):
        """
        Dispatches binary packets to the physical hardware transport layer.
        
        Implements an ERROR-state interlock to prevent sending non-critical 
        commands to limbs currently in a fault state.

        Args:
            pid (int): Destination limb identifier.
            msg_type (int): MTIP protocol message type.
            payload (str|bytes): Raw data to be transmitted.

        Returns:
            int|None: The assigned sequence ID of the dispatched packet.
        """
        if not self.fleet: 
            return None
            
        limb = GLOBAL_TWIN.limbs.get(pid)
        # Interlock: Don't send operational commands to limbs in ERROR state
        if limb and limb.remote_state == ms.STATE_ERROR:
            # Exceptions for Reset and Stop commands which are required for recovery.
            if msg_type not in [meowprotocol.MSG_TYPE_CMD_RST, meowprotocol.MSG_TYPE_CMD_STOP]:
                return None
                
        seq_id = await self.fleet.send(pid, msg_type, payload)
        
        # Track RTT for critical command types
        if seq_id is not None and msg_type in [meowprotocol.MSG_TYPE_CMD, meowprotocol.MSG_TYPE_SET_CFG, meowprotocol.MSG_TYPE_CMD_RST]:
            self.rtt_pending[pid][seq_id] = time.time()
            
        return seq_id

    def send_manual_command(self, pid, act_name, val):
        """
        Routes manual hardware overrides with built-in Thermal Pulse safety.
        
        Only permitted when the system is in DEV mode. Automatically converts 
        solenoid high signals into short thermal pulses to prevent hardware burnout.

        Args:
            pid (int): Target limb ID.
            act_name (str): Actuator identifier.
            val (str|float): Targeted state or intensity.
        """
        if GLOBAL_TWIN.host_state != ms.STATE_DEV:
            self._notify("Manual Controls Locked. Enter DEV Mode.", type='warning')
            return
            
        norm_name = self._normalize_actuator_name(pid, act_name)
        if not norm_name:
            self._notify(f"Actuator Unrecognized: {act_name}", type='warning')
            return
        
        # [Spec 15.4] Thermal Guard: Use pulse for solenoids to prevent burnout.
        if norm_name.startswith("sol") and float(val) > 0.0:
            asyncio.create_task(self.safety.pulse_solenoid(pid, norm_name, val))
            return
            
        payload = f"ACT:{norm_name}={val}"
        cache_key = (pid, norm_name)
        now = time.time()
        
        # [Spec 4.3.11] Deduplication logic
        cached = self.cmd_dedupe_cache.get(cache_key)
        if cached and cached['payload'] == payload:
            if now - cached['ts'] < self.REFRESH_INTERVAL:
                return 
                
        # Update cache and dispatch
        self.cmd_dedupe_cache[cache_key] = {"payload": payload, "ts": now, "mtype": meowprotocol.MSG_TYPE_CMD}
        asyncio.create_task(self.send_physical(pid, meowprotocol.MSG_TYPE_CMD, payload))

    def _normalize_actuator_name(self, pid, name):
        """Resolves shorthand or numeric actuator names to the canonical ID."""
        limb = GLOBAL_TWIN.limbs.get(pid)
        if not limb: return None
        if name in limb.actuators: return name
        
        # Fuzzy matching for numeric inputs (e.g. "1" -> "sol1")
        clean_num = "".join([c for c in name.lower() if c.isdigit()])
        for prefix in ["sol", "solenoid_", "s"]:
            test_id = f"{prefix}{clean_num}"
            if test_id in limb.actuators: return test_id
        return None

    async def dedupe_cache_refresher(self):
        """
        [Spec 4.3.11] Self-Healing Command Registry Watchdog.
        
        Periodically re-transmits the last known state for cached commands 
        to ensure hardware state consistency across potential link interruptions.
        """
        while self.running:
            try:
                now = time.time()
                for key, data in list(self.cmd_dedupe_cache.items()):
                    if now - data['ts'] > self.REFRESH_INTERVAL:
                        await self.send_physical(key[0], data['mtype'], data['payload'])
                        data['ts'] = now
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Hub] Dedupe Refresher Error: {e}")
                await asyncio.sleep(5.0)

    async def _broadcast_time_sync(self):
        """Synchronizes system time across all downstream Pico limbs."""
        now_epoch = int(time.time())
        for pid in self.config_ports:
            await self.send_physical(pid, meowprotocol.CMD_SYNC_TIME, str(now_epoch))

    async def host_health_monitor(self):
        """
        [Spec 21.0] Host Health Driver (Active Measurement).
        
        Following the 'Passive Twin' rectification, this task performs all 
        active OS polling (psutil/sysfs) and pushes the results to the Twin.
        """
        while self.running:
            try:
                # 1. CPU Metrics
                cpu_cores = psutil.cpu_percent(percpu=True)
                GLOBAL_TWIN.host.cpu_cores = cpu_cores
                GLOBAL_TWIN.host.cpu_avg = sum(cpu_cores) / len(cpu_cores)
                
                # 2. Memory & Disk
                mem = psutil.virtual_memory()
                GLOBAL_TWIN.host.ram_percent = mem.percent
                
                disk = psutil.disk_usage('/')
                GLOBAL_TWIN.host.disk_percent = disk.percent
                
                # 3. Thermals (RPi5 Broadcom Sysfs)
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        # Convert millidegrees to degrees
                        GLOBAL_TWIN.host.temp = int(f.read()) / 1000
                except (FileNotFoundError, PermissionError):
                    pass
                
                # Push update frequency: 0.2Hz (Every 5 seconds)
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Hub] Host Health Driver Error: {e}")
                await asyncio.sleep(5.0)

    async def log_request_watchdog(self):
        """Handles timeouts for hardware log retrieval requests."""
        while self.running:
            try:
                now = time.time()
                for pid, start in list(self.pending_log_requests.items()):
                    if now - start > 3.0:
                        # Trigger an empty log packet to satisfy the router wait
                        STREAM_ROUTER.route_packet(pid, meowprotocol.MSG_TYPE_LOG, b"")
                        del self.pending_log_requests[pid]
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Hub] Log Watchdog Error: {e}")
                await asyncio.sleep(1.0)

    def _notify(self, msg, type='info'):
        """Pushes a notification message to the GUI consumer queue."""
        self.ui_notification_queue.put_nowait((msg, type))

    def stop(self):
        """Clean shutdown of the Coordinator lifecycle."""
        logger.info("[Hub] Coordinator Shutdown Initiated.")
        self.running = False