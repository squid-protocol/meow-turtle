"""
tests/test_limb_actuators.py - MicroPython Actuator Subsystem Unit Tests.

Runs against the actual pico_template/lib/actuators.py using mock_rp2040 HAL.
Validates:
1. Soft-start ramping calculations (Spec 10.7.5).
2. Solenoid thermal fuse trip at max_on_ms (Spec 10.7.7).
3. Tachometer verification & stall detection (Spec 16.2).
4. Gyro noise verification & negative error immunity (preventing false F_RUN).
5. Emergency stop clamping.
"""

import os
import sys
import pytest

# Install MicroPython HAL shim before importing limb modules
import tests.mock_rp2040 as mock_rp2040

mock_rp2040.install()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICO_DIR = os.path.join(BASE_DIR, "pico_template")
if PICO_DIR not in sys.path:
    sys.path.insert(0, PICO_DIR)

import lib.actuators as actuators


@pytest.fixture
def sample_config():
    return {
        "actuators": [
            {
                "id": "CONVEYOR",
                "type": "BLDC",
                "pin": 21,
                "dir_pin": 20,
                "invert_dir": False,
                "min_duty": 0.05,
                "ramp_ms": 200,
                "failsafe_val": 0.0,
                "verification": {
                    "strategy": "TACHOMETER",
                    "sensor_id": "PULSE",
                    "threshold": 10,
                    "settle_ms": 100,
                    "quiet_ms": 200,
                },
            },
            {
                "id": "GATE_SOLENOID",
                "type": "SOLENOID",
                "pin": 11,
                "max_on_ms": 100,
                "failsafe_val": 0.0,
            },
            {
                "id": "VIBRATOR",
                "type": "VIBE_DRIVER",
                "pin": 12,
                "min_duty": 0.2,
                "max_duty": 1.0,
                "freq": 9400,
                "ramp_ms": 100,
                "failsafe_val": 0.0,
                "verification": {
                    "strategy": "GYRO_NOISE",
                    "sensor_id": "MAIN",
                    "threshold": 5.0,
                    "settle_ms": 50,
                    "quiet_ms": 100,
                },
            },
        ]
    }


class TestActuatorRampingAndThermal:
    def test_soft_start_ramping(self, sample_config):
        """Verifies BLDC soft-start ramp-up and ramp-down rates."""
        mgr = actuators.ActuatorManager(sample_config)

        # Command full speed (1.0) with ramp_ms=200
        mgr.set_target("CONVEYOR", 1.0)
        assert mgr.current["CONVEYOR"] == 0.0

        # Advance 100ms -> should reach ~0.5
        mgr.update(100.0)
        curr = mgr.current["CONVEYOR"]
        assert 0.45 <= curr <= 0.55

        # Advance another 100ms -> should reach 1.0
        mgr.update(100.0)
        assert mgr.current["CONVEYOR"] == 1.0

        # Command STOP (0.0)
        mgr.set_target("CONVEYOR", 0.0)
        mgr.update(100.0)
        curr = mgr.current["CONVEYOR"]
        assert 0.45 <= curr <= 0.55

        mgr.update(100.0)
        assert mgr.current["CONVEYOR"] == 0.0

    def test_solenoid_thermal_fuse(self, sample_config):
        """Verifies solenoid is shut off and faulted when active past max_on_ms."""
        mgr = actuators.ActuatorManager(sample_config)

        # Energize solenoid (max_on_ms = 100)
        mgr.set_target("GATE_SOLENOID", 1.0)
        mgr.update(10.0)  # Latch current to 1.0
        mgr.update(50.0)  # Accumulate 50ms
        assert "GATE_SOLENOID" not in mgr.faults
        assert mgr.current["GATE_SOLENOID"] == 1.0

        # Exceed 100ms (50ms + 60ms = 110ms)
        mgr.update(60.0)
        assert "GATE_SOLENOID" in mgr.faults
        assert mgr.faults["GATE_SOLENOID"] == actuators.VS_FAULT_THERMAL
        assert mgr.current["GATE_SOLENOID"] == 0.0


class TestActuatorVerificationAndSafety:
    def test_tachometer_stall_detection(self, sample_config):
        """Verifies that stationary tachometer while motor powered triggers F_STL."""
        mgr = actuators.ActuatorManager(sample_config)

        # Command motor ON
        mgr.set_target("CONVEYOR", 1.0)
        mgr.update(200.0)  # Finished ramping to 1.0

        # Feed sensor data with 0 pulses (stalled)
        # Drain confidence from 100 to 0 (50 steps of -2.0) past settle_ms (100)
        sensor_data = {"PULSE": 0}
        for _ in range(60):
            mgr.update(20.0, sensor_data=sensor_data)

        # Fault is latched into faults dict (Spec 16.5)
        assert "CONVEYOR" in mgr.faults
        assert mgr.faults["CONVEYOR"] == actuators.VS_FAULT_STALL
        assert mgr.current["CONVEYOR"] == 0.0  # Output forced to 0.0 on fault

    def test_negative_sensor_error_immunity(self, sample_config):
        """CRITICAL: Verifies negative sensor error codes (-8, -1, -2) do NOT trigger false runaway (F_RUN)."""
        mgr = actuators.ActuatorManager(sample_config)

        # Motor is OFF (target = 0.0, current = 0.0)
        mgr.set_target("VIBRATOR", 0.0)
        mgr.update(50.0)

        # Inject negative error codes from failed/frozen I2C gyro sensor (-8 ERR_ZOMBIE, -1 ERR_IO)
        corrupted_sensor_data = {
            "MAIN_GYRO": -8,
            "MAIN_GYRO_GX": -8,
            "MAIN_GYRO_GY": -8,
            "MAIN_GYRO_GZ": -8,
        }

        # Run multiple update cycles past quiet_ms (100ms)
        for _ in range(20):
            mgr.update(20.0, sensor_data=corrupted_sensor_data)

        # Motor was OFF, sensor reported negative error: must NOT trigger F_RUN
        assert "VIBRATOR" not in mgr.faults
        assert mgr.verify_states["VIBRATOR"] != actuators.VS_FAULT_RUNAWAY

    def test_emergency_stop_immediate_clamp(self, sample_config):
        """Verifies emergency_stop() zeroes all targets and overrides immediately."""
        mgr = actuators.ActuatorManager(sample_config)

        mgr.set_target("CONVEYOR", 1.0)
        mgr.set_target("VIBRATOR", 0.8)
        mgr.set_target("GATE_SOLENOID", 1.0)
        mgr.update(200.0)

        mgr.emergency_stop()

        for aid in mgr.targets:
            assert mgr.targets[aid] == 0.0
            assert mgr.current[aid] == 0.0
