"""
tests/firmware_pico.py - Co-Simulation Controller for RP2040 Limb Firmware.

Connects the Raspberry Pi 5 Core 0 SystemCoordinator / Switchboard to
in-memory RP2040 limbs running the actual MicroPython firmware stack
(pico_template/app.py, ActuatorManager, SensorManager, BreakbeamMonitor)
via isolated module namespaces and duplex stream pipes.
"""

import sys
import os
import time
import asyncio
import importlib.util
from typing import Optional, Dict, Any

try:
    import tests.mock_rp2040 as mock_rp2040
except ImportError:
    import mock_rp2040
mock_rp2040.install()

from lib import meowprotocol
from lib import machine_states as ms
from lib.digital_twin import GLOBAL_TWIN
from lib.switchboard import PicoController
import actuators
import sensors
import diagnostics

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PY_PATH = os.path.join(BASE_DIR, "pico_template", "app.py")


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


def create_firmware_instance(device_id: int, role: str, config: Optional[Dict[str, Any]] = None):
    """
    Spawns an isolated execution context of pico_template/app.py for a specific limb ID.
    Ensures global state variables (shared_state, act_mgr, sns_mgr) are fully isolated per node.
    """
    spec = importlib.util.spec_from_file_location(f"pico_firmware_node_{device_id}", APP_PY_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)

    # 1. Base Configuration
    default_actuators = {
        1: [{"id": "CONVEYOR", "type": "BLDC", "pin": 10, "dir_pin": 15, "freq": 20000, "ramp_ms": 100},
            {"id": "FEEDER_VIBE", "type": "PWM", "pin": 11, "freq": 5000, "ramp_ms": 50}],
        2: [{"id": "SOLENOID_DIVERT", "type": "SOLENOID", "pin": 12, "max_on_ms": 500},
            {"id": "GATE_VIBE", "type": "PWM", "pin": 13, "freq": 5000, "ramp_ms": 50}],
        3: [{"id": "DIST_PWM", "type": "PWM", "pin": 14, "freq": 10000, "ramp_ms": 100}]
    }

    sys_cfg = {
        "system": {"device_id": device_id, "role": role, "version": "1.20"},
        "comms": {"uart_bus": 0, "tx_pin": 0, "rx_pin": 1, "baud_rate": 115200, "max_retries": 3},
        "actuators": default_actuators.get(device_id, [{"id": f"ACT_{device_id}", "type": "PWM", "pin": 10}]),
        "sensors": {},
        "testing": {"watchdog_enabled": False, "standalone_mode": False}
    }
    if config:
        sys_cfg.update(config)

    app.system_config = sys_cfg

    # 2. State Initialization
    with app.state_lock:
        app.shared_state["id"] = device_id
        app.shared_state["current_state"] = app.STATE_IDLE
        app.shared_state["uptime_start"] = time.time()
        app.shared_state["lives_refilled"] = True
        app.shared_state["boot_attempts_cleared"] = True
        app.shared_state["error_code"] = "NONE"

    # 3. Hardware Subsystems
    app.act_mgr = actuators.ActuatorManager(sys_cfg)
    app.sns_mgr = sensors.SensorManager(sys_cfg)
    app.sys_man = diagnostics.SystemManifest()

    return app


