# lib/safety_tasks.py - Ninelives Core 0 (v6.9.0 Industrial Standard)
# ROLE: The Immune System. Real-time protection, watchdogging, and thermal management.
# COMPLIANCE: Spec 15 (Safety), Spec 15.1 (Aggressive Watchdog), Spec 15.4 (Thermal Tiering)
# VERSION: v6.9.0 - Unified Thermal Hierarchy Alignment.

"""
[Spec 6.0] Ninelives Safety Management System (The Immune System).

The SafetyManager is the primary 'Reflexive Brain' of the Ninelives architecture. 
Operating at a high frequency (20Hz), it monitors the Digital Twin for violations 
 of physical safety parameters, hardware faults, and environment-driven 
degradation. 

Key Responsibilities:
1. Reflexive Protection (Spec 15.5): Reacts to Pico-level hardware faults (Stall/Runaway).
2. Aggressive Watchdog (Spec 15.1): Monitors node liveness and signal integrity (LQI).
3. Thermal Hierarchy (Spec 15.4): Implements tiered responses to overheating.
4. Kinetic Shield: Verifies physical motion via odometer feedback to detect jams.
5. Command Interlock (Spec 18.2): Authorizes or blocks high-voltage arming sequences.
"""

import asyncio
import time
from lib.rp5_logger import logger
from lib.digital_twin import GLOBAL_TWIN
from lib import machine_states as ms
from lib import meowprotocol

