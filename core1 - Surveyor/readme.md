# Core 1: The Surveyor (Vision & Feature Extraction)

Welcome to **Core 1**, the dedicated vision processing engine of the Ninelives Robotic Lego Sorter. 

Running on an assigned CPU core of the Raspberry Pi 5 via Affinity Pinning, the Surveyor prioritizes speed and geometric interpretability over "Black Box" Neural Networks. It processes synchronized frames from the 4-Camera "CamHat", extracting physical metrics to match against a synthetic "Digital Twin" database generated in Blender.

Neural Networks are only utilized as a fallback for "Tricky Pieces," allowing the system to maintain a high-throughput sorting rate of ~1 piece per second.

## 🧠 Cache-Optimized Database Architecture

To maximize L1 Cache efficiency and achieve sub-100ms identification times, the search space is split into strictly separated, optimized databases:

* **The Color Palette:** ~100 LAB Color Histograms mapped to 0-255 integers (uint8). At ~4.5 KB, this fits entirely in the L1 Cache, reducing memory usage by 75% compared to floats.
* **The Mold Index:** ~15,000 unique geometric signatures (ignoring color) utilizing 16-bit half-floats. While the total database is ~3.5 MB, the top ~240 most common molds (~55 KB) reside permanently in the L1 Cache.
* **The SKU Index:** A cross-reference table mapping `(ColorID, MoldID) -> PartID`. This prevents the system from wasting CPU cycles searching for physically impossible combinations (e.g., a "Red Tree").

## 👁️ Feature Extraction Metrics

The Surveyor extracts 29 geometric and texture metrics per camera view to establish a unique fingerprint:

* **Macro (Size & Volume):** Calibrated Area, Bounding Box Fill, and Quaternary Volume (a Pseudo-3D-Mass calculated across all 4 views).
* **Shape (Contour):** Circularity, Convexity/Solidity, Rectangularity, and Center-Mass Shift.
* **Topology:** Euler Number (Hole detection) and Hole Area Ratio.
* **Surface & Texture (The "Stud" Check):** FAST Corner Density (high for Technic/Studs), LBP Entropy, and Color Entropy (high for prints/stickers).
* **Frequency Domain:** FFT Contour Signatures to capture the overarching "shape vibe" (e.g., Star-shape vs. Blob-shape).

## ⚙️ The Search Pipeline

1. **Color Variance Check:** Assesses color across the 4 cameras. Low variance triggers standard Average Color matching; high variance triggers a raw histogram "Sticker Mode" search.
2. **Global Geometry Pre-Filters:** Rapidly discards impossible molds before deep matching.
    * *Topology:* If any camera sees a hole (Euler < 1), instantly discard all solid molds (e.g., standard bricks).
    * *Visual Mass:* Compares the sum of the 4 live areas against the reference to rule out volume mismatches.
    * *Elongation:* Uses Max Aspect Ratio to discard compact shapes if a long beam is detected.
3. **4-View Geometry Match:** Rotates the incoming 4-camera vector around the reference candidate rings to find the `Best_Mold_ID`.

## 🤝 Inter-Process Communication (The SHM Handoff)

Core 1 passes data to Core 2 (The Specialist) and Core 3 (The Librarian) using atomic file renames in the `/dev/shm` RAM disk, completely avoiding read/write race conditions.

1. **Write Phase:** Core 1 dumps the raw uncompressed bitmap to `/dev/shm/img_TIMESTAMP.tmp`.
2. **Flag Phase (The Decision):** * If standard: Renames to `.ready` (Low Priority). Core 2 will compress and archive it when idle.
    * If tricky (Confidence < Threshold): Renames to `.tricky` (Critical Priority). Core 2 interrupts background tasks to run Neural Net inference (MobileNetV3) immediately.
3. **Lock & Cleanup Phase:** Core 2 renames the file to `.lock` while processing, then deletes it to free RAM.

*(Heuristic "Tricky" triggers include Chrome/Metallic specular spikes, Trans-Clear edge bleed-through, complex Foliage topology, and Minifigure color entropy.)*