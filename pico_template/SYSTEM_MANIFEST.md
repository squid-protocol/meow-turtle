# NINELIVES SYSTEM MANIFEST

## Forensic Logic Audit

| File | Object | Specs | Lines | Summary |
| :--- | :--- | :--- | :--- | :--- |
| app.py | 📄 app.py | S4.0 | 1038 | [Spec 4.0] Communication & Command Architecture (MTIP v1.02). |
|  | 🏛️ LogFallback | S14.1 | 26 | [Spec 14.1] Safety Telemetry & Logging Strategy. |
|  |   └─ 🛠️ info | S14.1.1 | 3 | [Spec 14.1.1] Fallback info output to console. |
|  |   └─ 🛠️ warn | S14.1.1 | 3 | [Spec 14.1.1] Fallback warning output to console. |
|  |   └─ 🛠️ error | S14.1.1 | 3 | [Spec 14.1.1] Fallback error output to console. |
|  |   └─ 🛠️ crit | S14.1.1 | 3 | [Spec 14.1.1] Fallback critical output to console. |
|  |   └─ 🛠️ debug | S14.1.1 | 3 | [Spec 14.1.1] Fallback debug output to console. |
|  | 🔧 save_config_atomic | S9.9 | 73 | [Spec 9.9] Flash Write Hygiene (The "Blind Spot"). |
|  | 🔧 refill_lives | S1.0 | 19 | [Spec 1.0] Core Philosophy: "Unbrickable by Design". |
|  | 🔧 clear_boot_attempts | S15.2 | 14 | [Spec 15.2] Automatic Rollback Logic. |
|  | 🔧 get_cpu_temp | S9.19 | 11 | [Spec 9.19] Active Thermal Safety & Interlock. |
|  | 🔧 get_vsys_voltage | S9.4 | 11 | [Spec 9.4] "Death Gasp" Telemetry (Brownout Handling). |
|  | 🔧 check_brownout | S9.4 | 22 | [Spec 9.4] Industrial Robustness: Brownout Protocol. |
|  | 🔧 build_status_string | S7.0 | 53 | [Spec 7.0] Status & Health Protocol (STS). |
|  | 🔧 send_reliable | S4.3.6 | 23 | [Spec 4.3.6] Ack-Back & Reliability Strategy. |
|  | 🔧 core1_task | S2.1 | 109 | [Spec 2.1] Core 1: The Machinist (Real-Time Role). |
|  | 🔧 process_packet | S4.3.1.1.A | 296 | [Spec 4.3.1.1.A] Communication Logic Engine (The Clerk). |
|  | 🔧 main | S2.1 | 259 | [Spec 2.1] Core 0: The Clerk (Management Role). |
| boot.py | 📄 boot.py | S3.0 | 626 | [Spec 3.0] Bootloader Subsystem. |
|  | 🏛️ LogFallback | S14.1 | 26 | [Spec 14.1] Safety Telemetry & Logging Strategy. |
|  |   └─ 🛠️ info | S14.1.1 | 3 | [Spec 14.1.1] Fallback info output to console. |
|  |   └─ 🛠️ warn | S14.1.1 | 3 | [Spec 14.1.1] Fallback warning output to console. |
|  |   └─ 🛠️ error | S14.1.1 | 3 | [Spec 14.1.1] Fallback error output to console. |
|  |   └─ 🛠️ crit | S14.1.1 | 3 | [Spec 14.1.1] Fallback critical output to console. |
|  |   └─ 🛠️ debug | S14.1.1 | 3 | [Spec 14.1.1] Fallback debug output to console. |
|  | 🔧 perform_safety_lockout | S3.2 | 14 | [Spec 3.2] Bootloader Safety Lockout (Electrical Clamping). |
|  | 🔧 cleanup_temp_files | S9.8 | 12 | [Spec 9.8] Flash Hygiene (Disk Exhaustion Prevention). |
|  | 🔧 check_crash_log | S12.6 | 15 | [Spec 12.6] Log Hygiene & Forensics. |
|  | 🔧 read_int_file | S9.3 | 14 | [Spec 9.3] Atomic Storage Utility (Read). |
|  | 🔧 write_int_file | S9.3 | 14 | [Spec 9.3] Atomic Storage Hardening (Write). |
|  | 🔧 perform_rollback | S/, S15.2, S4.3.14.5.2 | 33 | [Spec 15.2 / 4.3.14.5.2] Automatic Rollback (Boot Loop Protection). |
|  | 🔧 print_manifest | S12.2 | 11 | [Spec 12.2] Fleet Auditing & Startup Transparency. |
|  | 🔧 ghost_crc16 | S4.3.3 | 14 | [Spec 4.3.3] CRC-16-CCITT implementation. |
|  | 🔧 ghost_frame_packet | S4.3.3 | 20 | [Spec 4.3.3] Message Formatting (Wire Format Construction). |
|  | 🏛️ GhostParser | S4.3.1.1.A | 64 | [Spec 4.3.1.1.A] Minimalist Packet Parser (Greedy Ingestion). |
|  |   └─ 🛠️ __init__ | S4.3.14.5.3 | 7 | [Spec 4.3.14.5.3] Initialization with Identity Fallback. |
|  |   └─ 🛠️ parse_stream | S4.3.1.1.A | 50 | [Spec 4.3.1.1.A] Stream Processing. |
|  | 🏛️ GhostOTAManager | S4.3.14.5.3 | 107 | [Spec 4.3.14.5.3] Ghost Mode Recovery (OTA Receiver). |
|  |   └─ 🛠️ __init__ |  | 3 | Initializes empty state for atomic flash writing. |
|  |   └─ 🛠️ start | S4.3.14.1 | 25 | [Spec 4.3.14.1] OTA Phase 1: Preparation. |
|  |   └─ 🛠️ write | S4.3.14.1 | 12 | [Spec 4.3.14.1] OTA Phase 2: Ingestion. |
|  |   └─ 🛠️ commit | S4.3.14.1 | 24 | [Spec 4.3.14.1] OTA Phase 3: Commit (Atomic Swap). |
|  |   └─ 🛠️ abort | S4.3.14.3.1 | 11 | [Spec 4.3.14.3.1] Manual OTA Session Termination. |
|  | 🔧 run_ghost_mode | S4.3.14.5.3 | 95 | [Spec 4.3.14.5.3] Ghost Mode (The Rescue Kernel). |
|  | 🔧 main | S/, S1.0, S15.0 | 89 | [Spec 1.0 / 15.0] Bootloader Logical Sequence. |
| lib/actuators.py | 📄 actuators.py | S10.1 | 509 | [Spec 10.1] Actuator Subsystem Specification Overview. |
|  | 🏛️ ActuatorManager | S10.2 | 442 | [Spec 10.2] Core Actuator Subsystem Logic. |
|  |   └─ 🛠️ __init__ | S10.6.1 | 129 | [Spec 10.6.1] API Initialization. |
|  |   └─ 🛠️ __enter__ | S10.7.6 | 3 | [Spec 10.7.6] Context Guard entry point. |
|  |   └─ 🛠️ __exit__ | S10.5 | 14 | [Spec 10.5] "Smart Exit" Protocol implementation. |
|  |   └─ 🛠️ set_target | S10.6.2 | 28 | [Spec 10.6.2] Thread-Safe Intent Update. |
|  |   └─ 🛠️ get_telemetry_string | S10.8.4 | 16 | [Spec 10.8.4] Digital Twin Telemetry Serializer. |
|  |   └─ 🛠️ safe_stop | S10.5.2 | 14 | [Spec 10.5.2] Case B: Clean Shutdown. |
|  |   └─ 🛠️ emergency_stop | S10.5.1 | 20 | [Spec 10.5.1] Case A: Emergency Stop (E-Stop). |
|  |   └─ 🛠️ update_verification | S16.0 | 81 | [Spec 16.0] Closed-Loop Bridge Architecture. |
|  |   └─ 🛠️ update | S10.4.2, S10.6.3 | 98 | [Spec 10.6.3 & 10.4.2] Core 1 High-Speed Physics Step. |
|  |   └─ 🛠️ perform_health_audit | S10.8.4, S12.0 | 14 | [Spec 10.8.4 & 12.0] Component Health Audit. |
| lib/bldc_driver.py | 📄 bldc_driver.py | S10.9 | 121 | [Spec 10.9] Specialized Driver Standards (HAL Extensions). |
|  | 🏛️ BLDCDriver | S10.9.1 | 107 | [Spec 10.9.1] The "Humble Component" Pattern. |
|  |   └─ 🛠️ __init__ | S10.9.5 | 36 | [Spec 10.9.5] Configuration Whitelisting. |
|  |   └─ 🛠️ set_speed | S10.9.2 | 25 | [Spec 10.9.2] Mandatory Interface: set_speed(value). |
|  |   └─ 🛠️ set_direction | S10.9.3 | 16 | [Spec 10.9.3] Directional & State Memory. |
|  |   └─ 🛠️ stop | S10.9.2 | 7 | [Spec 10.9.2] Mandatory Interface: stop(). |
|  |   └─ 🛠️ deinit | S10.9.2 | 13 | [Spec 10.9.2] Mandatory Interface: deinit(). |
| lib/diagnostics.py | 📄 diagnostics.py | S12.1 | 169 | [Spec 12.1] Diagnostic Version Subsystem Overview. |
|  | 🏛️ LogFallback | S14.1 | 26 | [Spec 14.1] Safety Telemetry & Logging Strategy. |
|  |   └─ 🛠️ info | S14.1.1 | 3 | [Spec 14.1.1] Fallback info output to console. |
|  |   └─ 🛠️ warn | S14.1.1 | 3 | [Spec 14.1.1] Fallback warning output to console. |
|  |   └─ 🛠️ error | S14.1.1 | 3 | [Spec 14.1.1] Fallback error output to console. |
|  |   └─ 🛠️ crit | S14.1.1 | 3 | [Spec 14.1.1] Fallback critical output to console. |
|  |   └─ 🛠️ debug | S14.1.1 | 3 | [Spec 14.1.1] Fallback debug output to console. |
|  | 🏛️ SystemManifest | S12.4.1 | 119 | [Spec 12.4.1] SystemManifest Class. |
|  |   └─ 🛠️ __init__ | S12.4.1 | 25 | [Spec 12.4.1] Initializes the manifest scanner. |
|  |   └─ 🛠️ _parse_py_header | S12.3 | 41 | [Spec 12.3] File Header Standard Scanner. |
|  |   └─ 🛠️ _parse_config | S8.1 | 13 | [Spec 8.1] Configuration Version Extraction. |
|  |   └─ 🛠️ scan | S12.4.1 | 20 | [Spec 12.4.1] Fleet Auditing Logic. |
|  |   └─ 🛠️ get_report_string | S12.5 | 10 | [Spec 12.5] Report Format. |
| lib/logging.py | 📄 logging.py | S14.0 | 119 | [Spec 14.0] Ninelives Telemetry & Logging Strategy. |
|  | 🏛️ LogManager | S14.1 | 78 | [Spec 14.1] Centralized, thread-safe log buffering engine. |
|  |   └─ 🛠️ __init__ | S14.1 | 8 | [Spec 14.1] Initializes the log queue and SMP lock. |
|  |   └─ 🛠️ _push | S14.1 | 23 | [Spec 14.1] Internal: Formats and pushes log entries to the queue. |
|  |   └─ 🛠️ has_msg | S4.3.2 | 8 | [Spec 4.3.2] Checks if the log queue contains pending messages. |
|  |   └─ 🛠️ pop | S14.1 | 9 | [Spec 14.1] Retrieves and removes the oldest log entry. |
|  |   └─ 🛠️ debug | S14.1.1 | 3 | [Spec 14.1.1] D: High-volume development data. |
|  |   └─ 🛠️ info | S14.1.1 | 3 | [Spec 14.1.1] I: Routine state changes. |
|  |   └─ 🛠️ warn | S14.1.1 | 3 | [Spec 14.1.1] W: Non-critical issues. |
|  |   └─ 🛠️ error | S14.1.1 | 3 | [Spec 14.1.1] E: Functional failures. |
|  |   └─ 🛠️ crit | S14.1.1 | 3 | [Spec 14.1.1] C: Safety failures. |
| lib/meowprotocol.py | 📄 meowprotocol.py | S4.3 | 243 | [Spec 4.3] The meowprotocol Standard (MTIP v1.02). |
|  | 🔧 crc16_ccitt | S4.3.3 | 14 | [Spec 4.3.3] Message Formatting & Integrity. |
|  | 🔧 priority_sort | S4.3.1.1.A | 18 | [Spec 4.3.1.1.A] The "Jump-the-Line" Sort. |
|  | 🔧 build_packet | S4.3.3 | 27 | [Spec 4.3.3] Wire Format Construction. |
|  | 🏛️ PacketParser | S4.3.1.1 | 118 | [Spec 4.3.1.1] Elastic Loop Processing: The RX Side. |
|  |   └─ 🛠️ __init__ | S4.3.1.1 | 6 | [Spec 4.3.1.1] Initializes the stream parser with target device ID. |
|  |   └─ 🛠️ parse_stream | S4.3.1.1.A | 54 | [Spec 4.3.1.1.A] Stage 1 & 2: Buffer Drain & Stream Parsing. |
|  |   └─ 🛠️ _decode_hex_frame | S4.3.3 | 50 | [Spec 4.3.3] Wire Format Decoding. |
| lib/mpu6050.py | 📄 mpu6050.py | S11.0 | 150 | [Spec 11.0] Sensor Subsystem Specification. |
|  | 🏛️ MPU6050 | S11.8 | 113 | [Spec 11.8] Driver Interface & Error Responsibility. |
|  |   └─ 🛠️ __init__ | S11.1 | 26 | [Spec 11.1] Sensor Subsystem Initialization. |
|  |   └─ 🛠️ _write_register |  | 3 | Internal: Direct I2C memory write. |
|  |   └─ 🛠️ _read_register |  | 3 | Internal: Direct I2C memory read. |
|  |   └─ 🛠️ ping | S9.11 | 11 | [Spec 9.11] Sensor Connectivity Hardening. |
|  |   └─ 🛠️ close | S11.4.2 | 10 | [Spec 11.4.2] Standard Cleanup Protocol. |
|  |   └─ 🛠️ get_raw_values | S11.8 | 24 | [Spec 11.8] Exception Propagation. |
|  |   └─ 🛠️ get_values | S4.3.9.3 | 23 | [Spec 4.3.9.3] Standard Sensor Payload Ranges. |
| lib/ota.py | 📄 ota.py | S4.3.14 | 202 | [Spec 4.3.14] OTA System (Over-The-Air Updates). |
|  | 🏛️ OTAManager | S4.3.14.2.2 | 160 | [Spec 4.3.14.2.2] The OTA Receiver (Gatekeeper). |
|  |   └─ 🛠️ __init__ | S4.3.14.4 | 11 | [Spec 4.3.14.4] Initializes the update session state. |
|  |   └─ 🛠️ _ensure_path | S11.3 | 19 | [Spec 11.3] Filesystem Utilities. |
|  |   └─ 🛠️ start_update | S1, S4.3.14.4, SPhase | 41 | [Spec 4.3.14.4 Phase 1] Update Handshake (START). |
|  |   └─ 🛠️ write_chunk | S2, S4.3.14.4, SPhase | 18 | [Spec 4.3.14.4 Phase 2] Update Transport (DATA). |
|  |   └─ 🛠️ verify_and_commit | S3, S4.3.14.4, SPhase | 48 | [Spec 4.3.14.4 Phase 3] Update Commit (END). |
|  |   └─ 🛠️ abort | S4.3.14.3.1 | 12 | [Spec 4.3.14.3.1] OTA_ABORT Handler. |
| lib/pio_programs.py | 📄 pio_programs.py | S13.0 | 84 | [Spec 13.0] High-Speed Tachometry & PIO Strategy. |
|  | 🔧 pulse_counter_simple | S13.3.1 | 36 | [Spec 13.3.1] The Simple Pulse Counter Assembly Program. |
|  | 🔧 pulse_counter_with_mirror | S13.2.1 | 29 | [Spec 13.2.1] Pulse Counter with Hardware Mirror. |
| lib/sensors.py | 📄 sensors.py | S11.1, S11.2 | 486 | [Spec 11.1 & 11.2] Sensor Subsystem Specification Overview. |
|  | 🏛️ DigitalInput | S11.9 | 60 | [Spec 11.9] Digital Input Specification (GPIO Monitoring). |
|  |   └─ 🛠️ __init__ | S11.9.1, S9.5 | 21 | [Spec 11.9.1 & 9.5] Hardware Configuration & Anti-Poison. |
|  |   └─ 🛠️ _read_raw | S11.9.2 | 9 | [Spec 11.9.2] Raw Sampling & Logic Normalization. |
|  |   └─ 🛠️ read | S11.9.2 | 18 | [Spec 11.9.2] The Debounce Algorithm. |
|  |   └─ 🛠️ close | S11.8 | 3 | [Spec 11.8] Standard Lifecycle Cleanup. |
|  | 🏛️ PulseCounter | S11.6, S13.0 | 99 | [Spec 11.6 & 13.0] High-Performance Pulse Counting (PIO). |
|  |   └─ 🛠️ __init__ | S13.2, S13.5 | 40 | [Spec 13.2 & 13.5] Hardware Architecture & Signal Path. |
|  |   └─ 🛠️ get_data | S13.4 | 47 | [Spec 13.4] Python Driver Strategy (HAL). |
|  |   └─ 🛠️ close | S11.2 | 3 | [Spec 11.2] Hardware Hygiene: Disables the PIO State Machine. |
|  | 🏛️ BusWrapper | S11.4.4 | 143 | [Spec 11.4.4] Multi-Bus Abstraction (BusWrapper). |
|  |   └─ 🛠️ __init__ | S11.4.4 | 13 | [Spec 11.4.4] Initializes the bus and performs initial device discovery. |
|  |   └─ 🛠️ setup | S11.1, S9.5 | 35 | [Spec 11.1 & 9.5] Bus Discovery & Safe Init. |
|  |   └─ 🛠️ teardown | S11.4.2 | 9 | [Spec 11.4.2] Releases the physical I2C bus resources. |
|  |   └─ 🛠️ read | S11.8 | 49 | [Spec 11.8] Exception Propagation & Rosetta Stone Mapping. |
|  |   └─ 🛠️ _apply_filters | S11.5.2 | 26 | [Spec 11.5.2] Data Sanitization Filters. |
|  | 🏛️ SensorManager | S11.4 | 117 | [Spec 11.4] Master HAL Controller. |
|  |   └─ 🛠️ __init__ | S11.3 | 52 | [Spec 11.3] Configuration Ingestion. |
|  |   └─ 🛠️ __enter__ | S11.4.2 | 3 | [Spec 11.4.2] Clean Room Protocol: Context Manager entry. |
|  |   └─ 🛠️ __exit__ | S11.2, S11.4.2 | 5 | [Spec 11.4.2 & 11.2] Clean Room Protocol: Mandatory Resource Teardown. |
|  |   └─ 🛠️ read_all | S11.7.1 | 39 | [Spec 11.7.1] The Core 1 Update Step. |
|  |   └─ 🛠️ get_telemetry_string | S4.3.9 | 8 | [Spec 4.3.9] The Sensor Dump Serializer. |
| lib/tester.py | 📄 tester.py | S14.2.7 | 111 | [Spec 14.2.7] Hardware Validation Sequencer (tester.py). |
|  | 🔧 run_sequence | S14.2.7 | 97 | [Spec 14.2.7] Executes the automated hardware test sequence. |
| lib/tsl2591.py | 📄 tsl2591.py | S11.0 | 157 | [Spec 11.0] Sensor Subsystem Specification. |
|  | 🏛️ TSL2591 | S11.8 | 111 | [Spec 11.8] Humble Component Driver. |
|  |   └─ 🛠️ __init__ | S9.5 | 21 | [Spec 9.5] Configuration & Hardware Safety (Safe Init). |
|  |   └─ 🛠️ _write_register |  | 4 | Internal: Direct I2C memory write. |
|  |   └─ 🛠️ _read_register |  | 7 | Internal: Direct I2C memory read. |
|  |   └─ 🛠️ ping | S9.11 | 11 | [Spec 9.11] Sensor Connectivity Hardening. |
|  |   └─ 🛠️ enable | S11.0 | 4 | [Spec 11.0] Enables the device in Continuous Mode. |
|  |   └─ 🛠️ disable | S11.4.2 | 3 | [Spec 11.4.2] Places the silicon in low power mode. |
|  |   └─ 🛠️ close | S11.4.2 | 10 | [Spec 11.4.2] Standard Cleanup Method. |
|  |   └─ 🛠️ set_gain | S11.0 | 8 | [Spec 11.0] Sensor Configuration API. |
|  |   └─ 🛠️ set_timing | S11.0 | 8 | [Spec 11.0] Sensor Configuration API. |
|  |   └─ 🛠️ get_raw_channels | S11.8 | 10 | [Spec 11.8] Exception Propagation. |
|  |   └─ 🛠️ get_full_luminosity | S4.3.9.3 | 8 | [Spec 4.3.9.3] Standard Sensor Payload. |
| lib/vibration_driver.py | 📄 vibration_driver.py | S10.9 | 118 | [Spec 10.9] Specialized Driver Standards (HAL Extensions). |
|  | 🏛️ VibrationDriver | S10.9.1 | 104 | [Spec 10.9.1] Humble Component Driver. |
|  |   └─ 🛠️ __init__ | S10.9.5 | 37 | [Spec 10.9.5] Configuration Whitelisting. |
|  |   └─ 🛠️ set_freq | S10.3.1 | 12 | [Spec 10.3.1] Hardware Tuning. |
|  |   └─ 🛠️ set_speed | S10.9.2 | 25 | [Spec 10.9.2] Mandatory Interface: set_speed(value). |
|  |   └─ 🛠️ stop | S10.9.2 | 7 | [Spec 10.9.2] Mandatory Interface: stop(). |
|  |   └─ 🛠️ deinit | S10.9.2 | 13 | [Spec 10.9.2] Mandatory Interface: deinit(). |
| mass_ota_flasher.py | 🔧 crc16_ccitt |  | 9 | No docstring |
|  | 🔧 build_packet |  | 16 | Builds Standard MTIP v5.5 Packet. |
|  | 🔧 parse_packet |  | 17 | No docstring |
|  | 🔧 wait_for_ack |  | 14 | No docstring |
|  | 🔧 print_progress_bar |  | 11 | Call in a loop to create terminal progress bar |
|  | 🔧 flash_file |  | 88 | No docstring |
|  | 🔧 wizard |  | 46 | No docstring |

## Summary


Total Fleet Files:    14
Total Fleet Lines:    4133
Total Logical Classes: 18
Total Control Points:  135
Compliance Density:    85 Industrial Specs Identified
