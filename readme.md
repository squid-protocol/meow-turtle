# [cite_start]Meow Turtle: Ninelives Robotic Lego Sorter [cite: 2, 2058]

[cite_start]An industrial-grade, distributed Symmetric Multiprocessing (SMP) sorting framework designed for high-speed, high-precision singulation and cataloging of small parts. [cite: 5, 2063, 3083, 3175] [cite_start]The Ninelives architecture abandons traditional reactive control loops, instead operating on a "Robot-First" philosophy where a central Linux brain manages a live Digital Twin, and decentralized microcontrollers execute microsecond-perfect physical reflexes. [cite: 2201, 2202, 2206, 2207]

## 🧠 Core Architecture

[cite_start]The system is split into a "Brain" (Raspberry Pi 5) and multiple "Limbs" (Raspberry Pi Pico 2 / RP2350s). [cite: 3, 2771, 3221]

* [cite_start]**The Digital Twin (Core 0):** The RP5 Logic Engine never queries the hardware directly. [cite: 2212] [cite_start]It operates entirely against a real-time, memory-resident object model (the Digital Twin) that mirrors the physical state of every sensor and actuator. [cite: 2203, 2211]
* [cite_start]**Asynchronous MTIP Communication:** Communication over the RS-485 bus uses the Message Transfer Interface Protocol (MTIP), featuring an elastic loop that handles packet storms with Greedy Ingestion. [cite: 374, 380, 384, 2330, 2333] [cite_start]Critical safety alarms (0x48) bypass standard queues to guarantee microsecond-level Emergency Stops. [cite: 407, 408, 431, 2355]
* [cite_start]**Spatial Synchronization (Time-as-Distance):** Standard wall-clock time is unreliable due to belt friction and load variations. [cite: 1656] [cite_start]Ninelives uses high-speed PIO tachometry to count physical motor pulses, making sorting decisions strictly based on physical distance traveled ($mm\_per\_pulse$), rendering the system completely speed-invariant. [cite: 1657, 1660, 3283]
* [cite_start]**Industrial Hardening:** Features Phase-Locked Garbage Collection to prevent motor stutters, Bootloader Safety Lockouts to prevent startup lurches, and a "Closed-Loop Bridge" that demands physical sensor verification for every actuator state change. [cite: 289-293, 336, 338, 339, 1987, 1988]

## 📁 Repository Structure

The repository is organized by functional processing cores and hardware nodes:

### The Brain (RP5 Controller)
* [cite_start]**`core0 - Commander`/**: The "Self-Aware" System Coordinator. [cite: 2057] [cite_start]Runs the asyncio Python logic loop, maintains the Digital Twin, and manages the Switchboard for the RS-485 fleet. [cite: 2217, 2240, 2244, 2251]
* [cite_start]**`core1 - Surveyor`/**: The Vision Process node. [cite: 3064] [cite_start]Analyzes images, identifies parts, and pushes high-bandwidth results to the internal Synapse Bus. [cite: 3068, 3073] 
* [cite_start]**`core3 - Librarian`/**: The Database Process node. [cite: 3064] [cite_start]Manages inventory databases, kit lists, and order fulfillment tracking. [cite: 3070, 3097, 3100]

### The Limbs (RP2350 Gatekeepers)
* [cite_start]**`pico1`/ (The Loader):** Manages bulk material handling. [cite: 2930] [cite_start]Controls the tipper motors, vibrating shaker motors, and pneumatic arms to normalize the input flow of pieces. [cite: 2932, 2933, 2934]
* [cite_start]**`pico2`/ (The Gatekeeper):** Handles high-precision sensing. [cite: 2939] [cite_start]Uses TSL2591 light sensors as high-speed beam breaks to assign "Spatial Birth Certificates" (exact global pulse counts) to incoming parts. [cite: 2940, 2944]
* [cite_start]**`pico3`/ (Mission Control / Distributor):** Executes precision sorting. [cite: 2946] [cite_start]Controls the main BLDC conveyor motor and fires the specific functional air solenoids (e.g., Bins 1-10) using Position-Fused targeting. [cite: 2947, 2948, 2949]
* [cite_start]**`pico_template`/**: The base firmware environment for any new limb. [cite: 996] [cite_start]Includes the unbrickable `boot.py` guard dog, standard HAL libraries, and the OTA update manager. [cite: 998, 1005, 1006, 1860, 1861]

## 🛡️ Safety & "Unbrickable" Design

* [cite_start]**OTA Atomic Swaps & Rollbacks:** Firmware updates use a simulated A/B bank. [cite: 854] [cite_start]Bad code triggers an automatic rollback to the last known `.bak` "Golden Image" after 3 failed boot attempts. [cite: 1961, 1966-1972]
* [cite_start]**Ghost Mode:** If a Pico's filesystem is completely corrupted, it falls back to a RAM-resident "Ghost" rescue state on a hardcoded ID, allowing the RP5 to force-flash a new filesystem. [cite: 983, 987, 989, 992]
* **Active Thermal Throttling:** The RP5 monitors chassis temperatures. [cite: 3224] It proactively slows down vibrators and conveyors (Tier 1) to reduce electrical friction before eventually forcing a hardware lockout (Tier 4) if temperatures exceed 75°C. [cite: 1272, 1273, 3228, 3229]
* [cite_start]**Autonomous Escalation:** If a Pico detects a mechanical stall, it autonomously cuts power in $< 2ms$ and escalates a CRITICAL alarm to the RP5, preventing motor burnout without waiting for network permission. [cite: 3245, 3249, 3250, 3263]