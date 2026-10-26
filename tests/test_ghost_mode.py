"""
tests/test_ghost_mode.py - Test Suite for Bootloader & Ghost Mode Subsystem.

Validates:
1. Ghost Mode Wire Formatting & CRC16 calculation.
2. GhostParser greedy ingestion, addressing, and corrupt frame rejection.
3. GhostOTAManager lifecycle (start, write, hash verify, atomic commit, abort).
4. Telemetry Router recognition of ST=GHOST (and legacy S=GHOST).
5. Safety hierarchy blocking arming when a limb reports STATE_GHOST.
6. Coordinator EXIT_GHOST command dispatch.
"""

import os
import sys
import time
import struct
import binascii
import hashlib
import tempfile
import pytest

# Ensure Core 0 and pico_template libraries are discoverable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE0_DIR = os.path.join(BASE_DIR, "core0 - Commander")
PICO_DIR = os.path.join(BASE_DIR, "pico_template")

if CORE0_DIR not in sys.path:
    sys.path.insert(0, CORE0_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms
import lib.meowprotocol as meowprotocol
from lib.telemetry_router import STREAM_ROUTER


# --- Extract Ghost Mode Pure-Python Classes from boot.py ---
def ghost_crc16(data_bytes):
    crc = 0xFFFF
    for byte in data_bytes:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


def ghost_frame_packet(target_id, source_id, seq_id, msg_type, payload_bytes=b""):
    header = struct.pack(">BBHB", target_id, source_id, seq_id, msg_type)
    full_binary = header + payload_bytes
    hex_body = binascii.hexlify(full_binary).upper()
    crc_val = ghost_crc16(hex_body)
    return f"<{hex_body.decode()}:{crc_val:04X}>\n".encode()


class GhostParser:
    def __init__(self, local_id):
        self.buffer = b""
        self.max_buffer_size = 600
        self.local_id = local_id

    def parse_stream(self, chunk):
        if not chunk:
            return None
        self.buffer += chunk
        if len(self.buffer) > self.max_buffer_size:
            self.buffer = b""
            return None

        if b"<" in self.buffer and b">" in self.buffer:
            start = self.buffer.find(b"<")
            end = self.buffer.find(b">", start)
            if end == -1:
                return None

            frame_content = self.buffer[start + 1 : end]
            self.buffer = self.buffer[end + 1 :]
            if b":" not in frame_content:
                return None

            try:
                hex_body, crc_str = frame_content.rsplit(b":", 1)
                if ghost_crc16(hex_body) != int(crc_str, 16):
                    return ("NAK", "CRC")

                bin_dat = binascii.unhexlify(hex_body)
                if len(bin_dat) < 5:
                    return None

                tid, sid, seq, mtype = struct.unpack(">BBHB", bin_dat[:5])
                if tid != self.local_id and tid != 0 and tid != 0xFF:
                    return None

                return (tid, sid, seq, mtype, bin_dat[5:])
            except Exception:
                return ("NAK", "EXC")
        return None


class GhostOTAManager:
    LEGACY_MAP = {
        0x01: "config.json",
        0x02: "app.py",
        0x03: "lib/meowprotocol.py",
        0x04: "lib/tsl2591.py",
        0x05: "boot.py",
        0x06: "lib/actuators.py",
        0x07: "lib/sensors.py",
        0x08: "lib/diagnostics.py",
        0x09: "lib/tester.py",
        0x0A: "lib/bldc_driver.py",
        0x0B: "lib/logging.py",
        0x0C: "lib/mpu6050.py",
        0x0D: "lib/ota.py",
        0x0E: "lib/pio_programs.py",
        0x0F: "lib/vibration_driver.py",
        0x10: "lives.txt",
        0x11: "boot_attempts.txt",
    }

    def __init__(self):
        self.f = None
        self.name = ""
        self.hash = None
        self.exp_hash = ""

    def start(self, target_id, exp_hash):
        if isinstance(target_id, int):
            if target_id in self.LEGACY_MAP:
                self.name = self.LEGACY_MAP[target_id]
            else:
                return False, "BAD_ID"
        else:
            self.name = str(target_id)

        self.exp_hash = exp_hash.lower()
        try:
            if "/" in self.name:
                try:
                    os.mkdir(self.name.rsplit("/", 1)[0])
                except:
                    pass
            self.f = open(self.name + ".new", "wb")
            self.hash = hashlib.sha256()
            return True, "READY"
        except Exception as e:
            return False, f"FS_{e}"

    def write(self, data):
        if not self.f:
            return False, "NO_SESS"
        try:
            self.f.write(data)
            self.hash.update(data)
            return True, "OK"
        except:
            return False, "WR_ERR"

    def commit(self):
        if not self.f:
            return False, "NO_SESS"
        self.f.close()
        self.f = None

        calc = binascii.hexlify(self.hash.digest()).decode()
        if calc != self.exp_hash:
            try:
                os.remove(self.name + ".new")
            except:
                pass
            return False, "HASH_FAIL"

        try:
            if self.name == "app.py":
                try:
                    if "app.py" in os.listdir():
                        try:
                            os.remove("app.py.bak")
                        except:
                            pass
                        os.rename("app.py", "app.py.bak")
                except:
                    pass
            else:
                try:
                    os.remove(self.name)
                except:
                    pass
            os.rename(self.name + ".new", self.name)
            return True, "DONE"
        except Exception as e:
            return False, f"MV_{e}"

    def abort(self):
        if self.f:
            try:
                self.f.close()
            except:
                pass
        try:
            os.remove(self.name + ".new")
        except:
            pass
        return True, "ABORTED"


class TestGhostModeProtocol:
    """Verifies low-level Ghost Mode packet formatting and stream parsing."""

    def test_ghost_crc16_and_framing(self):
        """Validates that ghost_frame_packet matches the standard <HEX:CRC> wire format."""
        pkt = ghost_frame_packet(1, 0, 42, 0x11, b"STATUS_REQ")
        assert pkt.startswith(b"<")
        assert pkt.endswith(b">\n")

        # Decode content
        inner = pkt.strip()[1:-1]
        assert b":" in inner
        hex_body, crc_str = inner.rsplit(b":", 1)
        calc_crc = ghost_crc16(hex_body)
        assert f"{calc_crc:04X}".encode() == crc_str

    def test_ghost_parser_acceptance_and_filtering(self):
        """Verifies GhostParser accepts local, broadcast, and 0xFF, but rejects foreign IDs."""
        parser = GhostParser(local_id=2)

        # 1. Packet addressed directly to local_id (2)
        pkt_direct = ghost_frame_packet(2, 0, 10, 0x10, b"RESET")
        res = parser.parse_stream(pkt_direct)
        assert res is not None
        assert res[0] == 2
        assert res[4] == b"RESET"

        # 2. Broadcast packet (0)
        pkt_bcast = ghost_frame_packet(0, 0, 11, 0x10, b"HALT")
        res = parser.parse_stream(pkt_bcast)
        assert res is not None
        assert res[0] == 0

        # 3. Dynamic flash target (0xFF)
        pkt_ff = ghost_frame_packet(0xFF, 0, 12, 0x10, b"FLASH")
        res = parser.parse_stream(pkt_ff)
        assert res is not None
        assert res[0] == 0xFF

        # 4. Foreign packet addressed to node 3 (should be ignored by node 2)
        pkt_foreign = ghost_frame_packet(3, 0, 13, 0x10, b"IGNORE_ME")
        res = parser.parse_stream(pkt_foreign)
        assert res is None

    def test_ghost_parser_crc_rejection(self):
        """Verifies GhostParser flags CRC corruption with ('NAK', 'CRC')."""
        parser = GhostParser(local_id=1)
        valid_pkt = ghost_frame_packet(1, 0, 5, 0x10, b"TEST")

        # Corrupt one hex byte in the payload
        corrupted_pkt = valid_pkt[:10] + b"A" + valid_pkt[11:]
        res = parser.parse_stream(corrupted_pkt)
        assert res == ("NAK", "CRC")

    def test_ghost_parser_fragmentation(self):
        """Verifies GhostParser correctly handles chunks split across serial reads."""
        parser = GhostParser(local_id=1)
        pkt = ghost_frame_packet(1, 0, 7, 0x20, b"CHUNKED")

        # Split frame in two halves
        half = len(pkt) // 2
        assert parser.parse_stream(pkt[:half]) is None
        res = parser.parse_stream(pkt[half:])
        assert res is not None
        assert res[0] == 1
        assert res[3] == 0x20
        assert res[4] == b"CHUNKED"

    def test_ghost_ota_lifecycle_success(self, tmp_path, monkeypatch):
        """Verifies GhostOTAManager streams chunks, verifies hash, and commits atomically."""
        monkeypatch.chdir(tmp_path)
        ota = GhostOTAManager()

        test_content = b"print('Rescue Payload Online')\n"
        exp_hash = hashlib.sha256(test_content).hexdigest()

        ok, msg = ota.start("test_app.py", exp_hash)
        assert ok is True
        assert msg == "READY"

        ok, msg = ota.write(test_content)
        assert ok is True
        assert msg == "OK"

        ok, msg = ota.commit()
        assert ok is True
        assert msg == "DONE"

        with open(tmp_path / "test_app.py", "rb") as f:
            assert f.read() == test_content

    def test_ghost_ota_hash_mismatch(self, tmp_path, monkeypatch):
        """Verifies GhostOTAManager detects corrupted hashes and deletes staged artifacts."""
        monkeypatch.chdir(tmp_path)
        ota = GhostOTAManager()

        test_content = b"bad corrupted content"
        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        ok, msg = ota.start("bad_app.py", wrong_hash)
        assert ok is True

        ota.write(test_content)
        ok, msg = ota.commit()
        assert ok is False
        assert msg == "HASH_FAIL"
        assert not os.path.exists("bad_app.py")
        assert not os.path.exists("bad_app.py.new")

    def test_ghost_ota_abort(self, tmp_path, monkeypatch):
        """Verifies GhostOTAManager aborts session and cleans staging files."""
        monkeypatch.chdir(tmp_path)
        ota = GhostOTAManager()

        ota.start("abort_target.py", "somehash")
        ota.write(b"partial data")
        assert os.path.exists("abort_target.py.new")

        ok, msg = ota.abort()
        assert ok is True
        assert msg == "ABORTED"
        assert not os.path.exists("abort_target.py.new")


class TestGhostModeHostIntegration:
    """Verifies Core 0 telemetry routing, safety gating, and coordinator commands for Ghost Mode."""

    def test_telemetry_router_recognizes_st_ghost(self, hub):
        """Verifies that an incoming ST=GHOST status payload sets limb.remote_state to GHOST."""
        try:
            payload = b"ST=GHOST,S=GHOST,ERR=NO_APP"
            STREAM_ROUTER.route_packet(source_id=2, msg_type=meowprotocol.MSG_TYPE_STS, payload=payload)

            limb = GLOBAL_TWIN.limbs[2]
            assert limb.remote_state == ms.STATE_GHOST
        finally:
            GLOBAL_TWIN.limbs[2].remote_state = ms.STATE_IDLE

    def test_telemetry_router_legacy_s_ghost_fallback(self, hub):
        """Verifies backward compatibility: if a legacy node reports S=GHOST without ST, host still sets GHOST."""
        try:
            payload = b"S=GHOST,ERR=NO_APP"
            STREAM_ROUTER.route_packet(source_id=1, msg_type=meowprotocol.MSG_TYPE_STS, payload=payload)

            limb = GLOBAL_TWIN.limbs[1]
            assert limb.remote_state == ms.STATE_GHOST
        finally:
            GLOBAL_TWIN.limbs[1].remote_state = ms.STATE_IDLE

    def test_safety_manager_blocks_arming_in_ghost_mode(self, hub):
        """Verifies is_safe_to_arm() blocks transitioning to READY when any limb is in STATE_GHOST."""
        # Ensure clean initial state
        for l in GLOBAL_TWIN.limbs.values():
            l.remote_state = ms.STATE_IDLE
        GLOBAL_TWIN.host_state = ms.STATE_IDLE

        try:
            # Set limb 3 into GHOST mode
            GLOBAL_TWIN.limbs[3].remote_state = ms.STATE_GHOST
            assert hub.safety.is_safe_to_arm() is False

            # Restore limb 3 to IDLE
            GLOBAL_TWIN.limbs[3].remote_state = ms.STATE_IDLE
            assert hub.safety.is_safe_to_arm() is True
        finally:
            for l in GLOBAL_TWIN.limbs.values():
                l.remote_state = ms.STATE_IDLE

    @pytest.mark.asyncio
    async def test_coordinator_exit_ghost_command(self, hub):
        """Verifies coordinator.send_cmd('EXIT_GHOST_P2') dispatches EXIT packet to limb 2."""
        try:
            # Put limb 2 into GHOST mode
            GLOBAL_TWIN.limbs[2].remote_state = ms.STATE_GHOST

            # Execute EXIT_GHOST_P2
            await hub.send_cmd("EXIT_GHOST_P2")

            # Verify recovery grace period was triggered to prevent false watchdog alarms
            assert hub.safety.in_grace_period is True
        finally:
            GLOBAL_TWIN.limbs[2].remote_state = ms.STATE_IDLE
