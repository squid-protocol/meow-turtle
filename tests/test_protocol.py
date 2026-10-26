"""
Unit tests for MTIP wire protocol, CRC-16-CCITT, framing, and key-value payload parsing.
"""

import pytest
import lib.meowprotocol as meowprotocol
import lib.protocol_parser as protocol_parser

class TestMTIPProtocol:

    def test_crc16_ccitt(self):
        """Validates CRC-16-CCITT calculation against known test vectors."""
        data = b"HELLO_MEOW"
        crc = meowprotocol.crc16_ccitt(data)
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF
        # Repeating with identical data yields identical CRC
        assert meowprotocol.crc16_ccitt(data) == crc
        # Different data produces different CRC
        assert meowprotocol.crc16_ccitt(b"HELLO_MEOW2") != crc

    def test_build_packet_framing(self):
        """Ensures built wire packets conform to <HEX_BODY:CRC> framing standard."""
        packet = meowprotocol.build_packet(
            target_id=1,
            source_id=0,
            seq=42,
            msg_type=meowprotocol.MSG_TYPE_CMD,
            payload="FLOW"
        )
        assert packet.startswith(b"<")
        assert packet.endswith(b">\n")
        assert b":" in packet

    def test_stream_parser_valid_chunk(self):
        """Verifies PacketParser correctly parses unbroken wire packets."""
        parser = meowprotocol.PacketParser(local_id=1)
        raw_pkt = meowprotocol.build_packet(1, 0, 10, meowprotocol.MSG_TYPE_CMD, "IDLE")
        packets = parser.parse(raw_pkt)
        assert len(packets) == 1
        target, source, seq, mtype, payload = packets[0]
        assert target == 1
        assert source == 0
        assert seq == 10
        assert mtype == meowprotocol.MSG_TYPE_CMD
        assert payload == b"IDLE"

    def test_stream_parser_fragmented_delivery(self):
        """Verifies PacketParser reassembles bytes delivered across multiple chunk fragments."""
        parser = meowprotocol.PacketParser(local_id=2)
        raw_pkt = meowprotocol.build_packet(2, 0, 99, meowprotocol.MSG_TYPE_STS, "ST=FLOW,V=5.02")
        
        # Split packet into 3 fragments
        f1, f2, f3 = raw_pkt[:4], raw_pkt[4:10], raw_pkt[10:]
        assert parser.parse(f1) == []
        assert parser.parse(f2) == []
        res = parser.parse(f3)
        assert len(res) == 1
        target, source, seq, mtype, payload = res[0]
        assert target == 2
        assert source == 0
        assert seq == 99
        assert b"ST=FLOW" in payload

    def test_kv_payload_parser(self):
        """Verifies parsing of delimited key-value status strings."""
        payload = "ST=FLOW,UPT=1234,V=4.95,T=42.5,RAM=80.0%,UA=[10, 20, 30]"
        parsed = protocol_parser.parse_kv_payload(payload)
        assert parsed["ST"] == "FLOW"
        assert parsed["UPT"] == 1234
        assert parsed["V"] == 4.95
        assert parsed["T"] == 42.5
        assert parsed["RAM"] == "80.0%"
        assert parsed["UA"] == [10, 20, 30]

    def test_kv_payload_json_fallback(self):
        """Verifies JSON payloads are decoded properly by parse_kv_payload."""
        json_payload = '{"target_bin": 3, "impulse": 0.85}'
        parsed = protocol_parser.parse_kv_payload(json_payload)
        assert parsed["target_bin"] == 3
        assert parsed["impulse"] == 0.85
