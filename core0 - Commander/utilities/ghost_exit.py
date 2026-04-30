# rp5_ping_v3.py (Updated for Spec 4.3 - 2-Byte Seq & Clean Framing)
# RUN ON: Raspberry Pi 5
# PURPOSE: Simple diagnostic tool to send single packets and read responses.

"""
MTIP v5 Diagnostic Utility (Ghost Exit).

This module provides a command-line interface for manual hardware diagnostics 
over serial connections. It implements the Spec 4.3 protocol framing, 
including 16-bit sequence IDs and CRC-16-CCITT validation.

Primary Functions:
- Status polling of downstream Picos.
- Remote hardware reset commands.
- "Ghost Mode" termination (Exit Command).
"""

import serial
import time
import struct
import binascii

# --- CONFIGURATION ---
# Default to Pico 1 (Loader/Distributor) on ttyAMA0
SERIAL_PORT = '/dev/ttyAMA2'
BAUD_RATE = 115200
MY_ID = 0      # Main Brain ID
TARGET_ID = 2  # Target Pico ID

# --- PROTOCOL CONSTANTS ---
MSG_TYPE_CMD     = 0x10
MSG_TYPE_CMD_STS = 0x11
MSG_TYPE_CMD_RST = 0x14

# NOTE: Do NOT use SYNC_BYTE (b'\x3F') prefix. 
# Sending '?' triggers Zombie Mode in newer firmware, potentially causing 
# parser misalignment and CRC failures if the line is actually clean.

def crc16_ccitt(data_bytes):
    """
    Calculates the CRC-16-CCITT checksum for a given byte sequence.
    
    Uses Polynomial 0x1021 with an initial value of 0xFFFF. This is the 
    standard integrity check used for all MTIP v5 packet bodies.

    Args:
        data_bytes (bytes): The data to verify, typically the ASCII hex string 
                            of the packet body.

    Returns:
        int: The 16-bit CRC value.
    """
    crc = 0xFFFF
    for byte in data_bytes:
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ 0x1021
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    return crc

def build_packet(target_id, source_id, seq_id, msg_type, payload=b""):
    """
    Constructs an MTIP v5 packet according to the Spec 4.3 standard.
    
    The packet structure is: <HEX_BODY:CRC> followed by a newline.
    The binary header is packed using Big Endian: [Target][Source][SeqH][SeqL][Type].
    The body (header + payload) is converted to uppercase hex before CRC calculation.

    Args:
        target_id (int): ID of the destination device.
        source_id (int): ID of the sending device (this host).
        seq_id (int): 16-bit sequence identifier for packet tracking.
        msg_type (int): Protocol message type (e.g., CMD, STATUS).
        payload (bytes|str): Optional data to include in the packet.

    Returns:
        bytes: The fully framed ASCII packet ready for serial transmission.
    """
    if isinstance(payload, str): payload = payload.encode('utf-8')
    
    # UPDATED: Spec 4.3 - 2 Byte Sequence ID (Big Endian standard)
    # Structure: >BBHB (Target, Source, Seq(2), Type)
    header = struct.pack(">BBHB", target_id, source_id, seq_id, msg_type)
    full_binary = header + payload
    
    # Convert binary body to Uppercase Hex String
    hex_body = binascii.hexlify(full_binary).upper()
    
    # Calculate CRC on the HEX STRING
    crc_val = crc16_ccitt(hex_body)
    
    # Format: <BODY:CRC>\n
    packet = f"<{hex_body.decode('ascii')}:{crc_val:04X}>\n".encode('ascii')
    return packet 

