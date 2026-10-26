"""
Tests for Core 0 operational modes and dual-interlock state transitions.
"""

import asyncio
import time
import pytest
from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms

class TestStateTransitions:

    async def test_initial_boot_to_idle(self, hub):
        """Verifies system bootstraps into IDLE with online limbs."""
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        for pid in [1, 2, 3]:
            limb = GLOBAL_TWIN.limbs.get(pid)
            assert limb is not None
            assert limb.remote_state == ms.STATE_IDLE

    async def test_dev_mode_toggle(self, hub):
        """Verifies toggling DEV mode from IDLE and back."""
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.1)
        assert GLOBAL_TWIN.host_state == ms.STATE_DEV

        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.1)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_arming_valid_profile_and_collision(self, hub):
        """Verifies arming sequence reaches FLOW and blocks secondary arming collisions."""
        success = await hub.jobs.run_arming_sequence("BUILD_INVENTORY")
        assert success is True
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW

        # Attempting to arm again while active must be rejected
        collision_attempt = await hub.jobs.run_arming_sequence("BUILD_INVENTORY")
        assert collision_attempt is False

        # Reset back to IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_missing_profile_rejected(self, hub):
        """Verifies non-existent profiles abort arming without crashing."""
        success = await hub.jobs.run_arming_sequence("NON_EXISTENT_PROFILE_XYZ")
        assert success is False
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_adaptive_stop_from_flow(self, hub):
        """
        Verifies adaptive stop pauses feeder first, runs 5.0s conveyor runout,
        and then places all limbs into IDLE.
        """
        # Arm into FLOW
        arm_ok = await hub.jobs.run_arming_sequence("BUILD_INVENTORY")
        assert arm_ok is True
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW

        # Trigger Adaptive Stop
        start_t = time.time()
        await hub.jobs.enter_idle_sequence()
        dur = time.time() - start_t

        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        assert dur >= 5.0 # Enforced 5.0s conveyor clearance
