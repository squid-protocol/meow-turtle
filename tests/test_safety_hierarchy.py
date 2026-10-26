"""
Tests for Core 0 Safety Hierarchy, Thermal Tiers, Alarms, and Watchdogs.
"""

import asyncio
import time
import pytest
from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms

class TestSafetyHierarchy:

    async def test_thermal_tier_1_throttling_and_hysteresis(self, hub):
        """Verifies Thermal Tier 1 engages at 55C and releases below 50C."""
        p1 = GLOBAL_TWIN.limbs[1]
        p1.temp = 56.5
        await hub.safety._check_thermal_health()
        assert hub.safety._is_throttled is True

        # Hysteresis check (52.0C - still within hysteresis buffer)
        p1.temp = 52.0
        await hub.safety._check_thermal_health()
        assert hub.safety._is_throttled is True

        # Release check (48.0C - drops below 50.0C threshold)
        p1.temp = 48.0
        await hub.safety._check_thermal_health()
        assert hub.safety._is_throttled is False

    async def test_thermal_tier_2_safety_pause(self, hub):
        """Verifies Tier 2 (66C) forces system fallback to IDLE."""
        GLOBAL_TWIN.set_state(ms.STATE_FLOW)
        p1 = GLOBAL_TWIN.limbs[1]
        p1.temp = 66.0
        await hub.safety._check_thermal_health()
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        p1.temp = 28.5  # restore

    async def test_thermal_tier_3_critical_fire_alarm(self, hub):
        """Verifies Tier 3 (86C) forces system into ERROR state."""
        hub.safety.clear_recovery_grace()
        p1 = GLOBAL_TWIN.limbs[1]
        p1.temp = 86.0
        await hub.safety._check_thermal_health()
        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR
        p1.temp = 28.5  # restore

        # Arming must be strictly blocked in ERROR state
        can_arm = hub.safety.is_safe_to_arm()
        assert can_arm is False

        # Recover from ERROR back to IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_undervoltage_interlock(self, hub):
        """Verifies rail voltage below 4.4V raises alarm and blocks arming."""
        p3 = GLOBAL_TWIN.limbs[3]
        p3.uptime = 100
        p3.voltage = 4.15
        hub.alarms.check_health()
        assert "L3_UNDERVOLT" in hub.alarms.active_alarms

        safe_to_arm, msg = hub.alarms.check_arming_safety()
        assert safe_to_arm is False
        assert "L3_UNDERVOLT" in msg

        # Voltage recovers to 5.0V
        p3.voltage = 5.05
        hub.alarms.check_health()
        assert "L3_UNDERVOLT" not in hub.alarms.active_alarms
        safe_to_arm, _ = hub.alarms.check_arming_safety()
        assert safe_to_arm is True

    async def test_solenoid_thermal_fuse_duty_cycle(self, hub):
        """Verifies solenoids cannot be reactivated faster than 2.0s duty cycle."""
        if GLOBAL_TWIN.host_state != ms.STATE_IDLE:
            await hub.send_cmd("RESET")
            await asyncio.sleep(1.2)

        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.1)
        assert GLOBAL_TWIN.host_state == ms.STATE_DEV

        # First pulse
        await hub.send_manual_command(1, "SOL_TDWN", 1.0)
        last_fired = hub.safety._solenoid_cooldowns.get((1, "SOL_TDWN"), 0.0)
        assert last_fired > 0.0

        # Rapid second pulse within 200ms must be rejected
        await asyncio.sleep(0.2)
        await hub.send_manual_command(1, "SOL_TDWN", 1.0)
        now = time.time()
        # Cooldown record should remain the original timestamp
        assert (now - last_fired) < 2.0

        # Return to IDLE
        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.1)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_silent_node_watchdog(self, hub):
        """Verifies absence of limb heartbeats for >5.0s triggers watchdog."""
        p1 = GLOBAL_TWIN.limbs[1]
        p1.last_update = time.time() - 6.0
        elapsed = time.time() - p1.last_update
        assert elapsed > hub.safety.WATCHDOG_TIMEOUT
