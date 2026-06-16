# utilities/vibration_sweeper.py - Ninelives Resonance Mapper

import serial
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from lib import meowprotocol

# --- SWEEP CONFIGURATION ---
NODE_ID = 1
PORT = "/dev/ttyAMA0"
BAUD = 115200

ACTUATOR = "SVIB"  # Change to TVIB for the other motor
DUTY_CYCLE = 0.2  # 20% Power
START_HZ = 5000
END_HZ = 15000
STEP_HZ = 500  # Drop this to 50 for the Fine Sweep


def send_and_wait(
    ser, parser, m_type, payload, expect_type=meowprotocol.MSG_TYPE_ACK, timeout=0.5
):
    """Sends a packet and waits for a specific response type."""
    ser.read(max(1, ser.in_waiting))  # Clear buffer
    pkt = meowprotocol.build_packet(NODE_ID, 0, 1, m_type, payload)
    ser.write(pkt)

    t_start = time.time()
    while (time.time() - t_start) < timeout:
        chunk = ser.read(max(1, ser.in_waiting))
        if chunk:
            parsed = parser.parse(chunk)
            for p in parsed:
                if p[1] == NODE_ID and p[3] == expect_type:
                    return p[4].decode(errors="ignore")  # Return the payload payload
    return None


def run_sweep():
    print("\n" + "=" * 50)
    print(f" NINELIVES VIBRATION SWEEPER: {ACTUATOR} @ {DUTY_CYCLE} Duty")
    print("=" * 50)

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        parser = meowprotocol.PacketParser(0)
    except Exception as e:
        print(f"[!] Could not open port {PORT}: {e}")
        return

    print(f"[*] Sweeping from {START_HZ}Hz to {END_HZ}Hz (Steps of {STEP_HZ}Hz)\n")
    print(f"| {'Freq (Hz)':<10} | {'Status':<10} | {'Sensor Telemetry String':<40} |")
    print("-" * 70)

    for freq in range(START_HZ, END_HZ + 1, STEP_HZ):
        sys.stdout.write(f"| {freq:<10} | ")
        sys.stdout.flush()

        # 1. Update the Frequency in RAM (0x18 = MSG_TYPE_SET_CFG)
        cfg_cmd = f"CFG:ACT:{ACTUATOR}:freq={freq}"
        ack = send_and_wait(ser, parser, 0x18, cfg_cmd)
        if not ack:
            print(f"{'CFG FAIL':<10} | {'---':<40} |")
            continue

        # 2. Turn Motor ON at Target Duty Cycle (0x10 = MSG_TYPE_CMD)
        on_cmd = f"ACT:{ACTUATOR}={DUTY_CYCLE}"
        send_and_wait(ser, parser, 0x10, on_cmd)

        # 3. Wait for mechanical resonance to build up in the physical frame
        time.sleep(0.8)

        # 4. Query Sensors (0x16 = MSG_TYPE_CMD_SNS)
        # We wait for the 0x46 (MSG_TYPE_SNS) response packet
        sensor_data = send_and_wait(ser, parser, 0x16, "REQ", expect_type=0x46)

        if sensor_data:
            print(f"{'OK':<10} | {sensor_data[:40]:<40} |")
        else:
            print(f"{'SNS TIMEOUT':<10} | {'---':<40} |")

        # 5. Turn Motor OFF and let the frame settle
        off_cmd = f"ACT:{ACTUATOR}=0.0"
        send_and_wait(ser, parser, 0x10, off_cmd)
        time.sleep(0.5)

    ser.close()
    print("-" * 70)
    print("\n[*] Sweep Complete.")


if __name__ == "__main__":
    run_sweep()
