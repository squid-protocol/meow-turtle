"""
Tests for W-Protocol Persistent Wipe Registry and multi-pass status synchronization.
"""

import asyncio
import pytest
import lib.meowprotocol as meowprotocol

class TestWProtocol:

    async def test_sighting_and_wipe_registry(self, hub):
        """
        Verifies persistent events exceeding single-packet quota (5 IDs)
        are tracked and wiped across multiple status packets.
        """
        # Clear registries for clean test
        hub.pending_wipes[2].clear()
        hub.logic.sighted_ids[2].clear()

        # Step 1: Sighting 6 persistent events (501 to 506)
        event_seqs = [501, 502, 503, 504, 505, 506]
        for s in event_seqs:
            await hub.logic.handle_hardware_event({
                "source": 2, "mtype": meowprotocol.MSG_TYPE_EVT, "seq": s,
                "payload": f"EVENT_DATA_{s}"
            })

        assert len(hub.pending_wipes[2]) == 6

        # Step 2: First Wipe Pass
        # Pico reports 501-505 wiped; 506 still un-acked in status
        await hub.logic.handle_hardware_event({
            "source": 2, "mtype": meowprotocol.MSG_TYPE_STS, "seq": 999,
            "payload": "ST=FLOW,UA=506"
        })

        assert 501 not in hub.pending_wipes[2]
        assert 505 not in hub.pending_wipes[2]
        assert 506 in hub.pending_wipes[2]
        assert len(hub.pending_wipes[2]) == 1

        # Step 3: Second Wipe Pass
        # Pico reports UA is now completely empty
        await hub.logic.handle_hardware_event({
            "source": 2, "mtype": meowprotocol.MSG_TYPE_STS, "seq": 1000,
            "payload": "ST=FLOW,UA="
        })

        assert len(hub.pending_wipes[2]) == 0
