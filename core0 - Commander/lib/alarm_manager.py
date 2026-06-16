# lib/alarm_manager.py - Safety & Fault Logic (v1.17 - Unified Thermal Alignment)
# PURPOSE: Monitors telemetry and triggers E-STOP or Throttling.
# COMPLIANCE: Core 0 Spec Section 18.1 (Alarm States) & Section 15.4 (Thermal Hierarchy)
# CHANGES:
#   - v1.17: Unified Thermal Hierarchy (Throttle 55C, Pause 65C, Critical 85C).
#   - v1.17: Enforced Hysteresis Gate (Must cool to 55C after Pause/Critical).
#   - v1.16: LQI Burn-In Logic based on packet count.

"""
[Spec 18.1] Ninelives Alarm Management System.

The AlarmManager serves as the 'Passive Evaluator' of the Ninelives architecture.
Unlike the SafetyManager, which provides high-frequency reflexive protection,
the AlarmManager focuses on evaluative health, environmental thresholds,
and operator-aware fault states.

Key Responsibilities:
1. Health Evaluation (Spec 15.2): Periodically scans the Digital Twin for limit breaches.
2. Thermal Hierarchy (Spec 15.4): Enforces the 3-tier safety strategy (Throttle/Pause/Hard Stop).
3. Alarm Lifecycle (Spec 18.1): Manages transitions between Active, Acknowledged, and Cleared.
4. Arming Interlock (Spec 18.2): Prevents high-voltage state transitions during active faults.
"""

import time
import logging
from . import machine_states as ms

try:
    import config.debug as dbg

    DEBUG_LOGIC = getattr(dbg, "DEBUG_ALARMS", True)
except ImportError:
    DEBUG_LOGIC = True

# Setup Named Logger for industrial auditing
logger = logging.getLogger("AlarmManager")


