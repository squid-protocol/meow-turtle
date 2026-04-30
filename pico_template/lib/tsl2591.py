# tsl2591.py - Driver for TSL2591 Lux Sensor v1.02
# STANDARD: Ninelives Shell v2.2

"""
[Spec 11.0] Sensor Subsystem Specification.
High-range digital luminosity sensor (Lux) driver. Following the "Humble 
Component" pattern (Spec 11.8), it propagates OSErrors to the SensorManager 
to trigger bus resets (Spec 11.4.3) and provides standardized data scaling 
(Spec 4.3.9.3).
"""

import time
from micropython import const
import lib.logging as log

# [Spec 9.10] Dependency Versioning
VERSION = 2.2

# --- REGISTER MAP ---
TSL2591_REGISTER_ENABLE     = const(0x00)
TSL2591_REGISTER_CONFIG     = const(0x01)
TSL2591_REGISTER_DEVICE_ID   = const(0x12)
TSL2591_REGISTER_STATUS      = const(0x13)
TSL2591_REGISTER_CHAN0_LOW   = const(0x14)
TSL2591_REGISTER_CHAN1_LOW   = const(0x16)

# --- COMMANDS ---
TSL2591_COMMAND_BIT         = const(0xA0)
TSL2591_ENABLE_POWERON      = const(0x01)
TSL2591_ENABLE_AEN          = const(0x02)
TSL2591_ENABLE_AIEN         = const(0x10)
TSL2591_ENABLE_NPIEN        = const(0x80)

# --- CONSTANTS ---
TSL2591_INTEGRATIONTIME_100MS = const(0x00)
TSL2591_INTEGRATIONTIME_200MS = const(0x01)
TSL2591_INTEGRATIONTIME_300MS = const(0x02)
TSL2591_INTEGRATIONTIME_400MS = const(0x03)
TSL2591_INTEGRATIONTIME_500MS = const(0x04)
TSL2591_INTEGRATIONTIME_600MS = const(0x05)

TSL2591_GAIN_LOW  = const(0x00) # 1x
TSL2591_GAIN_MED  = const(0x10) # 25x
TSL2591_GAIN_HIGH = const(0x20) # 428x
TSL2591_GAIN_MAX  = const(0x30) # 9876x

class TSL2591:
    """
    [Spec 11.8] Humble Component Driver.
    Interface for the TSL2591 sensor. Responsible for protocol translation 
    without internal error masking, allowing the system to distinguish between 
    wiring breaks (I/O FAIL) and software bugs (BUG).
    """
    def __init__(self, i2c, address=0x29):
        """
        [Spec 9.5] Configuration & Hardware Safety (Safe Init).
        Initializes the sensor object and performs immediate connectivity 
        validation (Spec 9.11). Raises RuntimeError on failure to prevent 
        partial initialization of the Machinist core.
        """
        self.i2c = i2c
        self.address = address
        self._integration_time_val = TSL2591_INTEGRATIONTIME_100MS 
        self._gain_val = TSL2591_GAIN_MED 
        
        # Verify connection (Spec 9.11)
        if not self.ping():
             log.error("SEN", f"TSL2591 not found at {hex(address)}")
             raise RuntimeError(f"TSL2591 not found at {hex(address)}")
        
        self.enable()
        self.set_gain(self._gain_val)
        self.set_timing(self._integration_time_val)
        log.info("SEN", "TSL2591 Init Complete")

    def _write_register(self, register, value):
        """Internal: Direct I2C memory write."""
        cmd = TSL2591_COMMAND_BIT | register
        self.i2c.writeto_mem(self.address, cmd, bytearray([value]))

    def _read_register(self, register, length=1):
        """Internal: Direct I2C memory read."""
        cmd = TSL2591_COMMAND_BIT | register
        data = self.i2c.readfrom_mem(self.address, cmd, length)
        if length == 1:
            return data[0]
        return data

    def ping(self):
        """
        [Spec 9.11] Sensor Connectivity Hardening.
        Validates hardware presence via the silicon Device ID register (0x50).
        Used for startup verification and bus recovery health checks.
        """
        try:
            device_id = self._read_register(TSL2591_REGISTER_DEVICE_ID)
            return device_id == 0x50
        except OSError:
            return False

    def enable(self):
        """[Spec 11.0] Enables the device in Continuous Mode."""
        self._write_register(TSL2591_REGISTER_ENABLE,
                             TSL2591_ENABLE_POWERON | TSL2591_ENABLE_AEN | TSL2591_ENABLE_AIEN | TSL2591_ENABLE_NPIEN)

    def disable(self):
        """[Spec 11.4.2] Places the silicon in low power mode."""
        self._write_register(TSL2591_REGISTER_ENABLE, 0x00)

    def close(self):
        """
        [Spec 11.4.2] Standard Cleanup Method.
        Safely shuts down the sensor to release the I2C bus and reduce 
        power consumption during IDLE or ERROR states.
        """
        try:
            self.disable()
        except:
            pass

    def set_gain(self, gain_val):
        """
        [Spec 11.0] Sensor Configuration API.
        Updates the internal gain multiplier. Whitelisted for CFG tuning.
        """
        self._gain_val = gain_val
        self.enable() 
        self._write_register(TSL2591_REGISTER_CONFIG, self._integration_time_val | self._gain_val)

    def set_timing(self, integration_time_val):
        """
        [Spec 11.0] Sensor Configuration API.
        Updates the integration window. Whitelisted for CFG tuning.
        """
        self._integration_time_val = integration_time_val
        self.enable()
        self._write_register(TSL2591_REGISTER_CONFIG, self._integration_time_val | self._gain_val)

    def get_raw_channels(self):
        """
        [Spec 11.8] Exception Propagation.
        Burst reads 4 bytes from the luminosity registers. Propagates OSError 
        to trigger the "Rosetta Stone" error mapping (Spec 11.5) in the parent.
        """
        data = self._read_register(TSL2591_REGISTER_CHAN0_LOW, 4)
        ch0 = (data[1] << 8) | data[0]
        ch1 = (data[3] << 8) | data[2]
        return (ch0, ch1)
    
    def get_full_luminosity(self):
        """
        [Spec 4.3.9.3] Standard Sensor Payload.
        Returns a composite luminosity value scaled for MTIP SNS reports.
        Expected range: 0 to 65,535.
        """
        c0, c1 = self.get_raw_channels()
        return (c1 << 16) | c0