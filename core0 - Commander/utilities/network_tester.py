# utilities/network_tester.py - Ninelives Network Sweeper (Paranoid RAM Edition)

import serial
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from lib import meowprotocol

FLEET = {1: "/dev/ttyAMA0", 2: "/dev/ttyAMA2", 3: "/dev/ttyAMA3"}
TEST_BAUDS = [57600, 115200, 230400, 250000, 460800, 500000]
SAFE_BAUD = 115200
PACKETS_PER_TEST = 200

# Hardcoded for safety in case lib/meowprotocol.py isn't fully synced on the RP5 yet
MSG_TYPE_CMD_BAUD = 0x1B


def ping_node(node_id, baud_rate, timeout=1.0):
    """Sends a single ping at a specific baud rate and waits for an ACK or STS."""
    port = FLEET.get(node_id)
    try:
        ser = serial.Serial(port, baud_rate, timeout=0.1)
        ser.read(max(1, ser.in_waiting))  # Clear garbage

        parser = meowprotocol.PacketParser(0)
        pkt = meowprotocol.build_packet(
            node_id, 0, 1, meowprotocol.MSG_TYPE_CMD, "PING"
        )

        ser.write(pkt)
        t_start = time.time()

        while (time.time() - t_start) < timeout:
            chunk = ser.read(max(1, ser.in_waiting))
            if chunk:
                parsed = parser.parse(chunk)
                for p in parsed:
                    if p[1] == node_id:
                        ser.close()
                        return True
        ser.close()
        return False
    except Exception:
        return False


def hunt_for_node(node_id):
    """Scans bauds to find the node, with transparent logging."""
    print(f"\n[STAGE 1] PRE-FLIGHT HUNT: Locating Node {node_id}")

    sys.stdout.write(f"  [?] Pinging SAFE_BAUD ({SAFE_BAUD})... ")
    sys.stdout.flush()
    if ping_node(node_id, SAFE_BAUD):
        print("[✓] ALIVE")
        return SAFE_BAUD
    else:
        print("[✗] DEAF")

    for b in TEST_BAUDS:
        if b == SAFE_BAUD:
            continue
        sys.stdout.write(f"  [?] Pinging {b}... ")
        sys.stdout.flush()
        if ping_node(node_id, b):
            print("[✓] ALIVE")
            return b
        else:
            print("[✗] DEAF")

    return None


def shift_baud_ram(node_id, current_baud, target_baud):
    """Sends the 0x1B command to shift the hardware UART instantly in RAM."""
    print(f"\n[STAGE 2] RAM SHIFT COMMAND: {current_baud} -> {target_baud} bps")
    port = FLEET.get(node_id)
    try:
        ser = serial.Serial(port, current_baud, timeout=0.5)
        ser.read(max(1, ser.in_waiting))

        # Payload is just the raw string of the new baud rate
        pkt = meowprotocol.build_packet(
            node_id, 0, 255, MSG_TYPE_CMD_BAUD, str(target_baud)
        )
        ser.write(pkt)

        # Give the wire a moment to flush before we close the Pi's port
        time.sleep(0.1)
        ser.close()

        print("  [i] Shift packet transmitted.")
        return True
    except Exception as e:
        print(f"  [✗] Port Error during shift: {e}")
        return False


def test_link(node_id, baud_rate):
    """Floods the link to test physical wire integrity."""
    print(
        f"\n[STAGE 4] STRESS TEST: Blasting {PACKETS_PER_TEST} packets at {baud_rate} bps"
    )
    port = FLEET.get(node_id)
    try:
        ser = serial.Serial(port, baud_rate, timeout=0.1)
    except Exception as e:
        print(f"  [✗] Could not open port: {e}")
        return None

    parser = meowprotocol.PacketParser(0)
    ser.read(max(1, ser.in_waiting))

    received = 0
    latencies = []

    sys.stdout.write("  [>] ")
    for seq in range(1, PACKETS_PER_TEST + 1):
        pkt = meowprotocol.build_packet(
            node_id, 0, seq % 255, meowprotocol.MSG_TYPE_CMD, "PING"
        )
        t_start = time.time()
        ser.write(pkt)

        response_found = False
        timeout_start = time.time()

        while (time.time() - timeout_start) < 0.3:
            chunk = ser.read(max(1, ser.in_waiting))
            if chunk:
                parsed = parser.parse(chunk)
                for p in parsed:
                    if p[1] == node_id and p[3] == meowprotocol.MSG_TYPE_ACK:
                        latencies.append((time.time() - t_start) * 1000)
                        received += 1
                        response_found = True
                        break
            if response_found:
                break

        if response_found:
            sys.stdout.write("=")
        else:
            sys.stdout.write("x")
        sys.stdout.flush()

    sys.stdout.write("\n")
    ser.close()

    success_rate = (received / PACKETS_PER_TEST) * 100
    print(
        f"  [i] Test Complete. Hit Rate: {success_rate}%, CRC Errors: {parser.crc_error_count}"
    )

    return {
        "baud": baud_rate,
        "success": success_rate,
        "avg_lat": sum(latencies) / len(latencies) if latencies else 0,
        "max_lat": max(latencies) if latencies else 0,
        "crc": parser.crc_error_count,
    }


