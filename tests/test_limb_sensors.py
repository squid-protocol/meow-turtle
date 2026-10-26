"""
tests/test_limb_sensors.py - MicroPython Sensor Filtering & Zombie Lock Unit Tests.

Runs against pico_template/lib/sensors.py using mock_rp2040.
Validates:
1. Physical limit checking (Spec 11.5.2).
2. Ambient exemption: TSL light sensors and temperature probes NEVER false-lock into ERR_ZOMBIE (-8).
3. Dynamic axis freeze detection: Gyro axes return ERR_ZOMBIE only after sustained (>500 polls) silicon freeze.
"""

import os
import sys
import pytest

import tests.mock_rp2040 as mock_rp2040

mock_rp2040.install()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICO_DIR = os.path.join(BASE_DIR, "pico_template")
if PICO_DIR not in sys.path:
    sys.path.insert(0, PICO_DIR)

import lib.sensors as sensors


@pytest.fixture
def bus_wrapper():
    cfg = {"id": 0, "sda": 4, "scl": 5, "prefix": "MAIN"}
    return sensors.BusWrapper(cfg)


class TestSensorFilters:
    def test_physical_limit_check(self, bus_wrapper):
        """Verifies readings > 65000 are rejected with ERR_LIMIT (-7)."""
        res = bus_wrapper._apply_filters("MAIN_ANALOG", 65535)
        assert res == sensors.ERR_LIMIT

        res_ok = bus_wrapper._apply_filters("MAIN_ANALOG", 12345)
        assert res_ok == 12345

    def test_tsl_ambient_exemption_from_zombie(self, bus_wrapper):
        """CRITICAL: Verifies TSL ambient light sensor NEVER returns ERR_ZOMBIE on steady readings."""
        # Poll 2000 times with the exact same lux reading
        for _ in range(2000):
            val = bus_wrapper._apply_filters("MAIN_TSL", 4500)
            assert val == 4500
            assert val != sensors.ERR_ZOMBIE

    def test_temp_ambient_exemption_from_zombie(self, bus_wrapper):
        """CRITICAL: Verifies steady temperature sensor NEVER returns ERR_ZOMBIE."""
        for _ in range(1000):
            val = bus_wrapper._apply_filters("MAIN_TEMP", 24.5)
            assert val == 24.5
            assert val != sensors.ERR_ZOMBIE

    def test_dynamic_axis_zombie_detection(self, bus_wrapper):
        """Verifies dynamic motion gyro axes detect true silicon freezes after 500 polls."""
        # First 400 polls: steady value passes
        for _ in range(400):
            val = bus_wrapper._apply_filters("MAIN_GYRO_GX", 12.5)
            assert val == 12.5

        # After 501+ identical non-zero polls: trips ERR_ZOMBIE
        for _ in range(105):
            val = bus_wrapper._apply_filters("MAIN_GYRO_GX", 12.5)

        assert val == sensors.ERR_ZOMBIE

    def test_zero_value_does_not_trigger_zombie(self, bus_wrapper):
        """Verifies true zero readings (e.g. idle zero motion) do not trigger zombie freeze."""
        for _ in range(600):
            val = bus_wrapper._apply_filters("MAIN_GYRO_GZ", 0)
            assert val == 0
