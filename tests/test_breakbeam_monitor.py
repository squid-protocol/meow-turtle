"""
tests/test_breakbeam_monitor.py - Metrology & Breakbeam Tripwire Unit Tests.

Runs against pico_template/lib/breakbeam_monitor.py using mock_rp2040.
Validates:
1. 20-sample baseline statistical calibration (Spec 16.1).
2. Part singulation and birth certificate payload generation on rising edge.
3. Immunity to negative error codes (e.g. -8 ERR_ZOMBIE, -1 ERR_IO).
4. Manual recalibration reset.
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

import lib.breakbeam_monitor as breakbeam_monitor


@pytest.fixture
def monitor():
    cfg = {
        "tuning": {
            "beam_min_sigma": 15.0,
            "beam_alpha": 0.05,
            "beam_downward_gate_sigma": 1.5,
            "beam_tripwire_sigma": 6.0,
            "beam_sustain_ms": 20,
        }
    }
    return breakbeam_monitor.BreakbeamMonitor(
        cfg, sensor_key="MAIN_TSL", odometer_key="global_tick_TOTAL"
    )


class TestBreakbeamMonitor:
    def test_20_sample_calibration(self, monitor):
        """Verifies initial 20-sample window calculates baseline mean and threshold."""
        assert monitor.calibrating is True

        # Feed 19 samples
        for _ in range(19):
            res = monitor.update({"MAIN_TSL": 5000})
            assert res is None
            assert monitor.calibrating is True

        # Feed 20th sample
        res = monitor.update({"MAIN_TSL": 5000})
        assert res is None
        assert monitor.calibrating is False
        assert monitor.beam_mean == 5000.0
        assert monitor.beam_threshold < 5000.0

    def test_part_detection_and_birth_certificate(self, monitor):
        """Verifies part detection on beam dip and birth certificate generation upon exit."""
        # Calibrate
        for _ in range(20):
            monitor.update({"MAIN_TSL": 5000, "global_tick_TOTAL": 100})

        # Part enters: light drops to 500 (below threshold)
        # Advance time by more than beam_sustain_ms (20ms)
        start_pulse = 200
        for _ in range(5):
            mock_rp2040.sleep_ms(10)
            res = monitor.update({"MAIN_TSL": 500, "global_tick_TOTAL": start_pulse})
            assert res is None

        assert monitor.was_broken is True

        # Part exits: light returns to 5000, odometer advanced to 350
        exit_pulse = 350
        mock_rp2040.sleep_ms(10)
        evt = monitor.update({"MAIN_TSL": 5000, "global_tick_TOTAL": exit_pulse})

        assert evt is not None
        assert "PART_DETECTED" in evt
        assert "center_pulse=" in evt
        assert "len_ms=" in evt
        assert monitor.was_broken is False

    def test_negative_sensor_error_immunity(self, monitor):
        """Verifies negative error codes (-8 ERR_ZOMBIE, -1 ERR_IO) are ignored without breaking state."""
        # Calibrate
        for _ in range(20):
            monitor.update({"MAIN_TSL": 5000})

        # Feed negative error codes
        for err_code in [-8, -1, -2, -4]:
            res = monitor.update({"MAIN_TSL": err_code})
            assert res is None
            assert monitor.was_broken is False

    def test_reset_calibration(self, monitor):
        """Verifies reset_calibration re-arms the 20-sample calibration cycle."""
        for _ in range(20):
            monitor.update({"MAIN_TSL": 5000})
        assert monitor.calibrating is False

        monitor.reset_calibration()
        assert monitor.calibrating is True
        assert len(monitor.calib_samples) == 0
