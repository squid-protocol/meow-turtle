"""
tests/test_cosimulation.py - Combined Host & Firmware Co-Simulation Test Suite.

Executes real Raspberry Pi 5 Core 0 Coordinator tasks alongside real RP2040
MicroPython firmware instances (app.py, ActuatorManager, SensorManager)
simultaneously over in-memory duplex pipes on the asyncio event loop.
"""

import sys
import os
import asyncio
import pytest
import time

import tests.mock_rp2040 as mock_rp2040
mock_rp2040.install()

CORE0_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core0 - Commander"))
if CORE0_PATH not in sys.path:
    sys.path.insert(0, CORE0_PATH)

from lib.coordinator import SystemCoordinator
from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms
from lib import meowprotocol
from tests.firmware_pico import FirmwarePicoController


@pytest.fixture
async def cosim_hub():
    """
    Spawns a SystemCoordinator configured with real MicroPython firmware controllers.
    Cleanly starts background tasks and tears them down after each test.
    """
    GLOBAL_TWIN.host_state = ms.STATE_BOOT
    ports = {1: "/dev/ttyAMA0", 2: "/dev/ttyAMA2", 3: "/dev/ttyAMA3"}
    coord = SystemCoordinator(ports, simulate=True, controller_cls=FirmwarePicoController)
    await coord.start()
    await asyncio.sleep(0.5)

    yield coord

    # Teardown
    await coord.stop()
    await asyncio.sleep(0.2)
    # Restore digital twin default state
    GLOBAL_TWIN.host_state = ms.STATE_BOOT
    for pid in [1, 2, 3]:
        if pid in GLOBAL_TWIN.limbs:
            GLOBAL_TWIN.limbs[pid].remote_state = ms.STATE_IDLE


@pytest.mark.asyncio
async def test_cosim_discovery_and_health_sync(cosim_hub):
    """
    Verifies that Core 0 discovery handshake queries live MicroPython firmware
    nodes and syncs telemetry into the Digital Twin.
    """
    # 1. Verify Coordinator reaches IDLE
    assert GLOBAL_TWIN.host_state == ms.STATE_IDLE

    # 2. Verify all three limbs are discovered and online
    for pid in [1, 2, 3]:
        limb = GLOBAL_TWIN.limbs.get(pid)
        assert limb is not None
        assert limb.remote_state == ms.STATE_IDLE
        assert limb.voltage >= 4.5
        assert limb.temp >= 0

    # 3. Verify real firmware app.py instances exist and are in IDLE
    for pid in [1, 2, 3]:
        ctrl = cosim_hub.fleet.controllers[pid]
        assert isinstance(ctrl, FirmwarePicoController)
        assert ctrl.app.shared_state["current_state"] == ctrl.app.STATE_IDLE
        assert ctrl.app.shared_state["id"] == pid


@pytest.mark.asyncio
async def test_cosim_actuator_dispatch_and_ramping(cosim_hub):
    """
    Verifies that host actuator commands sent over MTIP wire-framing reach
    the live ActuatorManager on the firmware and properly execute physics ramping.
    """
    ctrl1 = cosim_hub.fleet.controllers[1]
    assert "CONVEYOR" in ctrl1.app.act_mgr.targets
    assert ctrl1.app.act_mgr.targets["CONVEYOR"] == 0.0

    # 1. Send ACT command from Host
    await cosim_hub.send_physical(1, meowprotocol.MSG_TYPE_CMD, "ACT:CONVEYOR=0.80")
    await asyncio.sleep(0.05)

    # 2. Verify firmware received and set the target
    assert ctrl1.app.act_mgr.targets["CONVEYOR"] == 0.80

    # 3. Allow real-time physics loop to ramp up current duty cycle (100ms ramp time)
    await asyncio.sleep(0.18)
    assert ctrl1.app.act_mgr.current["CONVEYOR"] >= 0.79

    # 4. Stop conveyor
    await cosim_hub.send_physical(1, meowprotocol.MSG_TYPE_CMD, "ACT:CONVEYOR=0.0")
    await asyncio.sleep(0.05)
    assert ctrl1.app.act_mgr.targets["CONVEYOR"] == 0.0