class AlarmManager:
    """
    [Spec 18.1] The Alarm Manager.

    Evaluates the Digital Twin state against safety limits and enforces
    the industrial thermal hierarchy. It acts as the primary authority for
    notifying the human operator of system degradation.
    """

    def __init__(self, machine_model):
        """
        Initializes the Alarm Manager and its internal registries.

        :param machine_model: Reference to the singleton Digital Twin.
        """
        self.model = machine_model
        self.active_alarms = {}  # { "CODE": "SEVERITY" } - Currently blocking
        self.acknowledged_alarms = {}  # { "CODE": "SEVERITY" } - Operator accepted risk
        self.alarm_contexts = {}  # { "CODE": "Last Message" }
        self.history = []

        # Track when the manager was born to allow for startup grace periods (Spec 18.3)
        self.boot_time = time.time()

        # --- UNIFIED INDUSTRIAL THRESHOLDS (Spec 15.4) ---
        self.LIMITS = {
            "VOLTAGE_MIN": 4.4,
            "TEMP_THROTTLE": 55.0,  # Tier 1: Slow down feeder
            "TEMP_PAUSE": 65.0,  # Tier 2: Safety Pause (Force IDLE)
            "TEMP_CRITICAL": 85.0,  # Tier 3: Hard Stop (Force ERROR)
            "LQI_MIN": 25.0,  # Link Quality Indicator floor
            "MATURITY_TIME_S": 5.0,  # Silence alarms during boot
            "LQI_BURN_IN_PACKETS": 50,  # Minimum samples for LQI validity
        }

    def check_health(self):
        """
        [Spec 15.2] Central Health Observer.

        Evaluates the current state of the Digital Twin against unified limits.
        This method executes on the 1Hz evaluative heartbeat. It prioritizes
        connectivity, then electrical health, then thermal stability.

        :return: Boolean indicating if the system is currently fault-free.
        """
        system_safe = True
        now = time.time()
        elapsed_since_boot = now - self.boot_time

        for limb_id, limb in self.model.limbs.items():
            # 1. Connection Check (Spec 15.1)
            # Suppress offline alarms during initial startup window
            if limb.remote_state == ms.STATE_OFFLINE:
                if elapsed_since_boot > self.LIMITS["MATURITY_TIME_S"]:
                    self.raise_alarm(
                        f"L{limb_id}_OFFLINE", ms.SEVERITY_CRITICAL, "Heartbeat Lost"
                    )
                    system_safe = False
                continue
            else:
                self.clear_alarm(f"L{limb_id}_OFFLINE")

            # --- DATA MATURITY FILTER (Spec 18.3) ---
            # Ignore uninitialized telemetry from limbs that just joined the fleet
            if limb.uptime <= 0 or limb.voltage == 0.0:
                continue

            # 2. Voltage Check
            if limb.voltage < self.LIMITS["VOLTAGE_MIN"]:
                self.raise_alarm(
                    f"L{limb_id}_UNDERVOLT", ms.SEVERITY_CRITICAL, f"V={limb.voltage}"
                )
                system_safe = False
            else:
                self.clear_alarm(f"L{limb_id}_UNDERVOLT")

            # 3. UNIFIED THERMAL HIERARCHY (Spec 15.4)

            # Tier 3: Critical Fire Alarm (85C)
            # Triggers immediate broadcast stop and locks the system in STATE_ERROR.
            if limb.temp >= self.LIMITS["TEMP_CRITICAL"]:
                self.raise_alarm(
                    f"L{limb_id}_FIRE",
                    ms.SEVERITY_CRITICAL,
                    f"T={limb.temp}C (CRITICAL)",
                )
                system_safe = False
                limb.needs_cooldown = True
            else:
                self.clear_alarm(f"L{limb_id}_FIRE")

            # Tier 2: Safety Pause (65C)
            # Forces machine to IDLE to allow convective cooling.
            if limb.temp >= self.LIMITS["TEMP_PAUSE"]:
                self.raise_alarm(
                    f"L{limb_id}_OVERHEAT_PAUSE",
                    ms.SEVERITY_PAUSE,
                    f"T={limb.temp}C (PAUSE)",
                )
                limb.needs_cooldown = True
            else:
                self.clear_alarm(f"L{limb_id}_OVERHEAT_PAUSE")

            # Tier 1: Pre-emptive Throttling (55C)
            # Lowers flow rates while maintaining production.
            if limb.temp >= self.LIMITS["TEMP_THROTTLE"]:
                if not getattr(limb, "needs_cooldown", False):
                    self.raise_alarm(
                        f"L{limb_id}_THROTTLE", ms.SEVERITY_WARNING, f"T={limb.temp}C"
                    )
                    limb.is_throttled = True
            else:
                self.clear_alarm(f"L{limb_id}_THROTTLE")
                # Hysteresis Reset: Only release throttling/cooldown if below Tier 1 threshold.
                if getattr(limb, "needs_cooldown", False):
                    limb.needs_cooldown = False
                    self.clear_alarm(f"L{limb_id}_COOLING")
                limb.is_throttled = False

            # [Spec 15.4.2] Hysteresis Feedback for UI
            if getattr(limb, "needs_cooldown", False):
                ctx = f"Cooling: {limb.temp}C -> target {self.LIMITS['TEMP_THROTTLE']}C"
                self.raise_alarm(f"L{limb_id}_COOLING", ms.SEVERITY_PAUSE, ctx)
                system_safe = False

            # 4. Network Health (Spec 20.2)
            lqi = getattr(limb, "lqi", 100.0)
            total_pkts = getattr(limb, "packet_count", 0)

            # Ensure enough packets have been processed to make LQI math statistically valid
            if total_pkts > self.LIMITS["LQI_BURN_IN_PACKETS"]:
                if lqi < self.LIMITS["LQI_MIN"]:
                    self.raise_alarm(
                        f"L{limb_id}_LQI_LOW",
                        ms.SEVERITY_WARNING,
                        f"LQI={round(lqi, 1)}%",
                    )
                else:
                    self.clear_alarm(f"L{limb_id}_LQI_LOW")
            else:
                self.clear_alarm(f"L{limb_id}_LQI_LOW")

            # 5. Actuator Verification Spectrum (Spec 3.2)
            for act_name, act in limb.actuators.items():
                if "FAULT" in act.verification_state:
                    self.raise_alarm(
                        f"L{limb_id}_{act_name}_FAULT",
                        ms.SEVERITY_CRITICAL,
                        act.verification_state,
                    )
                    system_safe = False
                else:
                    self.clear_alarm(f"L{limb_id}_{act_name}_FAULT")

        return system_safe

    def acknowledge_alarm(self, code):
        """
        [Spec 18.1] Transitions an alarm to Acknowledged state.

        Moves an active fault from the primary 'Blocking' list to the 'Acknowledged'
        list. Note: SEVERITY_CRITICAL alarms cannot be acknowledged while the
        condition persists.

        :param code: The unique alarm identifier (e.g., 'L1_OFFLINE').
        :return: Boolean indicating if acknowledgement was accepted.
        """
        if code in self.active_alarms:
            severity = self.active_alarms[code]
            if severity == ms.SEVERITY_CRITICAL:
                logger.warning(
                    f"Safety Override Rejected: Cannot acknowledge CRITICAL alarm {code}."
                )
                return False

            self.acknowledged_alarms[code] = severity
            del self.active_alarms[code]
            logger.info(f"[ALARM] Acknowledged by Operator: {code}")
            return True
        return False

    def check_arming_safety(self):
        """
        [Spec 18.2] Industrial Arming Interlock.

        Blocks transitions to high-voltage states (ARMING/FLOW) if any
        unacknowledged high-severity alarms exist in the registry.

        :return: (Boolean, String) - Safety status and the first blocking reason found.
        """
        for code, severity in self.active_alarms.items():
            if severity in [ms.SEVERITY_CRITICAL, ms.SEVERITY_PAUSE]:
                return False, f"Interlock Active: {code} ({severity})"
        return True, "Safe"

    def raise_alarm(self, code, severity, context=""):
        """
        Triggers a new alarm event and potentially modifies system state.

        Updates the registry and history. If severity is CRITICAL, it forces
        the machine into STATE_ERROR. If severity is PAUSE, it forces the
        machine into STATE_IDLE.

        :param code: Unique identifier for the fault.
        :param severity: Severity constant from machine_states (WARNING, PAUSE, CRITICAL).
        :param context: Human-readable description of the fault.
        """
        self.alarm_contexts[code] = context
        if code not in self.active_alarms and code not in self.acknowledged_alarms:
            self.active_alarms[code] = severity
            timestamp = time.strftime("%H:%M:%S")
            log_msg = f"[{severity}] {code}: {context}"

            # Handle State Machine Escalations
            if severity == ms.SEVERITY_CRITICAL:
                logger.critical(log_msg)
                self.model.set_state(ms.STATE_ERROR)
            elif severity == ms.SEVERITY_PAUSE:
                logger.error(log_msg)
                if self.model.host_state == ms.STATE_FLOW:
                    self.model.set_state(ms.STATE_IDLE)
            else:
                logger.warning(log_msg)

            self.history.append(
                {"ts": timestamp, "code": code, "lvl": severity, "ctx": context}
            )

    def clear_alarm(self, code):
        """
        Removes a fault condition from all registries.

        Used when telemetry confirms that a previously breached limit has
        returned to a safe operating range.

        :param code: The alarm identifier to remove.
        """
        removed = False
        if code in self.active_alarms:
            del self.active_alarms[code]
            removed = True
        if code in self.acknowledged_alarms:
            del self.acknowledged_alarms[code]
            removed = True

        if removed:
            logger.info(f"[ALARM] Condition Cleared: {code}")
            if code in self.alarm_contexts:
                del self.alarm_contexts[code]

    def get_active_list(self):
        """Returns the dictionary of currently active, unacknowledged alarms."""
        return self.active_alarms

    def get_active_details(self):
        """
        Aggregates details for all alarms (Active and Acknowledged).
        Used by the GUI update_tick to populate the status banner.
        """
        data = {
            k: {"lvl": v, "msg": self.alarm_contexts.get(k, ""), "acked": False}
            for k, v in self.active_alarms.items()
        }
        data.update(
            {
                k: {"lvl": v, "msg": self.alarm_contexts.get(k, ""), "acked": True}
                for k, v in self.acknowledged_alarms.items()
            }
        )
        return data
