# Ninelives: Lightweight Distributed SCADA Middleware
*(Featuring the "Meow Turtle" Reference Implementation)*

Ninelives is an industrial-grade, fault-tolerant SCADA (Supervisory Control and Data Acquisition) middleware built for **Constructors**. 

Traditional open-source SCADA projects (like FUXA, PyScada, or Scada-LTS) assume you are an *Integrator*—someone who already dropped $10,000 on proprietary Siemens or Allen-Bradley PLCs and just needs a pretty web dashboard. They rely on heavy Ethernet protocols like OPC-UA or standard Modbus, and often require Windows Servers and extensive IT budget approvals.

**Ninelives bridges the web directly to bare copper.** It is a full-stack framework designed to let you build distributed, highly deterministic physical automation networks using $4 microcontrollers (Raspberry Pi Picos) and a central Linux brain (Raspberry Pi 5), entirely bypassing enterprise IT friction. 

If ROS (Robot Operating System) is a massive, multi-lane highway for gigabytes of LIDAR and 4K video, Ninelives is a hyper-fast, low-latency bullet train for physical hardware execution.

## ⚖️ System Limits & Scalability
Ninelives trades high bandwidth for extreme, deterministic reliability over bare-metal serial connections. 
* **The Bandwidth Limit:** The system runs over RS-485 at 115,200 baud, giving a maximum theoretical throughput of ~11.5 Kilobytes per second. This is strictly for telemetry, state synchronization, and hardware commands. Heavy compute (like AI vision) must remain on the host RP5.
* **The Node Topology:** A single RP5 "Brain" can comfortably manage an RS-485 bus of 4 to 8 Pico "Limbs". 
* **The Component Density:** Each Pico can reliably manage roughly 10 physical hardware abstractions (e.g., 2 I2C sensors, 4 pneumatic solenoids, 2 PWM vibratory motors, 2 digital limit switches) at microsecond precision.
* **Horizontal Scaling:** Need 100 actuators? You don't overload the bus. You simply add a second RP5 Brain to the network, commanding its own dedicated RS-485 fleet of Picos.

## 🧠 The Ninelives Core Architecture
The framework abandons traditional reactive control loops. Instead, it operates on a "Split-Brain" philosophy:

* **The Passive Digital Twin (Host):** The RP5 Logic Engine never queries the hardware directly. It operates entirely against a real-time, memory-resident object model (the Digital Twin) that passively ingests telemetry and mirrors the physical reality of the factory floor.
* **The MTIP Protocol (Transport):** Communication utilizes the custom Message Transfer Interface Protocol (MTIP). It features payload deduplication, CRC-16 checksums, and prioritized queueing. Critical safety alarms (0x48) bypass standard command queues to guarantee sub-second system-wide Emergency Stops.
* **"Humble" Firmware (The Limbs):** The Pico firmware (`app.py`) is completely generalized. It has zero business logic. It reads a `config.json` file, turns pins HIGH/LOW, applies EMA (Exponential Moving Average) filters to sensor noise, and manages physical soft-starts to prevent electrical brownouts. 
* **Industrial Hardening:** The framework features Phase-Locked Garbage Collection to prevent motor stutters, atomic OTA (Over-The-Air) flash updates with automatic rollback on boot failure, and a "Closed-Loop Verification" system that uses fuzzy logic (Confidence Decay) to demand physical sensor proof for every actuator state change.

---

## 🐢 Reference Implementation: "Meow Turtle" Lego Sorter
To stress-test the Ninelives framework, this repository includes the codebase for **Meow Turtle**: a high-speed, high-precision robotic sorting machine for singulating and cataloging small Lego parts.

Instead of writing a monolith, the sorting logic is built entirely on top of the generic Ninelives API.

### The Brain (RP5 Controller)
* **`core0 - Commander`/**: The "Self-Aware" System Coordinator. Runs the asyncio Python logic loop, maintains the Digital Twin, and serves the NiceGUI browser-based control panel.
* **`core1 - Surveyor`/**: The Vision Process node. Analyzes images, identifies parts, and pushes high-bandwidth AI results to the internal Synapse Bus (completely isolated from the RS-485 hardware bus).
* **`core3 - Librarian`/**: The Database Process node. Manages inventory databases, kit lists, and order fulfillment tracking.

### The Limbs (RP2350 Gatekeepers)
Because Ninelives relies on a generalized hardware layer, these nodes run identical `app.py` firmware. Their roles are defined entirely by their local `config.json`:
* **`pico1`/ (The Loader):** Manages bulk material handling. Controls tipper motors and vibrating shakers to normalize the input flow of pieces.
* **`pico2`/ (The Gatekeeper):** Handles high-precision sensing. Uses PIO state machines and TSL2591 light sensors as high-speed beam breaks to assign "Spatial Birth Certificates" (exact global pulse counts) to incoming parts.
* **`pico3`/ (The Distributor):** Executes precision sorting. Controls the main BLDC conveyor motor and fires specific functional air solenoids (Bins 1-10). 
* **`pico_template`/**: The base firmware environment for any new limb on the network.

### ⏱️ Time-as-Distance Routing
To achieve industrial sorting precision, Meow Turtle does not use standard wall-clock time, which is vulnerable to belt friction and mechanical load variations. Instead, it utilizes Ninelives' PIO pulse-counting abstractions. By tracking physical motor tachometer pulses, sorting decisions are made strictly based on physical distance traveled (`mm_per_pulse`), rendering the entire system completely speed-invariant.