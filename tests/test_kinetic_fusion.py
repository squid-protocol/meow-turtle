"""
Tests for Vision Fusion, Kinetic Queue Marriage, and Gate Unjam Routines.
"""

import asyncio
import time
import pytest
from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms
import lib.meowprotocol as meowprotocol

class TestKineticFusion:

    async def test_breakbeam_before_vision(self, hub):
        """Verifies reconciliation when physical breakbeam arrives before vision."""
        if GLOBAL_TWIN.host_state != ms.STATE_IDLE:
            await hub.send_cmd("RESET")
            await asyncio.sleep(1.2)

        arm_ok = await hub.jobs.run_arming_sequence("BUILD_INVENTORY")
        assert arm_ok is True
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW

        hub.logic.reset_logic(reset_stats=True)

        # 1. Physical Breakbeam from Pico 2
        await hub.logic.handle_hardware_event({
            "source": 2, "mtype": meowprotocol.MSG_TYPE_EVT, "seq": 100,
            "payload": "PART_DETECTED,center_pulse=1500"
        })
        assert len(hub.logic.part_located) == 1

        # 2. Vision classification from Core 1
        await hub.logic.handle_vision_result({"target_bin": 4, "impulse": 0.9})
        await asyncio.sleep(0.1)

        assert hub.logic.stats["parts_sorted"] == 1
        assert len(hub.logic.part_located) == 0

    async def test_vision_before_breakbeam(self, hub):
        """Verifies reconciliation when vision classification arrives before breakbeam."""
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW
        hub.logic.reset_logic(reset_stats=True)

        # 1. Vision classification arrives first
        await hub.logic.handle_vision_result({"target_bin": 7, "impulse": 0.8})
        assert len(hub.logic.part_identified) == 1

        # 2. Breakbeam arrives second
        await hub.logic.handle_hardware_event({
            "source": 2, "mtype": meowprotocol.MSG_TYPE_EVT, "seq": 101,
            "payload": "PART_DETECTED,center_pulse=1850"
        })
        await asyncio.sleep(0.1)

        assert hub.logic.stats["parts_sorted"] == 1
        assert len(hub.logic.part_identified) == 0

    async def test_high_throughput_burst(self, hub):
        """Verifies rapid queue draining for high-throughput 10-part burst."""
        assert GLOBAL_TWIN.host_state == ms.STATE_FLOW
        hub.logic.reset_logic(reset_stats=True)

        for i in range(10):
            await hub.logic.handle_hardware_event({
                "source": 2, "mtype": meowprotocol.MSG_TYPE_EVT, "seq": 200 + i,
                "payload": f"PART_DETECTED,center_pulse={2000 + i * 100}"
            })
            await hub.logic.handle_vision_result({"target_bin": (i % 8) + 1, "impulse": 1.0})

        await asyncio.sleep(0.1)
        assert hub.logic.stats["parts_sorted"] == 10
        assert len(hub.logic.part_located) == 0
        assert len(hub.logic.part_identified) == 0

    async def test_stale_queue_item_eviction(self, hub):
        """Verifies physical/vision queue entries older than 15s are purged with sync error counted."""
        hub.logic.reset_logic(reset_stats=True)

        # Inject an item timestamped 20 seconds ago
        stale_time = time.time() - 20.0
        hub.logic.part_located.append({"pulse": 1000, "ts": stale_time})
        hub.logic.part_identified.append({"target_bin": 2, "impulse": 0.5, "ts": stale_time})

        await hub.logic.reconcile_queues()

        assert len(hub.logic.part_located) == 0
        assert len(hub.logic.part_identified) == 0
        assert hub.logic.stats["vision_sync_errors"] == 2

    async def test_gate_jam_handling(self, hub):
        """Verifies GATE_JAMMED event is processed without crashing."""
        await hub.logic.handle_hardware_event({
            "source": 2, "mtype": meowprotocol.MSG_TYPE_EVT, "seq": 350,
            "payload": "GATE_JAMMED"
        })
        await asyncio.sleep(0.1)
        # Event processed cleanly
        assert True