def rubber_band_recovery(node_id):
    """Waits for the Pico's Network Watchdog to crash and reboot the node back to SAFE_BAUD."""
    print("\n[RESCUE] RUBBER BAND RECOVERY INITIATED")
    print("  [!!!] Node is deaf or lost. Cannot send a RAM shift command.")
    print(
        "  [i] Waiting 65 seconds for the Pico's Autonomous Network Watchdog to bite..."
    )

    for i in range(65, 0, -1):
        sys.stdout.write(f"\r  [-] Watchdog starvation countdown: {i}s   ")
        sys.stdout.flush()
        time.sleep(1)

    print("\n  [i] Watchdog should have triggered a hardware reboot.")
    sys.stdout.write(f"  [?] Verifying snap-back to {SAFE_BAUD}... ")
    sys.stdout.flush()

    if ping_node(node_id, SAFE_BAUD, timeout=2.0):
        print("[✓] ALIVE")
        print("  [✓] Rubber Band successful. Node is back at baseline.")
        return True
    else:
        print("[✗] DEAF")
        print("  [!!!] FATAL: Node did not recover. Check physical power.")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print(" NINELIVES NETWORK SWEEPER (PARANOID RAM EDITION)")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage: python network_tester.py <node_id>")
        sys.exit(1)

    node = int(sys.argv[1])
    results = []

    # [STAGE 1] INITIAL HUNT
    current_baud = hunt_for_node(node)
    if current_baud is None:
        print(f"\n[!!!] Node {node} is completely unresponsive. Aborting.")
        sys.exit(1)

    if current_baud != SAFE_BAUD:
        print(
            f"\n[i] Node is stranded at {current_baud}. Shifting to baseline {SAFE_BAUD} in RAM."
        )
        shift_baud_ram(node, current_baud, SAFE_BAUD)
        if not ping_node(node, SAFE_BAUD):
            rubber_band_recovery(node)

    for target_baud in TEST_BAUDS:
        print("\n" + "-" * 50)
        print(f" TARGETING: {target_baud} bps")
        print("-" * 50)

        if target_baud != SAFE_BAUD:
            # [STAGE 2] RAM SHIFT
            shift_baud_ram(node, SAFE_BAUD, target_baud)

            # [STAGE 3] PARANOID VERIFICATION
            print("\n[STAGE 3] VERIFICATION: The Double-Tap")

            # Tap 1: Ensure it actually left the old frequency
            sys.stdout.write(f"  [?] Pinging OLD baud ({SAFE_BAUD})... ")
            sys.stdout.flush()
            if ping_node(node, SAFE_BAUD, timeout=0.5):
                print("[!] ALIVE")
                print(
                    "  [✗] FATAL: Pico ignored the shift command! It is still at the old baud."
                )
                print(
                    "  [i] The shift packet was likely corrupted by EMI. Aborting this frequency."
                )
                continue  # Skip to the next baud rate
            else:
                print("[✓] DEAF (Good, it left the baseline)")

            # Tap 2: Ensure it arrived at the new frequency
            sys.stdout.write(f"  [?] Pinging NEW baud ({target_baud})... ")
            sys.stdout.flush()
            if ping_node(node, target_baud, timeout=0.5):
                print("[✓] ALIVE (Shift Successful)")
            else:
                print("[✗] DEAF")
                print(
                    "  [✗] Node left the old baud but is completely deaf at the new one."
                )
                if not rubber_band_recovery(node):
                    sys.exit(1)
                continue  # Skip to the next baud rate

        # [STAGE 4] TEST IT
        stats = test_link(node, target_baud)
        if stats:
            results.append(stats)

        # [STAGE 5] RESTORE BASELINE
        if target_baud != SAFE_BAUD:
            print(f"\n[STAGE 5] CLEANUP: Restoring baseline ({SAFE_BAUD}) in RAM")
            shift_baud_ram(node, target_baud, SAFE_BAUD)

            sys.stdout.write(f"  [?] Verifying snap-back to {SAFE_BAUD}... ")
            sys.stdout.flush()
            if ping_node(node, SAFE_BAUD):
                print("[✓] ALIVE")
            else:
                print("[✗] DEAF")
                if not rubber_band_recovery(node):
                    sys.exit(1)

    # --- REPORT ---
    print("\n\n" + "=" * 60)
    print(f" NINELIVES EMI & BAUD PROFILE REPORT: NODE {node}")
    print("=" * 60)
    print(
        f"| {'Baud Rate':<10} | {'Success':<8} | {'Avg Lat':<8} | {'Max Lat':<8} | {'CRC Errs':<8} |"
    )
    print(
        "|"
        + "-" * 12
        + "|"
        + "-" * 10
        + "|"
        + "-" * 10
        + "|"
        + "-" * 10
        + "|"
        + "-" * 10
        + "|"
    )

    for r in results:
        print(
            f"| {r['baud']:<10} | {r['success']:>6.1f} % | {r['avg_lat']:>5.1f} ms | {r['max_lat']:>5.1f} ms | {r['crc']:>8} |"
        )
    print("=" * 60 + "\n")
