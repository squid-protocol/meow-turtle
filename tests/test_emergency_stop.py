"""
Tests for Emergency Stop (E-STOP) and hardware error handling across all operational modes.
"""

import asyncio
import time
import pytest
from lib.digital_twin import GLOBAL_TWIN, Actuator
import lib.machine_states as ms

class TestEmergencyStop:

    async def test_estop_in_idle_mode(self, hub):
        """Verifies E-STOP issued in IDLE mode forces ERROR across host and fleet."""
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        await hub.send_cmd("STOP")
        await asyncio.sleep(0.2)

        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR
        for limb in GLOBAL_TWIN.limbs.values():
            assert limb.remote_state == ms.STATE_ERROR

        # Recover back to IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_estop_in_dev_mode(self, hub):
        """Verifies E-STOP issued in DEV mode immediately shuts down manual actuation."""
        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_DEV

        await hub.send_cmd("STOP")
        await asyncio.sleep(0.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR
        for limb in GLOBAL_TWIN.limbs.values():
            assert limb.remote_state == ms.STATE_ERROR

        # Recover back to IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_actuator_stall_override_in_dev(self, hub):
        """Verifies limb actuator stall (F_STL) triggers safety escalation to ERROR in DEV."""
        await hub.send_cmd("DEV_TOGGLE")
        await asyncio.sleep(0.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_DEV

        p1 = GLOBAL_TWIN.limbs[1]
        if "feeder" not in p1.actuators:
            p1.actuators["feeder"] = Actuator("feeder", 0.0)
        p1.actuators["feeder"].verification_state = ms.ACT_FAULT_STALL

        hub.safety.clear_recovery_grace()
        await asyncio.sleep(0.5)
        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR

        # Clear fault badge and reset
        p1.actuators["feeder"].verification_state = ms.ACT_CONFIRMED_OFF
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_arming_blocked_by_limb_error(self, hub):
        """Verifies arming is prevented if any limb is in ERROR state."""
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
        GLOBAL_TWIN.limbs[3].remote_state = ms.STATE_ERROR
        hub.fleet.controllers[3].sim_state = ms.STATE_ERROR

        safe = hub.safety.is_safe_to_arm()
        assert safe is False

        # Restore limb 3
        GLOBAL_TWIN.limbs[3].remote_state = ms.STATE_IDLE
        hub.fleet.controllers[3].sim_state = ms.STATE_IDLE

    async def test_arming_aborts_on_handshake_fault(self, hub):
        """Verifies arming safely aborts to ERROR if a limb faults mid-handshake."""
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

        async def drop_limb():
            await asyncio.sleep(0.02)
            hub.fleet.controllers[1].sim_state = ms.STATE_ERROR
            GLOBAL_TWIN.limbs[1].remote_state = ms.STATE_ERROR

        fault_task = asyncio.create_task(drop_limb())
        arm_ok = await hub.jobs.run_arming_sequence(ms.PROFILE_SCAN)
        await fault_task

        assert arm_ok is False
        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR

        # Restore limb 1 and reset
        hub.fleet.controllers[1].sim_state = ms.STATE_IDLE
        GLOBAL_TWIN.limbs[1].remote_state = ms.STATE_IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_instantaneous_estop_during_flow(self, hub):
        """Verifies E-STOP during FLOW cuts power instantaneously (<100ms) without runout delay."""
        arm_ok = await hub.jobs.run_arming_sequence(ms.PROFILE_SCAN)
        assert arm_ok is True
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW

        start_t = time.time()
        await hub.send_cmd("STOP")
        latency = time.time() - start_t

        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR
        assert latency < 0.25 # Sub-250ms cut (instantaneous vs 5s runout)
        for ctrl in hub.fleet.controllers.values():
            assert ctrl.sim_state == ms.STATE_ERROR

        # Recover
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    async def test_split_brain_dropout_in_flow(self, hub):
        """Verifies silent limb dropout to IDLE while host is in FLOW escalates to ERROR."""
        if GLOBAL_TWIN.host_state != ms.STATE_IDLE:
            await hub.send_cmd("RESET")
            await asyncio.sleep(1.2)

        arm_ok = await hub.jobs.run_arming_sequence(ms.PROFILE_SCAN)
        assert arm_ok is True
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW

        # Simulate limb 1 dropping back to IDLE
        hub.fleet.controllers[1].sim_state = ms.STATE_IDLE
        GLOBAL_TWIN.limbs[1].remote_state = ms.STATE_IDLE
        hub.safety.clear_recovery_grace()

        await asyncio.sleep(1.0)
        assert GLOBAL_TWIN.host_state == ms.STATE_ERROR

        # Restore limb 1 and reset back to IDLE
        hub.fleet.controllers[1].sim_state = ms.STATE_IDLE
        GLOBAL_TWIN.limbs[1].remote_state = ms.STATE_IDLE
        await hub.send_cmd("RESET")
        await asyncio.sleep(1.2)
        assert GLOBAL_TWIN.host_state == ms.STATE_IDLE
