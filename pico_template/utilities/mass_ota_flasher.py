import serial
import time
import struct
import binascii
import hashlib
import math
import os
import sys
import argparse

# --- CONFIGURATION ---
MY_ID = 5                  # RP5 (Brain)
BAUD_RATE = 115200
CHUNK_SIZE = 64            # 64 Bytes (Safe for RP2040 UART FIFO)
MAX_RETRIES = 5

# --- TARGET LIST ---
TARGETS = {
    1: { "port": "/dev/ttyAMA0", "name": "Distributor" },
    2: { "port": "/dev/ttyAMA2", "name": "Sensor Array" },
    3: { "port": "/dev/ttyAMA3", "name": "Motor Controller" }
}

# --- PAYLOAD MODE ---
# Set True to send [ID][HASH]. Set False to send [ID][CHUNKS][HASH].
# Default True because current boot.py/app.py parsers do not support chunks in payload.
USE_LEGACY_PAYLOAD = True 

# --- FILE ID MAP ---
FILE_ID_MAP = {
    "config.json":              0x01,
    "app.py":                   0x02,
    "boot.py":                  0x05,
    "lib/meowprotocol.py":      0x03,
    "lib/tsl2591.py":           0x04,
    "lib/actuators.py":         0x06,
    "lib/sensors.py":           0x07,
    "lib/diagnostics.py":       0x08,
    "lib/tester.py":            0x09,
    "lib/bldc_driver.py":       0x0A,
    "lib/logging.py":           0x0B,
    "lib/mpu6050.py":           0x0C,
    "lib/ota.py":               0x0D,
    "lib/pio_programs.py":      0x0E,
    "lib/vibration_driver.py":  0x0F, 
    "lives.txt":                0x10, 
    "boot_attempts.txt":        0x11
}

# --- PROTOCOL CONSTANTS ---
MSG_TYPE_ACK       = 0x20
MSG_TYPE_NAK       = 0x30
MSG_TYPE_OTA_START = 0x50
MSG_TYPE_OTA_DATA  = 0x51
MSG_TYPE_OTA_END   = 0x52

def crc16_ccitt(data_bytes):
    crc = 0xFFFF
    for byte in data_bytes:
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc = (crc << 1)
            crc &= 0xFFFF
    return crc

def build_packet(target, source, seq, mtype, payload):
    """
    Builds Standard MTIP v5.5 Packet.
    Format: >BBHB (Big Endian)
    """
    if isinstance(payload, str): payload = payload.encode('utf-8')
    
    # Header: Target, Source, Seq(2), Type
    header = struct.pack(">BBHB", target, source, seq, mtype)
    full = header + payload
    
    hex_body = binascii.hexlify(full).upper()
    crc_val = crc16_ccitt(hex_body)
    
    # REMOVED SYNC_BYTE '?' to prevent Zombie Mode CRC failures on Pico
    return f"<{hex_body.decode()}:{crc_val:04X}>\n".encode()

def parse_packet(line):
    try:
        clean = line.strip(b'\x3F').strip().decode(errors='ignore').strip('<>')
        if ':' not in clean: return None
        hex_body, crc_str = clean.rsplit(':', 1)
        
        # Validate CRC
        if crc16_ccitt(hex_body.encode()) != int(crc_str, 16): return "CRC_FAIL"
        
        binary = binascii.unhexlify(hex_body)
        
        # Unpack Header >BBHB (Standard Big Endian)
        tgt, src, seq, mtype = struct.unpack(">BBHB", binary[:5])
        payload = binary[5:]
        
        return (tgt, src, seq, mtype, payload)
    except: return None

