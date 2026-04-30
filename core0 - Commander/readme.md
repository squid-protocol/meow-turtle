# Core 0: The System Coordinator ("The Brain")

Welcome to **Core 0**, the central nervous system of the Ninelives Robotic Lego Sorter (running on the Raspberry Pi 5). 

Unlike traditional reactive controllers that fire blind commands and assume compliance, Core 0 operates on a **"Self-Aware" Digital Twin** model. It maintains an absolute, millisecond-accurate reflection of physical reality within its memory. It coordinates high-level logic, manages the asynchronous operator dashboard, and enforces hardware accountability across the distributed microcontroller fleet.

## 🧠 Core Philosophy & Goals

1. **State Synchronicity (The Digital Twin):** The UI and logic engines *never* query hardware directly. They interact exclusively with `GLOBAL_TWIN`, an in-memory object model kept perfectly in sync via aggressive active polling (0.25s heartbeat).
2. **Asynchronous Orchestration:** Utilizes Python `asyncio` to manage high-latency operations (GUI rendering, database writes) without ever blocking the critical machine reflexes handling RS-485 communications.
3. **Hardware Accountability:** Enforces a strict "Verification Spectrum". It distinguishes between intent (Commanded ON) and reality (Verified ON), waiting for physical sensors to prove a state change before continuing logic.
4. **Transparent Observability:** No silent failures. Every state change, packet skip, or error is routed through the asynchronous Telemetry Router ("Flight Recorder") to both the UI and rotated log files.

## 📂 Directory Structure

### Entry Points & UI
* **`app.py`**: The main indestructible entry point. Initializes the logging bridge, boots the `SystemCoordinator` as a background task, and serves the NiceGUI dashboard.
* **`gui.py`**: The high-density operator dashboard (HMI) optimized for vertical touchscreens. Uses delta-state updates to visualize the Digital Twin without CPU thrashing.
* **`safe_mode_gui.py`**: The "Lifeboat" fallback UI. Loads automatically if the main application crashes due to configuration poisoning, ensuring the operator always has a screen.

### `config/` (System Configuration)
* `calibration.json`: Persistent spatial resolution constants (e.g., `mm_per_pulse`), crucial for the speed-invariant sorting logic.
* `profiles.json`: Operational "Recipes" (e.g., *Scan New Bucket*, *Precision Sort*) that reconfigure the machine without code changes.
* `debug.py` & `settings.py`: Global master switches and serial port mappings.

### `lib/` (The Logic Engine)
* **`digital_twin.py`**: The hierarchical singleton object model representing the Host, Limbs (Picos), Sensors, and Actuators.
* **`switchboard.py` & `meowprotocol.py`**: The MTIP v1.02 communications layer. Handles Elastic Loop processing, hardware handshakes, and "Piggyback ACKing" over the RS-485 bus to prevent network storms.
* **`alarm_manager.py` & `safety_tasks.py`**: Maps hardware-level faults to RP5 safety gradients (Warning, Pause, Critical E-Stop).
* **`telemetry_router.py` & `rp5_logger.py`**: Manages log deduplication, Bayesian GUI filtering, and daily file rotation to prevent disk exhaustion.
* **`coordinator.py` & `logic_engine.py`**: The "Boss" process that pops events from the queue, evaluates state transitions, and dispatches commands to the fleet.

### Auxillary Folders
* **`utilities/`**: Contains fleet management scripts like `mass_ota_flasher.py` for pushing firmware updates.
* **`logs/`**: Local daily rotated `.log` files (Excluded via `.gitignore`).
* **`checklists/` & `txt/`**: Development notes and modular spec breakdowns.

## 🚦 Communication Highways

Core 0 acts as the central hub for two distinct traffic networks:
1. **Highway 1 (The Nervous System):** Serial UART + MTIP protocol communicating directly with the bare-metal Pico Limbs. High frequency, low latency, handling commands and telemetry.
2. **Highway 2 (The Synapse Bus):** Inter-Process Communication (IPC) linking Core 0 to Core 1 (Vision/Surveyor) and Core 3 (Database/Librarian). High bandwidth, handling complex JSON and image payloads.

## 🛡️ Industrial Resilience

* **Indestructible Loop Pattern:** Critical `while True` logic loops are wrapped in broad try/except blocks to catch, log, and gracefully retry on exceptions rather than crashing the thread.
* **Active Thermal Interlock:** Core 0 monitors Pico chassis temperatures. It implements tiered workload throttling to actively cool down hardware, transitioning to a full safety lock-out if remote temperatures exceed 75°C.
* **Autonomous Escalation Coordination:** If a Pico limb autonomously kills its own motor due to a physical jam, Core 0 intercepts the `0x48` ALARM and globally pauses the rest of the machine to prevent a cascading pile-up.