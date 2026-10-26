# lib/virtual_fleet.py - Ninelives Virtual Fleet & Hardware Simulation Layer
# ROLE: High-Fidelity In-Memory Loopback Emulation of RS-485 Pico Fleet.
# PURPOSE: Enables testing of Core 0 SCADA dashboard, Digital Twin, pulse math,
#          kinetic sorting pipeline, and W-Protocol on host without physical limbs.

import asyncio
import time
import json
import os
import logging
from lib import meowprotocol
from lib import machine_states as ms
from lib.switchboard import PicoController
from lib.digital_twin import GLOBAL_TWIN

logger = logging.getLogger("VirtualFleet")

# Shared physical kinematics across the sorter chassis
SHARED_PHYSICS = {
    "conveyor_speed": 0.0,
    "belt_pulse_count": 0,
}


class VirtualSerialWriter:
    """In-memory serial writer matching the asyncio StreamWriter interface."""

    def __init__(self, on_write_cb):
        self._on_write_cb = on_write_cb

    def write(self, data: bytes):
        if self._on_write_cb:
            self._on_write_cb(data)

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        pass

    async def wait_closed(self):
        pass


class VirtualPicoController(PicoController):
    """
    [Simulation Standard] Virtual Pico Node Controller.

    Simulates the firmware behavior of an RP2040/RP2350 microcontroller running
    the Ninelives.shell MicroPython stack. Participates in full MTIP wire-framing,
    CRC-16 validation, W-Protocol piggyback wipes, and autonomous physics.
    """

    def __init__(self, port, baud_rate, device_id, logic_queue, coordinator):
        super().__init__(port, baud_rate, device_id, logic_queue, coordinator)
        self.sim_parser = meowprotocol.PacketParser(local_id=self.id)
        self.sim_state = ms.STATE_IDLE
        self.sim_start_time = time.time()
        self.sim_voltage = 5.04
        self.sim_temp = 28.5
        self.sim_pulse_count = 0
        self.sim_conveyor_speed = 0.0
        self.sim_beam_raw = 850
        self.sim_beam_trip = 0
        self.sim_unacked_events = set()
        self._sim_task = None
        self._part_sim_counter = 0
        self._sim_next_seq = 100

        # Load device configuration if available on disk
        self.sim_config = self._load_pico_config()

    def _load_pico_config(self):
        """Loads configuration from picoX/config.json if present."""
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", f"pico{self.id}")
        )
        cfg_path = os.path.join(base_dir, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[VirtualPico {self.id}] Config load failed: {e}")

        # Fallback default configuration
        role_map = {1: "LOADER", 2: "GATEKEEPER", 3: "DISTRIBUTOR"}
        return {
            "system": {
                "device_id": self.id,
                "role": role_map.get(self.id, f"LIMB_{self.id}"),
                "version": "1.00",
            },
            "tuning": {"heartbeat_timeout_ms": 500},
        }

    async def connect(self):
        """Establishes the virtual in-memory duplex stream."""
        self.reader = asyncio.StreamReader()
        self.writer = VirtualSerialWriter(self._on_host_bytes)
        self.connected = True

        if self.model:
            self.model.remote_state = ms.STATE_IDLE
            self.model.voltage = self.sim_voltage
            self.model.temp = self.sim_temp
            self.model.uptime = 1
            self.model.touch()

        # Launch periodic simulation loop for autonomous sensors & kinetics
        self._sim_task = asyncio.create_task(self._simulation_loop())
        logger.info(
            f"[VirtualPico {self.id}] Loopback Link Online ({self.port}) - Emulating {self.model.name if self.model else self.id}"
        )
        return True

    def _on_host_bytes(self, chunk: bytes):
        """Invoked when Commander transmits an MTIP packet to this limb."""
        try:
            packets = self.sim_parser.parse(chunk)
            for pkt in packets:
                target, source, seq, mtype, payload = pkt
                if target != self.id and target != 0xFF:
                    continue
                self._handle_sim_packet(source, seq, mtype, payload)
        except Exception as e:
            logger.error(f"[VirtualPico {self.id}] Ingestion crash: {e}")

    def _handle_sim_packet(self, source, seq, mtype, payload):
        """Processes incoming host packet and emits appropriate MTIP responses."""
        # W-Protocol extraction (Spec 4.3.6.3)
        payload_str = (
            payload.decode("ascii", "ignore")
            if isinstance(payload, bytes)
            else str(payload)
        )
        if "|W=" in payload_str:
            clean_payload, w_part = payload_str.split("|W=", 1)
            for token in w_part.split(","):
                token = token.strip()
                if token.isdigit():
                    w_seq = int(token)
                    self.sim_unacked_events.discard(w_seq)
        else:
            clean_payload = payload_str

        # 1. STOP (0x00)
        if mtype == meowprotocol.MSG_TYPE_CMD_STOP:
            self.sim_state = ms.STATE_ERROR
            SHARED_PHYSICS["conveyor_speed"] = 0.0
            self.sim_conveyor_speed = 0.0
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

        # 2. COMMAND (0x10)
        elif mtype == meowprotocol.MSG_TYPE_CMD:
            cmd = clean_payload.strip()
            if cmd == "IDLE":
                self.sim_state = ms.STATE_IDLE
                SHARED_PHYSICS["conveyor_speed"] = 0.0
                self.sim_conveyor_speed = 0.0
            elif cmd == "FLOW":
                self.sim_state = ms.STATE_FLOW
                SHARED_PHYSICS["conveyor_speed"] = 0.8
                self.sim_conveyor_speed = 0.8
            elif cmd == "RESET":
                self.sim_state = ms.STATE_BOOT
                SHARED_PHYSICS["conveyor_speed"] = 0.0
                self.sim_conveyor_speed = 0.0
                asyncio.create_task(self._delayed_state_change(ms.STATE_IDLE, 1.5))
            elif cmd.startswith("ACT:"):
                act_str = cmd[4:]
                if "conveyor" in act_str.lower():
                    for sep in ["=", ":"]:
                        if sep in act_str:
                            val_part = act_str.split(sep)[-1]
                            try:
                                val = float(val_part)
                                SHARED_PHYSICS["conveyor_speed"] = val
                                self.sim_conveyor_speed = val
                            except ValueError:
                                pass
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

        # 3. STATUS QUERY (0x11)
        elif mtype == meowprotocol.MSG_TYPE_CMD_STS:
            sts_str = self._build_status_string()
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_STS, sts_str)

        # 4. VERSION QUERY (0x12)
        elif mtype == meowprotocol.MSG_TYPE_CMD_VER:
            ver_str = self._build_version_string()
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_VRS, ver_str)

        # 5. LOG QUERY (0x13)
        elif mtype == meowprotocol.MSG_TYPE_CMD_LOG:
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, "NO_LOG")

        # 6. RESET (0x14)
        elif mtype == meowprotocol.MSG_TYPE_CMD_RST:
            self.sim_state = ms.STATE_BOOT
            self.sim_conveyor_speed = 0.0
            asyncio.create_task(self._delayed_state_change(ms.STATE_IDLE, 1.5))
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

        # 7. ACTUATOR QUERY (0x15)
        elif mtype == meowprotocol.MSG_TYPE_CMD_ACT:
            act_str = self._build_actuator_string()
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACT, act_str)

        # 8. SENSOR QUERY (0x16)
        elif mtype == meowprotocol.MSG_TYPE_CMD_SNS:
            sns_str = self._build_sensor_string()
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_SNS, sns_str)

        # 9. CONFIG QUERY (0x17)
        elif mtype == meowprotocol.MSG_TYPE_CMD_CFG:
            cfg_str = json.dumps(self.sim_config)
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_CFG, cfg_str)

        # 10. SET CONFIG (0x18)
        elif mtype == meowprotocol.MSG_TYPE_SET_CFG:
            if "speed=" in clean_payload:
                try:
                    s_val = float(clean_payload.split("speed=")[1].split(",")[0])
                    self.sim_conveyor_speed = s_val
                except ValueError:
                    pass
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

        # 11. TIME SYNC (0x1A)
        elif mtype == meowprotocol.CMD_SYNC_TIME:
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

        # Default ACK
        else:
            self._send_sim_packet(source, seq, meowprotocol.MSG_TYPE_ACK, str(seq))

    def _send_sim_packet(self, target, seq, mtype, payload):
        """Constructs an MTIP wire-framed packet and feeds it to the incoming reader."""
        try:
            pkt = meowprotocol.build_packet(target, self.id, seq, mtype, payload)
            if self.reader:
                self.reader.feed_data(pkt)
        except Exception as e:
            logger.error(f"[VirtualPico {self.id}] Sim TX Error: {e}")

    async def _delayed_state_change(self, target_state, delay_s):
        """Simulates firmware reboot and initialization delay."""
        await asyncio.sleep(delay_s)
        self.sim_state = target_state
        if self.model:
            self.model.remote_state = target_state

    def _build_status_string(self):
        uptime = int(time.time() - self.sim_start_time)
        status = (
            f"ST={self.sim_state},"
            f"UPT={uptime},"
            f"V={self.sim_voltage:.2f},"
            f"VM=4.98,"
            f"T={self.sim_temp:.1f},"
            f"RAM=85.0%,"
            f"RST=PWR,"
            f"LA=120,"
            f"LM=250,"
            f"CE=0,"
            f"IE=0,"
            f"WC=0,"
            f"RA=10,"
            f"RL=15,"
            f"CSE=0"
        )
        if self.sim_unacked_events:
            status += ",UA=" + ",".join(str(x) for x in sorted(self.sim_unacked_events))
        return status

    def _build_version_string(self):
        sys_info = self.sim_config.get("system", {})
        ver = sys_info.get("version", "1.00")
        role = sys_info.get("role", f"LIMB_{self.id}")
        return f"FW={ver},ROLE={role},BRANCH=main,COMMIT=sim"

    def _build_actuator_string(self):
        if self.id == 1:
            return (
                "SVIB=0.0,SVIB_ST=IDLE,SOL_TDWN=0.0,SOL_TDWN_ST=IDLE,"
                "TVIB=0.0,TVIB_ST=IDLE,SOL_TUP=0.0,SOL_TUP_ST=IDLE"
            )
        elif self.id == 2:
            return "GATE=0.0,GATE_ST=IDLE"
        elif self.id == 3:
            badge = "ON" if self.sim_conveyor_speed > 0 else "OFF"
            sol_items = ",".join(f"SOL_{i}=0.0,SOL_{i}_ST=IDLE" for i in range(1, 11))
            return (
                f"CONVEYOR={self.sim_conveyor_speed:.2f},CONVEYOR_ST={badge},{sol_items}"
            )
        return "ACT_CNT=0"

    def _build_sensor_string(self):
        if self.id == 1:
            return (
                "ESTOP_BUTTON=0,MAIN_accel_x=0.01,MAIN_accel_y=0.02,MAIN_accel_z=0.98,"
                "AUX_accel_x=0.00,AUX_accel_y=0.01,AUX_accel_z=0.99"
            )
        elif self.id == 2:
            return (
                f"ESTOP_BUTTON=0,pulse_count={self.sim_pulse_count},"
                f"global_tick={self.sim_pulse_count},global_tick_TOTAL={self.sim_pulse_count},"
                f"odo={self.sim_pulse_count},beam_raw={self.sim_beam_raw},"
                f"beam_sigma=0.5,beam_trip={self.sim_beam_trip}"
            )
        elif self.id == 3:
            rpm = int(self.sim_conveyor_speed * 1200)
            return f"ESTOP_BUTTON=0,pulse_count={self.sim_pulse_count},tach_rpm={rpm}"
        return "SNS_OK"

    async def _simulation_loop(self):
        """Autonomous 10Hz physics, tachometer, and breakbeam tick loop."""
        while self.connected:
            try:
                await asyncio.sleep(0.1)

                # Kinetics: Check shared conveyor motion or FLOW state
                speed = max(self.sim_conveyor_speed, SHARED_PHYSICS["conveyor_speed"])
                if speed > 0 or self.sim_state == ms.STATE_FLOW:
                    rate = max(0.2, speed)
                    pulses_per_tick = int(12 * rate)
                    SHARED_PHYSICS["belt_pulse_count"] += max(1, pulses_per_tick)

                self.sim_pulse_count = SHARED_PHYSICS["belt_pulse_count"]
                if self.id == 3:
                    self.sim_conveyor_speed = SHARED_PHYSICS["conveyor_speed"]

                # Simulated LEGO part detection on Gatekeeper (Pico 2)
                if self.id == 2 and self.sim_state == ms.STATE_FLOW:
                    self._part_sim_counter += 1
                    # Trigger part detection every ~4 seconds (40 ticks @ 100ms)
                    if self._part_sim_counter >= 40:
                        self._part_sim_counter = 0
                        # 1. Optical dip
                        self.sim_beam_raw = 110
                        self.sim_beam_trip = 1

                        # 2. Spontaneous Event packet from independent event sequence
                        self._sim_next_seq = (self._sim_next_seq + 1) % 65535
                        evt_seq = self._sim_next_seq
                        self.sim_unacked_events.add(evt_seq)
                        evt_payload = (
                            f"PART_DETECTED,center_pulse={self.sim_pulse_count}"
                        )
                        self._send_sim_packet(
                            0, evt_seq, meowprotocol.MSG_TYPE_EVT, evt_payload
                        )

                        # Restore optical baseline after 250ms
                        await asyncio.sleep(0.25)
                        self.sim_beam_raw = 850
                        self.sim_beam_trip = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[VirtualPico {self.id}] Sim Loop Error: {e}")
                await asyncio.sleep(0.5)

    def close(self):
        """Stops the simulation task and closes pipes."""
        self.connected = False
        if self._sim_task:
            self._sim_task.cancel()
        if self.writer:
            self.writer.close()
