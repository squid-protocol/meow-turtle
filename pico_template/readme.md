# Pico Template: The "Limb" Firmware (Ninelives Shell)

This directory serves as the master blueprint for all Raspberry Pi Pico 2 (RP2350) microcontrollers in the Ninelives system. 

Built on bare-metal MicroPython, this firmware is designed for **Industrial Reliability**. It assumes that power will be cut unexpectedly, RS-485 lines will be noisy, and code will eventually crash. To survive this, it implements an "Unbrickable by Design" architecture featuring a multi-stage bootloader, Dual-Core Symmetric Multiprocessing (SMP), and automatic rollback recovery.

## 🧠 Dual-Core Architecture

To guarantee microsecond-level motor timing while simultaneously handling heavy UART communication, the firmware strictly divides labor between the two processor cores:

* **Core 0 ("The Clerk"):** Handles all management. It runs the MTIP communication parser (`meowprotocol.py`), processes incoming configuration commands, manages the OTA updates, feeds the hardware Watchdog, and pushes asynchronous telemetry/events to the RP5 Brain.
* **Core 1 ("The Machinist"):** Dedicated entirely to real-time physics. It runs an uninterrupted, high-speed loop (>1kHz) that polls sensors via PIO/I2C, controls motor PWM ramping, and verifies actuator states. **Garbage Collection is strictly forbidden on this core** to prevent motor stutter.

## 📁 File Structure & Roles

### Root Level
* **`boot.py` (The Guard Dog):** Runs before the main application. Clamps all motor pins to ground within milliseconds to prevent "Startup Lurch." It manages the 9-Life counter, detecting crash loops and triggering `.bak` file restorations if the main app fails to boot.
* **`app.py`:** The main kernel. Instantiates the Actuator/Sensor HALs, initializes the Core 1 physics thread, and enters the Core 0 event loop.
* **`config.json`:** The "Single Source of Truth." Contains all hardware pin mappings, PWM frequencies, debounce limits, and actuator calibration settings.

### `lib/` (Hardware Abstraction & Services)
* **`actuators.py` & `sensors.py`:** The Hardware Abstraction Layers (HAL). These translate logical intent (e.g., "Set Conveyor to 50%") into physical voltages, complete with brownout-preventing soft-start ramping.
* **`meowprotocol.py`:** The MTIP v1.01 protocol handler. Uses an "Elastic Loop" with Greedy Ingestion to process packet storms and prioritizes the `0x48` Safety Channel.
* **`ota.py`:** The Over-The-Air update manager. Uses a simulated A/B bank system (writing to `.new` files and checking SHA-256 hashes) before atomically swapping system files to prevent corruption during mid-update power loss.
* **`pio_programs.py`:** Contains the assembly instructions for the PIO state machines, allowing high-speed tachometer counting without putting any load on the CPU.
* **`diagnostics.py`:** Scans local file headers to generate a System Manifest, allowing the RP5 to audit the exact firmware versions running on the Pico without flashing.
* **Hardware Drivers:** Specialized scripts for specific components (`bldc_driver.py`, `mpu6050.py` for gyros, `tsl2591.py` for light sensors, `vibration_driver.py`).

## 🛡️ Industrial Safeguards

1. **The Closed-Loop Bridge:** The system does not use "Open Loop" control. When commanded ON, an actuator enters `VERIFYING` state. Core 1 waits for physical sensor feedback (e.g., a tachometer pulse or gyro vibration) to prove the motor is actually moving before transitioning to `CONFIRMED_ON`. If it doesn't move, it triggers a `FAULT_STALL` Emergency Stop.
2. **Ghost Mode Fallback:** If `boot.py` detects 0 lives remaining (or extreme file corruption), it bypasses `app.py` entirely and loads a minimal, RAM-resident rescue environment on a hardcoded ID. This guarantees the RP5 can always find and re-flash the board.
3. **Cross-Core Watchdog (Dead Man's Switch):** Core 0 feeds the hardware Watchdog Timer, but it will *only* do so if Core 1 is actively proving it is alive via a shared-memory heartbeat. If either core freezes, the hardware forces a full system reboot.