def wait_for_ack(ser, expected_seq, timeout=2.0):
    start = time.time()
    while (time.time() - start) < timeout:
        if ser.in_waiting:
            line = ser.readline()
            if b'<' in line:
                res = parse_packet(line)
                if isinstance(res, tuple):
                    tgt, src, seq, mtype, pay = res
                    if seq == expected_seq:
                        if mtype == MSG_TYPE_ACK: return True, pay.decode(errors='ignore')
                        elif mtype == MSG_TYPE_NAK: return False, f"NAK: {pay.decode(errors='ignore')}"
        time.sleep(0.005)
    return False, "TIMEOUT"

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=30, fill='█'):
    """
    Call in a loop to create terminal progress bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

def flash_file(target_id, file_path, port):
    # 1. Resolve File Details (Smart Map Lookup)
    filename = os.path.basename(file_path)
    file_id = filename # Default to string name
    
    # Try exact match
    if filename in FILE_ID_MAP:
        file_id = FILE_ID_MAP[filename]
    else:
        # Try finding 'lib/filename' in map
        for key, val in FILE_ID_MAP.items():
            if key.endswith(f"/{filename}"):
                file_id = val
                break
    
    try:
        with open(file_path, "rb") as f: file_data = f.read()
    except Exception as e:
        print(f"Read Error: {e}"); return

    # 2. Init Serial
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        print(f"Serial Error: {e}"); return

    file_hash = hashlib.sha256(file_data).hexdigest()
    total_chunks = math.ceil(len(file_data) / CHUNK_SIZE)
    seq = 0

    print(f"Target: {TARGETS[target_id]['name']} (ID {target_id}) | File: {filename} ({len(file_data)} bytes)")
    
    # 3. START SESSION
    sys.stdout.write(">> Initializing... ")
    sys.stdout.flush()
    
    if isinstance(file_id, str):
        # Dynamic Name: [FF][NameLen][Name][Hash] 
        name_bytes = file_id.encode('utf-8')
        payload = struct.pack(">BB", 0xFF, len(name_bytes)) + name_bytes + file_hash.encode()
    else:
        # Legacy ID Mode
        if USE_LEGACY_PAYLOAD:
            payload = struct.pack("B", file_id) + file_hash.encode()
        else:
            payload = struct.pack(">BH", file_id, total_chunks) + file_hash.encode()

    pkt = build_packet(target_id, MY_ID, seq, MSG_TYPE_OTA_START, payload)
    
    if not _send_reliable(ser, pkt, seq, "START", verbose=False):
        print("\n[ERROR] Target did not respond to handshake. Aborting.")
        return

    print("OK") # Handshake done
    seq = (seq + 1) % 65536

    # 4. UPLOAD DATA
    # print(f"[2/3] Uploading...")
    for i in range(total_chunks):
        chunk = file_data[i*CHUNK_SIZE : (i+1)*CHUNK_SIZE]
        pkt = build_packet(target_id, MY_ID, seq, MSG_TYPE_OTA_DATA, chunk)
        
        if not _send_reliable(ser, pkt, seq, f"Chunk {i+1}", verbose=False):
            print(f"\n[ERROR] Upload Failed at Chunk {i+1}/{total_chunks}")
            return
        
        # Update Progress Bar
        print_progress_bar(i + 1, total_chunks, prefix='>> Uploading:', suffix='Complete', length=40)
        
        seq = (seq + 1) % 65536

    # 5. COMMIT
    sys.stdout.write(">> Committing...   ")
    sys.stdout.flush()
    pkt = build_packet(target_id, MY_ID, seq, MSG_TYPE_OTA_END, b"")
    
    # We expect NAK: TRUNCATED or similar if reboot is fast, or ACK if slow.
    # We accept either as success, or a timeout as "likely rebooted".
    success = _send_reliable(ser, pkt, seq, "COMMIT", timeout=5.0, verbose=False)
    
    if success:
        print("DONE (Verified)")
    else:
        print("DONE (Implicit - No final ACK)")

    ser.close()

def _send_reliable(ser, pkt, seq, label="TX", timeout=2.0, verbose=True):
    for attempt in range(MAX_RETRIES):
        ser.write(pkt)
        success, msg = wait_for_ack(ser, seq, timeout)
        
        if success: 
            return True
            
        # If verbose is False (like during chunks), only print on error/retry
        # We handle retry output differently to keep progress bar clean?
        # Actually, for chunks, we just retry silently unless it fails max times.
        if verbose:
            sys.stdout.write(f"\r{label} Retry {attempt+1}/{MAX_RETRIES} ({msg})   ")
            sys.stdout.flush()
            
    if verbose: print("")
    return False

def wizard():
    print("\n=== MASS FLASHER OTA v2.0 (Clean Mode) ===")
    
    # 1. Target Selection
    print("\nAvailable Targets:")
    for tid, info in TARGETS.items():
        print(f"  [{tid}] {info['name']}")
    print("  [A] ALL Targets")
        
    selected_targets = []
    while True:
        val = input("\nSelect Target IDs (e.g. 1, 2 or A): ").strip().upper()
        if val in ['A', 'ALL']:
            selected_targets = list(TARGETS.keys())
            break
        
        try:
            parts = [int(x.strip()) for x in val.split(',')]
            valid = True
            for t in parts:
                if t not in TARGETS:
                    print(f"Invalid ID: {t}")
                    valid = False
            if valid and parts:
                selected_targets = parts
                break
        except ValueError:
            pass
        print("Invalid input. Try '1,3' or 'A'.")
    
    print(f"Targets Selected: {selected_targets}")

    # 2. File Selection
    while True:
        path = input("Enter file path (e.g., lib/ota.py): ").strip()
        if os.path.exists(path): break
        print("File not found.")

    # 3. Execution Loop
    for tid in selected_targets:
        print(f"\n{'-'*60}")
        flash_file(tid, path, TARGETS[tid]['port'])
        time.sleep(1.0) # Allow bus to settle between targets
    
    print(f"\n{'-'*60}")
    print("Batch Job Complete.\n")

if __name__ == "__main__":
    wizard()