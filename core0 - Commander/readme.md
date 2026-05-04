# Core 0: The Commander (Ninelives SCADA Host)

Welcome to **Core 0**, the central nervous system of the Ninelives SCADA middleware. 

Designed to run on a Raspberry Pi 5 (or any Linux machine with an RS-485 interface), Core 0 acts as the "Brain" of the distributed network. While the Pico microcontrollers on the edge are designed to be "humble" and reactionary, Core 0 is hyper-aware. It maintains the master Digital Twin, serves the web-based HMI dashboard via NiceGUI (bypassing corporate IT firewalls), and coordinates high-level logic across the fleet.

Currently, this Core 0 instance is loaded with the **"Meow Turtle" Reference Implementation**—a high-speed, high-precision robotic sorting machine for singulating and cataloging small Lego parts.

## 🧠 Core Philosophy & Architecture

Unlike traditional reactive controllers that fire blind commands over a network and simply assume compliance, Core 0 operates on a strict **"Self-Aware" Digital Twin** model.

1. **State Synchronicity:** The UI and logic engines *never* query physical hardware directly. They interact exclusively with `GLOBAL_TWIN`, an in-memory object model kept perfectly in sync via aggressive background polling.
2. **Asynchronous Orchestration:** Utilizes Python `asyncio` to manage high-latency operations (GUI rendering, database writes, user input) without ever blocking the critical, deterministic machine reflexes handling the RS-485 bus.
3. **Hardware Accountability:** Enforces a strict "Verification Spectrum." Core 0 distinguishes between intent (Commanded ON) and reality (Verified ON), waiting for physical sensors on the edge to prove a state change via Fuzzy Logic confidence scores before continuing the logic sequence.
4. **Transparent Observability:** No silent failures. Every state change, packet skip, or E-Stop is routed through the asynchronous Telemetry Router ("Flight Recorder") to both the UI and daily rotated log files.

## 📁 Directory Structure & Roles

Because this repository contains both the universal framework and a specific implementation, the files are separated by function:

### 🚀 Entry Points & HMI (Human-Machine Interface)
* **`app.py`:** The indestructible entry point. Initializes the logging bridge, boots the `SystemCoordinator` as a background task, and serves the NiceGUI dashboard.
* **`gui.py`:** The high-density operator dashboard. Optimized for vertical touchscreens, it uses delta-state updates to visualize the Digital Twin in real-time without CPU thrashing.
* **`safe_mode_gui.py`:** The "Lifeboat." Loads automatically if the main application crashes due to configuration poisoning, ensuring the operator always has a screen to diagnose the failure.

### ⚙️ `config/` (System Configuration)
* `profiles.json`: Operational "Recipes" (e.g., *Scan New Bucket*, *Precision Sort*) that reconfigure the machine's behavior without requiring code changes.
* `calibration.json`: Persistent spatial resolution constants (e.g., `mm_per_pulse`). Crucial for the speed-invariant "Time-as-Distance" sorting logic used by the Lego Sorter.
* `debug.py` & `settings.py`: Global master switches, verbosity filters, and serial port mappings.

### 🧠 `lib/` (The Middleware & Logic Engine)
* **The Ninelives Framework (Universal):**
  * `digital_twin.py`: The hierarchical singleton object model representing the Host, Limbs, Sensors, and Actuators.
  * `switchboard.py` & `protocol_parser.py`: The MTIP v1.02 communications layer. Handles Elastic Loop processing and payload deduplication over the RS-485 bus.
  * `alarm_manager.py` & `safety_tasks.py`: Intercepts hardware-level faults from the Picos and maps them to RP5 safety gradients (Warning, Pause, Critical E-Stop).
  * `telemetry_router.py` & `rp5_logger.py`: Manages log deduplication and daily file rotation to prevent SD card exhaustion.
* **The "Meow Turtle" Implementation (Lego Sorter Specific):**
  * `coordinator.py` & `logic_engine.py`: The specific business logic that pops events from the queue, evaluates Lego sorting state transitions, and dispatches commands.
  * `job_manager.py`: Handles atomic handshakes and the execution of specific sorting tasks.

### 🔧 Auxillary Folders
* **`utilities/`**: Contains fleet management scripts like `mass_ota_flasher.py` for pushing atomic firmware updates over the RS-485 bus to the Limbs.
* **`logs/`**: Local daily rotated `.log` files.
* **`checklists/` & `txt/`**: Development notes, raw specs, and modular architectural breakdowns.

## 🚦 Communication Highways

Core 0 acts as the central router for two distinctly separated traffic networks:

1. **Highway 1 (The Nervous System):** Serial UART utilizing the deterministic MTIP protocol. Communicates directly with the bare-metal Pico Limbs. Low bandwidth (~11.5 KB/s), but extreme reliability and low latency for hardware commands and safety interlocks.
2. **Highway 2 (The Synapse Bus):** Inter-Process Communication (IPC) linking Core 0 to external heavy-compute nodes like Core 1 (Vision/AI) and Core 3 (Database). High bandwidth, handling complex JSON arrays and image payloads without lagging the physical hardware loop.

## 🛡️ Industrial Resilience

* **The Indestructible Loop:** Critical `while True` logic loops are wrapped in broad try/except blocks to catch, log, and gracefully retry on exceptions rather than crashing the primary application thread.
* **Active Thermal Interlock:** Core 0 passively monitors Pico chassis temperatures. It implements tiered workload throttling to actively cool down hardware, transitioning to a full, system-wide safety lock-out if remote silicon temperatures exceed safe thresholds.
* **Autonomous Escalation Coordination:** If a Pico limb autonomously kills its own motor due to a physical jam, Core 0 intercepts the asynchronous `0x48` ALARM and globally pauses the rest of the machine to prevent a cascading physical pile-up.