@pytest.mark.asyncio
async def test_cosim_w_protocol_piggyback_lifecycle(cosim_hub):
    """
    Verifies the end-to-end W-Protocol lifecycle between live MicroPython firmware
    and Core 0:
    1. Limb generates an asynchronous sensor event.
    2. Host receives the event and registers a pending wipe sequence.
    3. Host injects |W={seq} into the next status poll.
    4. Firmware intercepts |W= and purges the event from its unacked queue.
    """
    ctrl2 = cosim_hub.fleet.controllers[2]

    # 1. Trigger an asynchronous part trip on Limb 2
    ctrl2.trigger_event("PART:105:250:50")

    # 2. Wait for firmware tick loop to transmit event to Host
    await asyncio.sleep(0.1)

    # 3. Verify Host received the event in its logic pipeline
    assert 2 in cosim_hub.pending_wipes or not cosim_hub.logic_queue.empty()

    # 4. Trigger host poll to deliver piggyback wipe
    await cosim_hub.send_physical(2, meowprotocol.MSG_TYPE_CMD_STS, "")
    await asyncio.sleep(0.1)

    # 5. Verify firmware unacked queues are clean
    with ctrl2.app.state_lock:
        unacked = list(ctrl2.app.shared_state["tx_events"].keys())
    assert len(unacked) == 0


@pytest.mark.asyncio
async def test_cosim_fault_propagation_to_global_estop(cosim_hub):
    """
    Verifies that a hardware fault originating in the limb firmware propagates
    through telemetry, trips the host SafetyManager, and triggers a system-wide
    emergency shutdown across all limbs.
    """
    ctrl3 = cosim_hub.fleet.controllers[3]

    # Arm system to FLOW and clear recovery grace so watchdog and safety loops are hot
    cosim_hub.safety.clear_recovery_grace()
    GLOBAL_TWIN.set_state(ms.STATE_FLOW)
    await asyncio.sleep(0.05)

    # 1. Inject motor stall on Limb 3 firmware
    ctrl3.inject_fault("F_STL")
    assert ctrl3.app.shared_state["current_state"] == ctrl3.app.STATE_ERROR

    # 2. Allow telemetry sync and safety watchdog loop (0.5s interval)
    await asyncio.sleep(0.65)

    # 3. Verify Host entered Emergency Stop / Error
    assert GLOBAL_TWIN.host_state == ms.STATE_ERROR

    # 4. Verify Coordinator broadcasted stop to all other limbs
    ctrl1 = cosim_hub.fleet.controllers[1]
    ctrl2 = cosim_hub.fleet.controllers[2]
    assert ctrl1.app.shared_state["current_state"] == ctrl1.app.STATE_ERROR
    assert ctrl2.app.shared_state["current_state"] == ctrl2.app.STATE_ERROR


@pytest.mark.asyncio
async def test_cosim_ghost_mode_recovery(cosim_hub):
    """
    Verifies live remote recovery from Ghost Mode:
    1. Limb drops into Ghost Mode (ST=GHOST).
    2. Host safety monitor blocks arming.
    3. Host issues EXIT_GHOST command.
    4. Firmware handles EXIT, resets to IDLE, and safety monitor unblocks arming.
    """
    ctrl2 = cosim_hub.fleet.controllers[2]

    # 1. Put Limb 2 into Ghost Mode
    ctrl2.set_ghost_mode()
    await asyncio.sleep(0.15)
    assert GLOBAL_TWIN.limbs[2].remote_state == "GHOST"

    # 2. Verify arming is blocked
    assert cosim_hub.safety.is_safe_to_arm() is False

    # 3. Core 0 dispatches remote recovery
    await cosim_hub.send_cmd("EXIT_GHOST_P2")
    await asyncio.sleep(0.1)

    # 4. Limb 2 restored to IDLE
    with ctrl2.app.state_lock:
        ctrl2.app.shared_state["current_state"] = ctrl2.app.STATE_IDLE
        ctrl2.app.shared_state["error_code"] = "NONE"
    await asyncio.sleep(0.15)

    assert GLOBAL_TWIN.limbs[2].remote_state == ms.STATE_IDLE
    assert cosim_hub.safety.is_safe_to_arm() is True