class FirmwarePicoController(PicoController):
    """
    [Co-Simulation Adapter] Real-Firmware Loopback Controller.

    Replaces synthetic packet mocking with a live MicroPython firmware instance
    running concurrently on the asyncio event loop.
    """

    def __init__(self, port: str, baud_rate: int, device_id: int, logic_queue, coordinator, role: Optional[str] = None):
        super().__init__(port, baud_rate, device_id, logic_queue, coordinator)
        
        role_map = {1: "LOADER", 2: "GATEKEEPER", 3: "DISTRIBUTOR"}
        self.role = role or role_map.get(device_id, f"LIMB_{device_id}")

        self.app = create_firmware_instance(self.id, self.role)
        self.firmware_uart = mock_rp2040.MockUART(0)
        self.firmware_parser = meowprotocol.PacketParser(self.id)
        
        self._firmware_task: Optional[asyncio.Task] = None
        self._last_tick = time.ticks_ms()

    async def connect(self):
        """Establishes in-memory duplex streams and launches the real-time physics task."""
        self.reader = asyncio.StreamReader()
        self.writer = VirtualSerialWriter(self._on_host_bytes)
        self.connected = True

        if self.model:
            self.model.remote_state = ms.STATE_IDLE
            self.model.touch()

        self._firmware_task = asyncio.create_task(self._firmware_tick_loop())
        return True

    def _on_host_bytes(self, chunk: bytes):
        """Ingests raw bytes from Host TX, processes through app.py, and returns replies."""
        try:
            packets = self.firmware_parser.parse_stream(chunk)
            for pkt in packets:
                target, source, seq, mtype, payload = pkt
                if target != self.id and target != 0 and target != 0xFF:
                    continue

                resp = self.app.process_packet(self.firmware_uart, pkt, log_traffic=False)
                if resp and self.reader:
                    self.reader.feed_data(resp)

                if self.firmware_uart.tx_buffer and self.reader:
                    self.reader.feed_data(bytes(self.firmware_uart.tx_buffer))
                    self.firmware_uart.tx_buffer.clear()
        except Exception as e:
            pass

    async def _firmware_tick_loop(self):
        """Concurrent physics loop and asynchronous event flusher (50 Hz)."""
        while self.running:
            try:
                now = time.ticks_ms()
                dt = time.ticks_diff(now, self._last_tick)
                self._last_tick = now

                # 1. Real-time actuator physics (ramping, thermal fuses)
                if self.app.act_mgr:
                    self.app.act_mgr.update(dt)

                # 2. Flush pending events (e.g. breakbeam trips)
                events_to_send = []
                with self.app.state_lock:
                    if self.app.shared_state["pending_events"]:
                        events_to_send = list(self.app.shared_state["pending_events"])
                        self.app.shared_state["pending_events"].clear()

                for payload in events_to_send:
                    self.app.send_reliable(self.firmware_uart, 0, meowprotocol.MSG_TYPE_EVT, payload)

                if self.firmware_uart.tx_buffer and self.reader:
                    self.reader.feed_data(bytes(self.firmware_uart.tx_buffer))
                    self.firmware_uart.tx_buffer.clear()

                # 3. Mirror firmware state to digital twin
                if self.model:
                    with self.app.state_lock:
                        st = self.app.shared_state["current_state"]
                    self.model.remote_state = st

                await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.05)

    def trigger_event(self, payload: str):
        """Simulates an asynchronous sensor event (e.g., PART:spatial_id:pulse)."""
        with self.app.state_lock:
            self.app.shared_state["pending_events"].append(payload)

    def inject_fault(self, fault_code: str):
        """Forces the limb firmware into ERROR state with a specific fault code."""
        with self.app.state_lock:
            self.app.shared_state["current_state"] = self.app.STATE_ERROR
            self.app.shared_state["error_code"] = fault_code
        if self.app.act_mgr:
            self.app.act_mgr.emergency_stop()

    def set_ghost_mode(self):
        """Forces the limb firmware into GHOST recovery state."""
        with self.app.state_lock:
            self.app.shared_state["current_state"] = self.app.STATE_GHOST
            self.app.shared_state["error_code"] = "BOOT_FAIL"
        if self.app.act_mgr:
            self.app.act_mgr.emergency_stop()

    def close(self):
        """Tears down background tasks and closes streams."""
        self.running = False
        self.connected = False
        if self._firmware_task:
            self._firmware_task.cancel()
        if self.reader and not self.reader.at_eof():
            try:
                self.reader.feed_eof()
            except Exception:
                pass
