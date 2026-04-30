# Meow Turtle: Ninelives Robotic Lego Sorter

An industrial-grade, distributed Symmetric Multiprocessing (SMP) sorting framework designed for high-speed, high-precision singulation and cataloging of small parts. The Ninelives architecture abandons traditional reactive control loops, instead operating on a "Robot-First" philosophy where a central Linux brain manages a live Digital Twin, and decentralized microcontrollers execute microsecond-perfect physical reflexes.

## 🧠 Core Architecture

The system is split into a "Brain" (Raspberry Pi 5) and multiple "Limbs" (Raspberry Pi Pico 2 / RP2350s).

* **The Digital Twin (Core 0):** The RP5 Logic Engine never queries the hardware directly. It operates entirely against a real-time, memory-resident object model (the Digital Twin) that mirrors the physical state of every sensor and actuator.
* **Asynchronous MTIP Communication:** Communication over the RS-485 bus uses the Message Transfer Interface Protocol (MTIP), featuring an elastic loop that handles packet storms with Greedy Ingestion. Critical safety alarms (0x48) bypass standard queues to guarantee microsecond-level Emergency Stops.
* **Spatial Synchronization (Time-as-Distance):** Standard wall-clock time is unreliable due to belt friction and load variations. Ninelives uses high-speed PIO tachometry to count physical motor pulses, making sorting decisions strictly based on physical distance traveled (`mm_per_pulse`), rendering the system completely speed-invariant.
* **Industrial Hardening:** Features Phase-Locked Garbage Collection to prevent motor stutters, Bootloader Safety Lockouts to prevent startup lurches, and a "Closed-Loop Bridge" that demands physical sensor verification for every actuator state change.

## 📁 Repository Structure

The repository is organized by functional processing cores and hardware nodes:

### The Brain (RP5 Controller)
* **`core0 - Commander`/**: The "Self-Aware" System Coordinator. Runs the asyncio Python logic loop, maintains the Digital Twin, and manages the Switchboard for the RS-485 fleet.
* **`core1 - Surveyor`/**: The Vision Process node. Analyzes images, identifies parts, and pushes high-bandwidth results to the internal Synapse Bus. 
* **`core3 - Librarian`/**: The Database Process node. Manages inventory databases, kit lists, and order fulfillment tracking.

### The Limbs (RP2350 Gatekeepers)
* **`pico1`/ (The Loader):** Manages bulk material handling. Controls the tipper motors, vibrating shaker motors, and pneumatic arms to normalize the input flow of pieces.
* **`pico2`/ (The Gatekeeper):** Handles high-precision sensing. Uses TSL2591 light sensors as high-speed beam breaks to assign "Spatial Birth Certificates" (exact global pulse counts) to incoming parts.
* **`pico3`/ (Mission Control / Distributor):** Executes precision sorting. Controls the main BLDC conveyor motor and fires the specific functional air solenoids (e.g., Bins 1-10) using Position-Fused targeting.
* **`pico_template`/**: The base firmware environment for any new limb. Includes the unbrickable `boot.py` guard dog, standard HAL libraries, and the OTA update manager.

## 🛡️ Safety & "Unbrickable" Design

* **OTA Atomic Swaps & Rollbacks:** Firmware updates use a simulated A/B bank. Bad code triggers an automatic rollback to the last known `.bak` "Golden Image" after 3 failed boot attempts.
* **Ghost Mode:** If a Pico's filesystem is completely corrupted, it falls back to a RAM-resident "Ghost" rescue state on a hardcoded ID, allowing the RP5 to force-flash a new filesystem.
* **Active Thermal Throttling:** The RP5 monitors chassis temperatures. It proactively slows down vibrators and conveyors (Tier 1) to reduce electrical friction before eventually forcing a hardware lockout (Tier 4) if temperatures exceed 75°C.
* **Autonomous Escalation:** If a Pico detects a mechanical stall, it autonomously cuts power in < 2ms and escalates a CRITICAL alarm to the RP5, preventing motor burnout without waiting for network permission.