def parse_response(raw_bytes):
    """
    Parses and validates a raw serial response line.
    
    Extracts content between protocol markers '<' and '>', validates the 
    CRC-16 checksum, and unpacks the Spec 4.3 binary header.

    Args:
        raw_bytes (bytes): The raw data received from the serial buffer.

    Returns:
        tuple|None: (Target, Source, Seq, Type, Payload) if successful.
        tuple: ("NAK", ErrorCode) if validation fails.
        None: If no packet markers are found.
    """
    try:
        # Look for start/end markers
        txt = raw_bytes.decode('ascii', errors='ignore').strip()
        if '<' not in txt or '>' not in txt: return None
        
        # Extract content between < and >
        # Handle potential garbage before/after markers
        start = txt.find('<')
        end = txt.find('>')
        content = txt[start+1 : end]
        
        if ':' not in content: return ("NAK", "FMT")
        
        hex_body, crc_str = content.rsplit(':', 1)
        
        # Validate CRC
        if crc16_ccitt(hex_body.encode()) != int(crc_str, 16):
            return ("NAK", "CRC")
            
        # Decode Body
        binary = binascii.unhexlify(hex_body)
        
        # UPDATED: Spec 4.3 - Unpack 5 byte header (Seq is now 2 bytes)
        if len(binary) < 5: return ("NAK", "LEN")
        
        tgt, src, seq, mtype = struct.unpack(">BBHB", binary[:5])
        payload = binary[5:]
        
        return (tgt, src, seq, mtype, payload)
    except Exception as e:
        return ("NAK", f"EXC_{e}")

# --- MAIN ---
def main():
    """
    Main execution loop for the diagnostic tool.
    
    Provides an interactive CLI to send packets, manage sequence counters, 
    and display real-time decoded serial telemetry.
    """
    print(f"--- OPENING {SERIAL_PORT} (MTIP v5 Clean Mode) ---")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    except Exception as e:
        print(f"ERROR: {e}")
        return

    seq_counter = 0

    try:
        while True:
            print("\nSelect Query to Send:")
            print("  [s] Status Request (CMD_STS 0x11)")
            print("  [r] Reset Command  (CMD 0x14 - Hard Reset)")
            print("  [e] Exit Ghost     (CMD 0x10 payload='EXIT')")
            print("  [q] Quit Script")
            
            choice = input("Enter selection: ").strip().lower()
            
            msg_type = 0
            payload = b""
            
            if choice == 'q':
                break
            elif choice == 's':
                msg_type = MSG_TYPE_CMD_STS
                payload = b""
            elif choice == 'r':
                msg_type = MSG_TYPE_CMD_RST
                payload = b""
            elif choice == 'e':
                msg_type = MSG_TYPE_CMD
                payload = b"EXIT"
            else:
                print("Invalid selection.")
                continue

            # Clear input buffer before sending to avoid reading old junk
            ser.reset_input_buffer()

            # Send Packet
            pkt = build_packet(TARGET_ID, MY_ID, seq_counter, msg_type, payload)
            ser.write(pkt)
            print(f"[TX] {pkt.strip().decode()}")
            
            # UPDATED: Spec 4.3 - 16-bit Sequence Counter
            seq_counter = (seq_counter + 1) % 65536

            # Listen for Reply
            print("Waiting for reply...")
            start = time.time()
            buffer = b""
            got_reply = False
            
            while (time.time() - start) < 1.0: # 1s timeout
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting)
                    buffer += chunk
                    
                    # Check if we have a full packet line
                    if b'\n' in buffer or b'>' in buffer:
                        # Try parsing
                        res = parse_response(buffer)
                        if res and res[0] != "NAK":
                            tgt, src, seq, mtype, pay = res
                            # Try to decode payload as string if possible
                            try:
                                pay_str = pay.decode('utf-8', 'ignore')
                            except:
                                pay_str = pay.hex()
                                
                            print(f"     [RX DECODED] SRC={src} SEQ={seq} TYPE={hex(mtype)} | PAYLOAD={pay_str}")
                            got_reply = True
                            break
                        elif res and res[0] == "NAK":
                             # If we found markers but CRC failed
                             print(f"     [RX INVALID] {res}")
                             # Don't break, keep listening in case real packet is coming
                time.sleep(0.01)
            
            if not got_reply:
                print(f"     [TIMEOUT] No valid reply received. Raw buffer: {buffer}")

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()