class SafetyManager:
    """
    [Spec 6.0] The Immune System.
    
    The sole authority for monitoring the Digital Twin for safety violations. 
    It performs high-speed 'Badge Scanning' to synchronize hardware-autonomous 
    safety decisions with global system coordination.
    """

    def __init__(self, coordinator):
        """
        Initializes the Safety Manager and establishes the reflexive thresholds.
        
        :param coordinator: Reference to the SystemCoordinator (The Hub).
        """
        self.coord = coordinator
        self.running = True
        
        # State Tracking
        self._last_host_state = ms.STATE_IDLE
        self._grace_period_end = 0.0
        self._is_throttled = False
        self._solenoid_cooldowns = {} # {(pid, act_name): last_pulse_time}
        self._last_odometer_reading = {1: 0, 2: 0, 3: 0}
        self._last_motion_ts = time.time()
        
        # --- AGGRESSIVE THRESHOLDS & CONSTANTS ---
        self.WATCHDOG_TIMEOUT = 5.0       # [Spec 15.1] Time before a silent node is declared dead
        self.WATCHDOG_INTERVAL = 0.5      # Frequency of liveness check
        self.LQI_CRITICAL_THRESHOLD = 25.0 # [Spec 20.2] Link Quality floor for emergency stop
        self.MOTION_TIMEOUT = 2.0         # Seconds allowed for stationary belt while in FLOW
        self.RECOVERY_GRACE_S = 10.0      # [Spec 15.3] Window to allow boot-up without re-tripping
        self.OBSERVER_HERTZ = 20          # 50ms reflex loop
        
        # [Spec 15.4] Unified Thermal Constants
        self.THERMAL_THROTTLE_C = 55.0  # Tier 1: Slow down feeder
        self.THERMAL_PAUSE_C = 65.0     # Tier 2: Force IDLE (Safety Pause)
        self.THERMAL_CRITICAL_C = 85.0  # Tier 3: Force ERROR (Fire/Critical)
        self.THERMAL_HYSTERESIS = 5.0   

        logger.info("[Safety] SafetyManager v6.9.0 Online. Unified Thermal Hierarchy Active.")

    # --------------------------------------------------------------------------
    # RECOVERY & ALARM INTERLOCKS
    # --------------------------------------------------------------------------
    def trigger_recovery_grace(self):
        """
        [Spec 15.3] Inhibits STATE_ERROR transitions for a brief window post-reset.
        
        Allows the hardware fleet to transition through BOOT/IDLE states 
        without the watchdog immediately re-triggering due to transient 
        initialization delays.
        """
        self._grace_period_end = time.time() + self.RECOVERY_GRACE_S
        logger.info(f"[Safety] Recovery Grace Active for {self.RECOVERY_GRACE_S}s.")

    @property
    def in_grace_period(self):
        """Checks if the system is currently within the post-reset safety window."""
        return time.time() < self._grace_period_end

    def is_safe_to_arm(self):
        """
        [Spec 18.2] Industrial Arming Interlock.
        
        Determines if the hardware fleet is physically capable of entering FLOW.
        Checks for:
        1. Ghost Nodes (missing expected hardware).
        2. Signal Integrity (LQI above critical threshold).
        3. Active Fault Badges (existing stalls or runaway conditions).
        
        :return: Boolean indicating if arming is permitted.
        """
        # 1. Ghost Detection
        if 1 in GLOBAL_TWIN.limbs and len(self.coord.config_ports) > 1:
            logger.error("[Safety] ARMING BLOCKED: Ghost Node detected.")
            return False

        # 2. Signal Integrity Check
        for pid, limb in GLOBAL_TWIN.limbs.items():
            if limb.lqi < self.LQI_CRITICAL_THRESHOLD:
                logger.error(f"[Safety] ARMING BLOCKED: P{pid} LQI Critical ({limb.lqi:.1f}%)")
                return False

        # 3. Check for Active Fault Badges (Spec 15.5)
        for pid, limb in GLOBAL_TWIN.limbs.items():
            for act in limb.actuators.values():
                if act.verification_state in [ms.ACT_FAULT_STALL, ms.ACT_FAULT_RUNAWAY]:
                    logger.error(f"[Safety] ARMING BLOCKED: {limb.name} has latched fault: {act.name}")
                    return False

        return True

    # --------------------------------------------------------------------------
    # THERMAL FUSE (SOLENOID PROTECTION)
    # --------------------------------------------------------------------------
    async def pulse_solenoid(self, pid, act_name, val):
        """
        [Spec 15.4] Duty-Cycle protection for pneumatic solenoids.
        
        Prevents coil burnout during manual testing by enforcing a 2.0s 
        cooldown between pulses. Automatically handles the 'Off' command 
        after a 500ms trigger.
        """
        key = (pid, act_name)
        now = time.time()
        
        if now - self._solenoid_cooldowns.get(key, 0.0) < 2.0:
            return

        try:
            self._solenoid_cooldowns[key] = now
            await self.coord.send_physical(pid, meowprotocol.MSG_TYPE_CMD, f"ACT:{act_name}={val}")
            await asyncio.sleep(0.5)
            await self.coord.send_physical(pid, meowprotocol.MSG_TYPE_CMD, f"ACT:{act_name}=0.0")
        except Exception as e:
            logger.error(f"[Safety] Thermal Pulse Failure: {e}")

    # --------------------------------------------------------------------------
    # MONITORING LOOPS
    # --------------------------------------------------------------------------
    async def monitor_loop(self):
        """
        [Spec 15.2] Central Safety Observer (20Hz).
        
        The primary high-frequency reflex loop. Performs real-time auditing of:
        - Thermal health (3-tier escalation).
        - Hardware fault badge synchronization.
        - Kinetic motion verification (jam detection).
        - State-based stop coordination.
        """
        while self.running:
            try:
                # 1. Thermal Health Check (Spec 15.4 Tiering)
                await self._check_thermal_health()
                
                # 2. Badge Scanning (Spec 15.5 Hardware Reflex Sync)
                await self._scan_for_hardware_overrides()

                # 3. Motion Verification (Mechanical Jam Detection)
                if GLOBAL_TWIN.host_state == ms.STATE_FLOW:
                    await self._verify_motion()

                # 4. State-Based Halt Coordination
                current_state = GLOBAL_TWIN.host_state
                if current_state == ms.STATE_ERROR and self._last_host_state != ms.STATE_ERROR:
                    if self.in_grace_period:
                        GLOBAL_TWIN.set_state(ms.STATE_BOOT)
                    else:
                        logger.critical("[Safety] CRITICAL: Fault detected. Executing Broadcast Stop.")
                        await self.coord.broadcast_stop()
                
                self._last_host_state = current_state
                await asyncio.sleep(1.0 / self.OBSERVER_HERTZ)
                
            except Exception as e:
                logger.error(f"[Safety] Observer Loop Crash: {e}")
                await asyncio.sleep(1.0)

    async def _scan_for_hardware_overrides(self):
        """
        [Spec 15.5] Detects and reacts to Pico-autonomous safety decisions.
        
        Monitors the Digital Twin for 'F_STL' (Stall) or 'F_RUN' (Runaway) badges.
        If detected, it escalates the local limb fault to a global system ERROR.
        """
        for pid, limb in GLOBAL_TWIN.limbs.items():
            for act_name, act in limb.actuators.items():
                if act.verification_state in [ms.ACT_FAULT_STALL, ms.ACT_FAULT_RUNAWAY]:
                    if not self.in_grace_period:
                        logger.critical(f"[Safety] HW OVERRIDE: {limb.name} reports {act_name} is {act.verification_state}!")
                        GLOBAL_TWIN.set_state(ms.STATE_ERROR)
                        return

    async def _verify_motion(self):
        """
        Kinetic Jam detection via odometer stagnation.
        
        Monitors the pulse count from Pico 3 (Distributor). If the belt is 
        commanded ON but the odometer remains stationary for >2.0s, a 
        mechanical jam is declared.
        """
        limb = GLOBAL_TWIN.limbs.get(3) # Distributor Odometer
        if not limb: return

        current_pulse = 0
        if "odo" in limb.sensors:
            current_pulse = limb.sensors["odo"].raw_value
        elif "pulse_count" in limb.sensors:
            current_pulse = limb.sensors["pulse_count"].raw_value

        now = time.time()
        if current_pulse == self._last_odometer_reading[3]:
            if (now - self._last_motion_ts) > self.MOTION_TIMEOUT:
                logger.critical("[Safety] MOTION TIMEOUT: Belt reported ON but pulse count is stationary.")
                GLOBAL_TWIN.set_state(ms.STATE_ERROR)
        else:
            self._last_odometer_reading[3] = current_pulse
            self._last_motion_ts = now

    async def _check_thermal_health(self):
        """
        [Spec 15.4.1] Unified Thermal Tiering logic.
        
        Monitors all limb temperatures and applies the appropriate workload 
        management strategy:
        Tier 1 (55C): Throttle feeder flow.
        Tier 2 (65C): Fallback to IDLE (Safety Pause).
        Tier 3 (85C): Global E-STOP (Critical Fault).
        """
        max_temp = 0.0
        for limb in GLOBAL_TWIN.limbs.values():
            max_temp = max(max_temp, limb.temp)

        # Tier 3: Critical Fire Alarm (85C)
        if max_temp >= self.THERMAL_CRITICAL_C:
            if not self.in_grace_period:
                logger.critical(f"[Safety] THERMAL FIRE: {max_temp}C exceeds critical limit!")
                GLOBAL_TWIN.set_state(ms.STATE_ERROR)
            return

        # Tier 2: Safety Pause (65C)
        if max_temp >= self.THERMAL_PAUSE_C:
            if GLOBAL_TWIN.host_state == ms.STATE_FLOW:
                logger.warning(f"[Safety] THERMAL PAUSE: {max_temp}C triggers fallback to IDLE.")
                GLOBAL_TWIN.set_state(ms.STATE_IDLE)
            return

        # Tier 1: Pre-emptive Throttling (55C)
        if max_temp >= self.THERMAL_THROTTLE_C and not self._is_throttled:
            self._is_throttled = True
            logger.info(f"[Safety] Thermal Throttling Active: {max_temp}C")
            await self.coord.send_physical(1, meowprotocol.MSG_TYPE_SET_CFG, "CFG:ACT:feeder:flow=0.4")
        elif self._is_throttled and max_temp < (self.THERMAL_THROTTLE_C - self.THERMAL_HYSTERESIS):
            self._is_throttled = False
            logger.info(f"[Safety] Thermal Throttling Released: {max_temp}C")
            # Clear manual throttle from cache to allow refresh
            cache_key = (1, "feeder")
            if cache_key in self.coord.cmd_dedupe_cache:
                del self.coord.cmd_dedupe_cache[cache_key]

    async def watchdog_task(self):
        """
        [Spec 15.1] Aggressive Watchdog Task.
        
        Monitors the liveness of the fleet. Triggers a global system ERROR if:
        1. A node fails to connect after boot (Ghost Node).
        2. A node stops communicating for >5.0s (Silent Node).
        3. A node's signal integrity falls below 25% (Signal Loss).
        """
        while self.running:
            try:
                now = time.time()
                for pid, limb in GLOBAL_TWIN.limbs.items():
                    # Judgement A: Never Connected (Ghost Watchdog)
                    if limb.remote_state == ms.STATE_OFFLINE:
                        if not self.in_grace_period:
                            logger.critical(f"[Safety] WATCHDOG: P{pid} is MISSING from fleet.")
                            GLOBAL_TWIN.set_state(ms.STATE_ERROR)
                        continue

                    # Judgement B: Lost Connection (Heartbeat Watchdog)
                    if (now - limb.last_update) > self.WATCHDOG_TIMEOUT:
                        if not self.in_grace_period:
                            logger.critical(f"[Safety] WATCHDOG: P{pid} SILENT for >{self.WATCHDOG_TIMEOUT}s.")
                            limb.remote_state = ms.STATE_OFFLINE
                            GLOBAL_TWIN.set_state(ms.STATE_ERROR)

                    # Judgement C: Signal Integrity (LQI Watchdog)
                    if limb.lqi < self.LQI_CRITICAL_THRESHOLD:
                        if not self.in_grace_period:
                            logger.critical(f"[Safety] SIGNAL LOSS: P{pid} LQI {limb.lqi:.1f}%.")
                            GLOBAL_TWIN.set_state(ms.STATE_ERROR)
                
                await asyncio.sleep(self.WATCHDOG_INTERVAL)
            except Exception as e:
                logger.error(f"[Safety] Watchdog Judgement Fail: {e}")
                await asyncio.sleep(2.0)