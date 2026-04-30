# Core 3: The Librarian (Data Persistence & Asset Management)

Welcome to **Core 3**, the dedicated data and asset management engine of the Ninelives Robotic Lego Sorter. 

While Core 0 manages real-time control (The Present) and Cores 1 & 2 analyze images (The Identity), Core 3 manages the history, business integrity, and permanent storage of the system. Operating as an isolated Multiprocessing Worker coupled with a dedicated PostgreSQL server, The Librarian ensures that no data is lost, the NVMe SSD is protected from unnecessary wear, and the high-speed vision pipelines never run out of RAM.

## 🧠 Architectural Philosophy & Mandate

The primary operational risk in a high-speed computer vision system is RAM saturation. If the camera pipeline writes 48MB/s to memory and it isn't cleared instantly, the Raspberry Pi will crash.

**The Librarian's Mandate:**
1. **Zero Blocking:** Database operations and file transfers must *never* slow down the physical sorting loop or camera ingest.
2. **RAM Hygiene:** Evacuate the `/dev/shm` RAM disk immediately using "Smart Crop" and "Trickle" network backups.
3. **Data Integrity:** A physical sort is not considered complete until the result is committed to the Database Write-Ahead Log (WAL).
4. **Source of Truth:** The Raspberry Pi acts as the high-speed active buffer; the external NAS ("Melek") holds the permanent archive.

## ⚙️ Hardware & CPU Pinning

To ensure database operations do not starve the Computer Vision processes, PostgreSQL is isolated at the OS level:
* **CPU Affinity:** The entire PostgreSQL service is strictly pinned to CPU Core 3 via `systemd` (`CPUAffinity=3`).
* **Storage Topology:** The OS and Database run exclusively on the 512GB NVMe SSD (PCIe Gen 3) for speed. 
* **Database Tuning:** Optimized for Write-Heavy / Append-Only operations. The system uses **UUID v7 (Time-Ordered)** primary keys to keep the active index tip incredibly small (~0.5MB), leaving the rest of the 8GB RAM free for image buffering.

## 🗄️ The Dual Pipelines

Core 3 manages two completely distinct data flows:

### 1. The Asset Pipeline (Images)
Uses a "Touch and Go" strategy to bypass SSD wear entirely.
* **Smart Crop:** Raw 16MP images are cropped to bounding boxes, compressed to JPEG, and saved in the RAM buffer (`/dev/shm/lego_buffer`). Raw data is immediately garbage collected.
* **Trickle Backup:** A background `rsync` daemon continuously trickles images from the RAM buffer directly to the Melek NAS every 30 seconds. Images never touch the Pi's SSD unless the network goes down.
* **Failover:** If RAM utilization exceeds 80% (e.g., network failure), Core 3 safely spills the images to the local NVMe SSD and marks them for pending sync.

### 2. The Transaction Pipeline (Data)
Core 3 acts as the ultimate authority on machine state via a "Closed Loop" control system. It maintains the `Pending_Sort_Buffer` (Waiting Room) in its isolated memory.
* **Initialization (INIT):** When Core 0 tells a pneumatic bin to fire, it sends an `INIT` payload to Core 3. Core 3 logs that the piece is on the belt.
* **Reconciliation (RESULT):** When the physical sorter (Pico 3) reports back (Sorted, Missed, or Lost), Core 0 forwards the `RESULT` to Core 3. Core 3 marries the result to the initial intent, executes a batch `COPY` insert into PostgreSQL, and removes the item from the buffer.
* **Crash Resilience:** Because the state lives in Core 3, if the main logic engine (Core 0) crashes mid-sort, Core 3 flushes all pending items to the database as `CRASH_UNKNOWN` to guarantee zero inventory loss.

## 🚦 Inter-Process Communication (IPC Queues)

Core 3 listens to specific multiprocessing queues to decouple its slow I/O tasks from the high-speed robot:

* **`Q4: Sort_Lifecycle_IPC_Queue`**: The primary data feed. Receives the `INIT` and `RESULT` payloads from Core 0. Core 3 monitors the depth of this queue to signal **Backpressure**. If the queue exceeds 50 items, Core 3 forces the physical conveyor belt to pause until the database catches up.
* **`Q5: Training_Image_IPC_Queue` (Low Priority)**: Receives pointers from Core 2 (The Appraiser) containing identified part numbers. Core 3 lazily processes these, renaming the cropped images to their exact LEGO part number (e.g., `3001-uuid.jpg`) and uploading them for future Neural Network training.