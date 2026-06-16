# lib/calibration.py - Tuning & Unit Translation (v2.2 - Restored)
# PURPOSE: Handles Pulse/Distance mapping, physical constants, and motor scaling.
# COMPLIANCE: Core 0 Spec Section 16

"""
[Spec 16.0] Ninelives Spatial Calibration System.

The CalibrationManager is responsible for translating logical intents 
into physical hardware parameters and converting raw sensor data 
(Motor Pulses) into real-world units (Millimeters).
"""

import json
import os
import logging

logger = logging.getLogger("Calibration")
CAL_FILE = "config/calibration.json"

DEFAULT_CALIBRATION = {
    "loader": {
        "feeder_freq_hz": 60,
        "shaker_freq_hz": 80,
        "feeder_strength_scale": 1.0,
        "shaker_strength_scale": 1.0
    },
    "distributor": {
        "mm_per_pulse": 0.05123456, 
        "belt_min_start_pwm": 15
    },
    "gatekeeper": {
        "sensor_threshold": 200
    }
}

class CalibrationManager:
    """
    [Spec 16.0] The Calibration Manager.
    Central authority for unit conversion and hardware tuning parameters.
    """
    def __init__(self):
        """Initializes the manager and loads persistent data."""
        self.data = self._load_data()

    def _load_data(self):
        """[Spec 10.4] Configuration Anti-Poison Logic."""
        if not os.path.exists("config"):
            try: os.makedirs("config")
            except: pass
        if not os.path.exists(CAL_FILE):
            self._write_defaults()
            return DEFAULT_CALIBRATION.copy()
        try:
            with open(CAL_FILE, 'r') as f:
                return json.load(f)
        except:
            self._write_defaults()
            return DEFAULT_CALIBRATION.copy()

    def _write_defaults(self):
        """Commits hardcoded defaults to disk to recover from corruption."""
        try:
            with open(CAL_FILE, 'w') as f:
                json.dump(DEFAULT_CALIBRATION, f, indent=2)
        except Exception as e:
            logger.critical(f"Write Fail: {e}")

    def save(self):
        """Atomic write of the calibration data to JSON to prevent power-loss corruption."""
        try:
            tmp_file = CAL_FILE + ".tmp"
            with open(tmp_file, 'w') as f:
                json.dump(self.data, f, indent=2)
                f.flush()
                os.fsync(f.fileno()) # Force OS to write to physical SSD hardware
                
            # Atomic swap replaces the old file with the new one safely
            os.replace(tmp_file, CAL_FILE)
        except Exception as e:
            logger.error(f"Calibration Save Fail: {e}")

    def get_loader_params(self, strength_percent, motor_type="feeder"):
        """[Spec 19.3] Translates GUI 'Strength' into hardware PWM parameters."""
        cfg = self.data.get("loader", {})
        freq = cfg.get(f"{motor_type}_freq_hz", 60)
        scale = cfg.get(f"{motor_type}_strength_scale", 1.0)
        duty = int((strength_percent / 100.0) * 65535 * scale)
        return freq, max(0, min(65535, duty))

    def get_belt_pwm(self, target_speed_percent):
        """[Spec 19.4] Precision speed scaling for the transport belt."""
        cfg = self.data.get("distributor", {})
        min_pwm = cfg.get("belt_min_start_pwm", 15)
        if target_speed_percent <= 0: return 0
        pwm_range = 255 - min_pwm
        pwm = int(min_pwm + (target_speed_percent / 100.0) * pwm_range)
        return max(0, min(255, pwm))

    def pulses_to_mm(self, pulse_count):
        """[Spec 16.1] Translates raw odometer pulses into physical distance."""
        ratio = self.data["distributor"].get("mm_per_pulse", 0.05)
        return pulse_count * ratio

    def mm_to_pulses(self, mm_distance):
        """[Spec 16.3] Translates physical distance into target motor pulses."""
        ratio = self.data["distributor"].get("mm_per_pulse", 0.05)
        if ratio == 0: return 0
        return int(mm_distance / ratio)

    def get_real_speed(self, pulses_per_second):
        """Calculates current belt velocity in millimeters per second."""
        return self.pulses_to_mm(pulses_per_second)

    def update_pulse_ratio(self, measured_distance_mm, total_pulses_observed):
        """[Spec 16.4] Commits new calibration results from the Wizard."""
        if total_pulses_observed <= 0: return
        new_ratio = float(measured_distance_mm) / float(total_pulses_observed)
        self.data["distributor"]["mm_per_pulse"] = round(new_ratio, 8) 
        logger.info(f"Calibration Updated: {new_ratio:.8f} mm/p")
        self.save()

CALIBRATION = CalibrationManager()