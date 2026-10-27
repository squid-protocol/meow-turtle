"""
tests/mock_rp2040.py - MicroPython RP2040/RP2350 Hardware Mocking Shim.

Allows MicroPython firmware modules (ActuatorManager, BreakbeamMonitor, etc.)
to be executed and tested under standard Python 3 / pytest without hardware.
"""

import sys
import time
import types
import threading

# --- 1. Mock Hardware Clock & Ticks ---
_SIM_START_TIME = time.time()


def ticks_ms():
    return int((time.time() - _SIM_START_TIME) * 1000) & 0x3FFFFFFF


def ticks_us():
    return int((time.time() - _SIM_START_TIME) * 1000000) & 0x3FFFFFFF


def ticks_diff(t1, t2):
    diff = (t1 - t2) & 0x3FFFFFFF
    if diff & 0x20000000:
        diff -= 0x40000000
    return diff


def ticks_add(t, delta):
    return (t + delta) & 0x3FFFFFFF


def sleep_ms(ms):
    time.sleep(ms / 1000.0)


def sleep_us(us):
    time.sleep(us / 1000000.0)


# --- 2. Mock Machine Hardware Classes ---
class MockPin:
    IN = 0
    OUT = 1
    PULL_UP = 1
    PULL_DOWN = 2

    def __init__(self, pin_num, mode=OUT, pull=None, value=0):
        self.pin_num = pin_num
        self.mode = mode
        self.pull = pull
        self._val = value

    def value(self, val=None):
        if val is not None:
            self._val = int(bool(val))
        return self._val

    def on(self):
        self._val = 1

    def off(self):
        self._val = 0

    def toggle(self):
        self._val = 0 if self._val else 1


class MockPWM:
    def __init__(self, pin, freq=1000, duty_u16=0):
        self.pin = pin
        self._freq = freq
        self._duty_u16 = duty_u16
        self.active = True

    def freq(self, value=None):
        if value is not None:
            self._freq = value
        return self._freq

    def duty_u16(self, value=None):
        if value is not None:
            self._duty_u16 = max(0, min(65535, int(value)))
        return self._duty_u16

    def deinit(self):
        self.active = False


class MockADC:
    def __init__(self, pin):
        self.pin = pin
        self.mock_voltage = 5.0

    def read_u16(self):
        # Convert mock_voltage (assuming VSYS 3:1 divider: V_adc = mock_voltage / 3)
        v_adc = self.mock_voltage / 3.0
        return int((v_adc / 3.3) * 65535)


class MockWDT:
    def __init__(self, timeout=8000):
        self.timeout = timeout
        self.last_feed = ticks_ms()

    def feed(self):
        self.last_feed = ticks_ms()


class MockUART:
    def __init__(self, bus_id, baudrate=115200, tx=None, rx=None, timeout=0):
        self.bus_id = bus_id
        self.baudrate = baudrate
        self.tx_buffer = bytearray()
        self.rx_buffer = bytearray()

    def any(self):
        return len(self.rx_buffer)

    def read(self, n=None):
        if not self.rx_buffer:
            return None
        if n is None:
            data = bytes(self.rx_buffer)
            self.rx_buffer.clear()
            return data
        data = bytes(self.rx_buffer[:n])
        del self.rx_buffer[:n]
        return data

    def write(self, data):
        self.tx_buffer.extend(data)
        return len(data)


# --- 3. Mock Machine Module ---
mock_machine = types.ModuleType("machine")
mock_machine.Pin = MockPin
mock_machine.PWM = MockPWM
mock_machine.ADC = MockADC
mock_machine.WDT = MockWDT
mock_machine.UART = MockUART

mock_machine.PWRON_RESET = 1
mock_machine.HARD_RESET = 2
mock_machine.WDT_RESET = 3
mock_machine.SOFT_RESET = 4

mock_machine._reset_cause = mock_machine.PWRON_RESET
mock_machine.reset_cause = lambda: mock_machine._reset_cause
mock_machine.reset = lambda: None
mock_machine.idle = lambda: time.sleep(0.001)

# --- 4. Mock RP2 PIO Module ---
class MockPIO:
    SHIFT_RIGHT = 0
    SHIFT_LEFT = 1
    JOIN_RX = 2
    JOIN_TX = 3
    JOIN_NONE = 0
    OUT_LOW = 0
    OUT_HIGH = 1
    IN_LOW = 2
    IN_HIGH = 3


class MockStateMachine:
    def __init__(self, *args, **kwargs):
        pass
    def active(self, val=None):
        pass
    def get(self, *args, **kwargs):
        return 0
    def put(self, *args, **kwargs):
        pass

mock_rp2 = types.ModuleType("rp2")
mock_rp2.PIO = MockPIO
mock_rp2.StateMachine = MockStateMachine
mock_rp2.asm_pio = lambda *args, **kwargs: (lambda fn: fn)


def install():
    """Patches sys.modules and time to emulate RP2040 MicroPython."""
    sys.modules["machine"] = mock_machine
    sys.modules["rp2"] = mock_rp2

    # Standard MicroPython 'u' alias modules
    import binascii
    import os
    import json
    import gc

    sys.modules["ubinascii"] = binascii
    sys.modules["uos"] = os
    sys.modules["ujson"] = json
    sys.modules["utime"] = time

    # MicroPython gc shims
    if not hasattr(gc, "mem_free"):
        gc.mem_free = lambda: 1048576
    if not hasattr(gc, "mem_alloc"):
        gc.mem_alloc = lambda: 524288

    # Patch time module with MicroPython tick extensions
    time.ticks_ms = ticks_ms
    time.ticks_us = ticks_us
    time.ticks_diff = ticks_diff
    time.ticks_add = ticks_add
    time.sleep_ms = sleep_ms
    time.sleep_us = sleep_us

    # Ensure lib module paths include pico_template/lib
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pico_dir = os.path.join(base_dir, "pico_template")
    pico_lib = os.path.join(pico_dir, "lib")
    core0_dir = os.path.join(base_dir, "core0 - Commander")

    if core0_dir not in sys.path:
        sys.path.insert(0, core0_dir)
    if pico_dir not in sys.path:
        sys.path.insert(0, pico_dir)
    if pico_lib not in sys.path:
        sys.path.insert(0, pico_lib)

    try:
        import lib
        if hasattr(lib, "__path__") and pico_lib not in lib.__path__:
            lib.__path__.append(pico_lib)
    except ImportError:
        pass
