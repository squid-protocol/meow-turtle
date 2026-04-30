# NINELIVES SYSTEM MANIFEST

## Forensic Logic Audit

| File | Object | Specs | Lines | Summary |
| :--- | :--- | :--- | :--- | :--- |
| app.py | 📄 app.py | S6.0 | 168 | [Spec 6.0] Core 0 Main Entry Point. |
|  | 🏛️ GuiLogBridge | S19.5 | 44 | [Spec 19.5] Industrial GUI Logging Bridge. |
|  |   └─ 🛠️ emit | S19.5.1 | 32 | [Spec 19.5.1] Record Interception and Transformation. |
|  | 🔧 setup_logging |  | 11 | Initializes the cross-domain logging synchronization. |
|  | 🔧 index_page | S6.0 | 9 | [Spec 6.0] NiceGUI Client Landing Page. |
|  | 🔧 startup_service | S7.2 | 10 | [Spec 7.2] Service Startup Sequence. |
| ghost_exit.py | 📄 ghost_exit.py |  | 243 | MTIP v5 Diagnostic Utility (Ghost Exit). |
|  | 🔧 crc16_ccitt |  | 24 | Calculates the CRC-16-CCITT checksum for a given byte sequence. |
|  | 🔧 build_packet |  | 34 | Constructs an MTIP v5 packet according to the Spec 4.3 standard. |
|  | 🔧 parse_response |  | 46 | Parses and validates a raw serial response line. |
|  | 🔧 main |  | 94 | Main execution loop for the diagnostic tool. |
| gui.py | 📄 gui.py | S19.0 | 577 | [Spec 19.0] Ninelives Prototype GUI Dashboard. |
|  | 🏛️ SorterGUI | S19.0 | 537 | [Spec 19.0] Master GUI Controller. |
|  |   └─ 🛠️ __init__ |  | 46 | Initializes the GUI Controller. |
|  |   └─ 🛠️ _bg_task |  | 9 | [ASYNC SAFETY] Internal helper to launch non-blocking coroutines. |
|  |   └─ 🛠️ setup_ui | S19.1 | 19 | [Spec 19.1] Constructs the high-density grid layout. |
|  |   └─ 🛠️ build_system_status_block |  | 39 | [Section 13] Top Left: Global System Health, CPU, and Primary Controls. |
|  |   └─ 🛠️ build_flight_recorder_block | S19.5 | 28 | [Spec 19.5] Top Right: Real-time Log Stream with Bayesian Filtering & Deduplication. |
|  |   └─ 🛠️ build_limb_block | S6.2 | 37 | [Spec 6.2] Standard layout for Loader (P1) and Distributor (P3). |
|  |   └─ 🛠️ build_gatekeeper_block | S6.2.2 | 30 | [Spec 6.2.2] Pico 2: Specialized Pulse/Breakbeam Sync monitor. |
|  |   └─ 🛠️ _add_health_dashboard | S20.1 | 18 | [Spec 20.1] Technical grid displaying critical limb health metrics. |
|  |   └─ 🛠️ _build_gyro_table | S6.2.1 | 14 | [Spec 6.2.1] IMU visualization table for stability monitoring. |
|  |   └─ 🛠️ _add_config_table |  | 6 | Displays the 'Persistent Metadata' (Spec 4.4) retrieved from the Pico flash. |
|  |   └─ 🛠️ _add_version_table |  | 6 | Displays the firmware 'Version Manifest' (Spec 9.3) for forensic auditing. |
|  |   └─ 🛠️ send_throttled_cfg | S19.5 | 8 | [Spec 19.5] Resource Management: Prevents flooding the RS-485 bus. |
|  |   └─ 🛠️ flash_freq |  | 7 | [Section 4.3.10 Mechanism 3] Atomic Hardware Frequency Flash. |
|  |   └─ 🛠️ add_vibratory_control | S19.3 | 22 | [Spec 19.3] High-fidelity dual-slider control for material singulation. |
|  |   └─ 🛠️ add_conveyor_control | S19.4 | 11 | [Spec 19.4] Precision speed control for sorting transport. |
|  |   └─ 🛠️ add_solenoid_button | S19.3 | 6 | [Spec 19.3] Simplified one-shot trigger interface for pneumatic actuators. |
|  |   └─ 🛠️ update_tick | S19.5 | 161 | [Spec 19.5] The Primary UI Heartbeat Loop (5Hz). |
|  |   └─ 🛠️ _toggle_log_filter |  | 5 | Toggles the visibility filter for specific log levels (D/I/W/E). |
|  |   └─ 🛠️ _refresh_log_filter_buttons |  | 6 | Updates the visual state of filter buttons to reflect active filters. |
|  |   └─ 🛠️ clear_logs |  | 3 | Wipes the 'Flight Recorder' visualization and resets the deduplication state. |
|  |   └─ 🛠️ toggle_autoscroll |  | 3 | Enables or disables automatic scroll-to-bottom for the log stream. |
|  |   └─ 🛠️ build_imaging_block |  | 5 | [Placeholder] UI container for the Vision system output. |
| lib/alarm_manager.py | 📄 alarm_manager.py | S18.1 | 274 | [Spec 18.1] Ninelives Alarm Management System. |
|  | 🏛️ AlarmManager | S18.1 | 238 | [Spec 18.1] The Alarm Manager. |
|  |   └─ 🛠️ __init__ |  | 25 | Initializes the Alarm Manager and its internal registries. |
|  |   └─ 🛠️ check_health | S15.2 | 99 | [Spec 15.2] Central Health Observer. |
|  |   └─ 🛠️ acknowledge_alarm | S18.1 | 22 | [Spec 18.1] Transitions an alarm to Acknowledged state. |
|  |   └─ 🛠️ check_arming_safety | S18.2 | 13 | [Spec 18.2] Industrial Arming Interlock. |
|  |   └─ 🛠️ raise_alarm |  | 30 | Triggers a new alarm event and potentially modifies system state. |
|  |   └─ 🛠️ clear_alarm |  | 21 | Removes a fault condition from all registries. |
|  |   └─ 🛠️ get_active_list |  | 3 | Returns the dictionary of currently active, unacknowledged alarms. |
|  |   └─ 🛠️ get_active_details |  | 10 | Aggregates details for all alarms (Active and Acknowledged). |
| lib/calibration.py | 📄 calibration.py | S16.0 | 115 | [Spec 16.0] Ninelives Spatial Calibration System. |
|  | 🏛️ CalibrationManager | S16.0 | 78 | [Spec 16.0] The Calibration Manager. |
|  |   └─ 🛠️ __init__ |  | 3 | Initializes the manager and loads persistent data. |
|  |   └─ 🛠️ _load_data | S10.4 | 14 | [Spec 10.4] Configuration Anti-Poison Logic. |
|  |   └─ 🛠️ _write_defaults |  | 7 | Commits hardcoded defaults to disk to recover from corruption. |
|  |   └─ 🛠️ save |  | 6 | Atomic write of the calibration data to JSON. |
|  |   └─ 🛠️ get_loader_params | S19.3 | 7 | [Spec 19.3] Translates GUI 'Strength' into hardware PWM parameters. |
|  |   └─ 🛠️ get_belt_pwm | S19.4 | 8 | [Spec 19.4] Precision speed scaling for the transport belt. |
|  |   └─ 🛠️ pulses_to_mm | S16.1 | 4 | [Spec 16.1] Translates raw odometer pulses into physical distance. |
|  |   └─ 🛠️ mm_to_pulses | S16.3 | 5 | [Spec 16.3] Translates physical distance into target motor pulses. |
|  |   └─ 🛠️ get_real_speed |  | 3 | Calculates current belt velocity in millimeters per second. |
|  |   └─ 🛠️ update_pulse_ratio | S16.4 | 7 | [Spec 16.4] Commits new calibration results from the Wizard. |
| lib/coordinator.py | 📄 coordinator.py | S5.0 | 582 | [Spec 5.0] The System Coordinator (The Hub). |
|  | 🏛️ SystemCoordinator | S4.3.11, S21.0 | 534 | The Hub. Maintains the lifecycle of all specialized domains. |
|  |   └─ 🛠️ __init__ |  | 58 | Initializes the central orchestrator and populates the Digital Twin. |
|  |   └─ 🛠️ start |  | 61 | Orchestrates the formal bootstrap sequence (Spec 7.2). |
|  |   └─ 🛠️ alarm_check_loop | S18.1 | 19 | [Spec 18.1] Periodic health check and alarm evaluation loop. |
|  |   └─ 🛠️ send_cmd |  | 82 | Routes GUI Intents while enforcing the Dual-Interlock Safety Hierarchy. |
|  |   └─ 🛠️ fetch_fleet_versions | S9.3 | 10 | [Spec 9.3] Triggers a fleet-wide 'Version Manifest' audit. |
|  |   └─ 🛠️ broadcast_reset |  | 20 | Executes a synchronized system-wide reset. |
|  |   └─ 🛠️ broadcast_stop |  | 12 | Priority Hard Stop. |
|  |   └─ 🛠️ record_ack | S20.1 | 22 | [Spec 20.1] Centralized RTT calculation. |
|  |   └─ 🛠️ network_health_aggregator | S20.2 | 29 | [Spec 20.2] Centralized LQI scoring based on transport counters. |
|  |   └─ 🛠️ register_receipt |  | 4 | Registers a packet sequence ID for the W-Protocol Wipe Registry. |
|  |   └─ 🛠️ _clear_confirmed_wipes |  | 6 | Clears confirmed packet sequence IDs from the Wipe Registry. |
|  |   └─ 🛠️ send_physical |  | 32 | Dispatches binary packets to the physical hardware transport layer. |
|  |   └─ 🛠️ send_manual_command |  | 39 | Routes manual hardware overrides with built-in Thermal Pulse safety. |
|  |   └─ 🛠️ _normalize_actuator_name |  | 12 | Resolves shorthand or numeric actuator names to the canonical ID. |
|  |   └─ 🛠️ dedupe_cache_refresher | S4.3.11 | 20 | [Spec 4.3.11] Self-Healing Command Registry Watchdog. |
|  |   └─ 🛠️ _broadcast_time_sync |  | 5 | Synchronizes system time across all downstream Pico limbs. |
|  |   └─ 🛠️ host_health_monitor | S21.0 | 36 | [Spec 21.0] Host Health Driver (Active Measurement). |
|  |   └─ 🛠️ log_request_watchdog |  | 16 | Handles timeouts for hardware log retrieval requests. |
|  |   └─ 🛠️ _notify |  | 3 | Pushes a notification message to the GUI consumer queue. |
|  |   └─ 🛠️ stop |  | 4 | Clean shutdown of the Coordinator lifecycle. |
| lib/digital_twin.py | 📄 digital_twin.py | S3.0 | 277 | [Spec 3.0] Ninelives Digital Twin System. |
|  | 🏛️ Actuator | S3.2 | 36 | [Spec 3.2] Representation of a physical output (Motor, Solenoid). |
|  | 🏛️ Sensor | S4.3.9 | 17 | [Spec 4.3.9] Representation of a physical input (Light, Gyro, Odometer). |
|  | 🏛️ HostHealth | S21.0 | 22 | [Spec 21.0] Host Health Mirror (Passive). |
|  | 🏛️ Limb | S6.2 | 69 | [Spec 6.2] The Digital Mirror of a physical Pico node. |
|  |   └─ 🛠️ touch |  | 3 | Resets the liveness timer. Called by Switchboard on valid RX. |
|  | 🏛️ DigitalTwin | S3.0 | 85 | [Spec 3.0] The Global Hierarchy Root. |
|  |   └─ 🛠️ __init__ |  | 7 | Initializes the host health monitor and logical state. |
|  |   └─ 🛠️ register_limb | S6.2 | 13 | [Spec 6.2] Dynamically registers a new hardware limb. |
|  |   └─ 🛠️ update_actuator_telemetry | S19.2 | 27 | [Spec 19.2] Synchronizes hardware actuator states into the Twin. |
|  |   └─ 🛠️ update_sensor_telemetry | S6.1 | 18 | [Spec 6.1] Synchronizes hardware sensor telemetry into the Twin. |
|  |   └─ 🛠️ set_state | S13.0 | 9 | [Spec 13.0] Updates the global logical state machine. |
| lib/gui_helpers.py | 📄 gui_helpers.py | S19.0 | 344 | [Spec 19.0] Ninelives GUI Utility Library. |
|  | 🏛️ UIUtils | S19.5 | 102 | [Spec 19.5] Industrial UI Primitives. |
|  |   └─ 🛠️ update_text | S19.5 | 17 | [Spec 19.5] Delta-State Text Update. |
|  |   └─ 🛠️ update_style | S19.5 | 16 | [Spec 19.5] Delta-State CSS Update. |
|  |   └─ 🛠️ update_classes | S19.5 | 20 | [Spec 19.5] Delta-State Tailwind Update. |
|  |   └─ 🛠️ update_vis | S19.5 | 16 | [Spec 19.5] Delta-State Visibility Management. |
|  |   └─ 🛠️ parse_kv_payload | S4.3 | 15 | [Spec 4.3] Key-Value Parser Proxy. |
|  | 🏛️ LogManager | S19.5 | 68 | [Spec 19.5] Flight Recorder Management Engine. |
|  |   └─ 🛠️ __init__ |  | 11 | Initializes the LogManager with deduplication state. |
|  |   └─ 🛠️ get_signature | S19.5 | 18 | [Spec 19.5] Log Deduplication logic. |
|  |   └─ 🛠️ process_entry |  | 29 | Filters and formats raw log entries for display. |
|  | 🏛️ GUIModals | S19.0 | 143 | [Spec 19.0] Industrial HMI Modals. |
|  |   └─ 🛠️ open_inspector | S9.3 | 59 | [Spec 9.3] Comprehensive Hardware Inspector. |
|  |   └─ 🛠️ open_calibration_wizard | S16.4 | 73 | [Spec 16.4] Interactive Spatial Calibration Wizard. |
| lib/job_manager.py | 📄 job_manager.py | S12.0 | 287 | [Spec 12.0] Ninelives Job Management System. |
|  | 🏛️ JobManager | S12.0 | 257 | [Spec 12.0] The Job Manager. |
|  |   └─ 🛠️ __init__ |  | 16 | Initializes the Job Manager and locates the profile manifest. |
|  |   └─ 🛠️ run_arming_sequence | S7.2 | 59 | [Spec 7.2] Orchestrates the transition: IDLE -> ARMING -> FLOW. |
|  |   └─ 🛠️ run_calibration_sequence | S16.4 | 72 | [Spec 16.4] Automated Spatial Calibration Sequence. |
|  |   └─ 🛠️ _load_profile | S14.1 | 22 | [Spec 14.1] Loads and performs safety bounds-checking on profile parameters. |
|  |   └─ 🛠️ _dispatch_configs |  | 22 | [Spec 4.3.6.2 Phase 1] Dispatches configuration parameters to the fleet. |
|  |   └─ 🛠️ _verify_hardware_readiness |  | 27 | [Spec 4.3.6.2 Phase 2] Verifies receipt of configuration parameters. |
|  |   └─ 🛠️ enter_idle_sequence | S13.2 | 16 | [Spec 13.2] Adaptive Stop Management (Production Clear-Out). |
| lib/logic_engine.py | 📄 logic_engine.py | S6.0 | 247 | [Spec 6.0] Ninelives Logic Engine (The Frontal Lobe). |
|  | 🏛️ LogicEngine | S6.0 | 220 | [Spec 6.0] The Frontal Lobe. |
|  |   └─ 🛠️ __init__ |  | 28 | Initializes the Logic Engine and its internal memory structures. |
|  |   └─ 🛠️ run_loop | S10.1 | 27 | [Spec 10.1] Main Event Processing Loop. |
|  |   └─ 🛠️ handle_hardware_event |  | 34 | Parses raw payloads from Picos and translates them into logical actions. |
|  |   └─ 🛠️ _verify_wipe_success | S4.3.6.3 | 37 | [Spec 4.3.6.3] Verification of Success. |
|  |   └─ 🛠️ _process_part_detected | S4.2 | 32 | [Spec 4.2] Odometer Synchronization. |
|  |   └─ 🛠️ handle_vision_result | S11.3 | 29 | [Spec 11.3] Vision result matching and kinetic routing. |
|  |   └─ 🛠️ reset_logic | S15.3 | 9 | [Spec 15.3] Clears memory and tracking state to recover from system errors. |
| lib/machine_states.py | 📄 machine_states.py | S13.1 | 97 | [Spec 13.1] Ninelives Standardized Machine States. |
| lib/meowprotocol.py | 📄 meowprotocol.py | S4.3 | 236 | [Spec 4.3] Ninelives Message Transfer Interface Protocol (MTIP). |
|  | 🔧 crc16_ccitt | S23.1 | 17 | [Spec 23.1] High-performance CRC-16-CCITT implementation. |
|  | 🔧 build_packet | S4.3.3 | 29 | [Spec 4.3.3] Constructs an MTIP wire-ready packet. |
|  | 🏛️ PacketParser | S4.3.1 | 95 | [Spec 4.3.1] Robust Delimiter-Based Parser. |
|  |   └─ 🛠️ __init__ |  | 9 | Initializes the parser buffer and local addressing. |
|  |   └─ 🛠️ parse |  | 75 | Ingests a raw data chunk and extracts valid MTIP packets. |
| lib/protocol_parser.py | 📄 protocol_parser.py | S4.3 | 167 | [Spec 4.3] MTIP v5 Protocol Parser. |
|  | 🔧 parse_kv_payload | S4.3 | 85 | [Spec 4.3] Hardened Key-Value and JSON Parser. |
|  | 🔧 decode_envelope | S19.2 | 39 | [Spec 19.2] Protocol Envelope Decoder. |
|  | 🔧 format_telemetry |  | 16 | Helper to pack a dictionary back into a protocol string. |
| lib/rp5_logger.py | 📄 rp5_logger.py | S9.0 | 165 | [Spec 9.0] Ninelives Host Logging System. |
|  | 🔧 setup_logger | S9.1 | 42 | [Spec 9.1] Configures the central ROOT logger infrastructure. |
|  | 🔧 set_debug_mode | S10.5 | 19 | [Spec 10.5] Dynamic Debug Control. |
|  | 🔧 scan_local_versions | S9.3 | 43 | [Spec 9.3] Forensic Boot Manifest Generation. |
| lib/safety_tasks.py | 📄 safety_tasks.py | S6.0 | 306 | [Spec 6.0] Ninelives Safety Management System (The Immune System). |
|  | 🏛️ SafetyManager | S6.0 | 278 | [Spec 6.0] The Immune System. |
|  |   └─ 🛠️ __init__ |  | 32 | Initializes the Safety Manager and establishes the reflexive thresholds. |
|  |   └─ 🛠️ trigger_recovery_grace | S15.3 | 10 | [Spec 15.3] Inhibits STATE_ERROR transitions for a brief window post-reset. |
|  |   └─ 🛠️ in_grace_period |  | 3 | Checks if the system is currently within the post-reset safety window. |
|  |   └─ 🛠️ is_safe_to_arm | S18.2 | 31 | [Spec 18.2] Industrial Arming Interlock. |
|  |   └─ 🛠️ pulse_solenoid | S15.4 | 21 | [Spec 15.4] Duty-Cycle protection for pneumatic solenoids. |
|  |   └─ 🛠️ monitor_loop | S15.2 | 37 | [Spec 15.2] Central Safety Observer (20Hz). |
|  |   └─ 🛠️ _scan_for_hardware_overrides | S15.5 | 14 | [Spec 15.5] Detects and reacts to Pico-autonomous safety decisions. |
|  |   └─ 🛠️ _verify_motion |  | 25 | Kinetic Jam detection via odometer stagnation. |
|  |   └─ 🛠️ _check_thermal_health | S15.4.1 | 40 | [Spec 15.4.1] Unified Thermal Tiering logic. |
|  |   └─ 🛠️ watchdog_task | S15.1 | 37 | [Spec 15.1] Aggressive Watchdog Task. |
| lib/switchboard.py | 📄 switchboard.py | S4.0 | 440 | [Spec 4.0] Ninelives Nervous System (The Transport Layer). |
|  | 🏛️ PicoController | S4.1 | 255 | [Spec 4.1] Individual Limb Controller. |
|  |   └─ 🛠️ __init__ |  | 41 | Initializes the controller for a specific Pico ID. |
|  |   └─ 🛠️ connect | S4.1.1 | 21 | [Spec 4.1.1] Attempts to open the asynchronous serial connection. |
|  |   └─ 🛠️ send_packet | S4.3.6.3 | 74 | [Spec 4.3.6.3] Transmits a packet with integrated W-Protocol injection. |
|  |   └─ 🛠️ read_loop | S4.3.1.1 | 44 | [Spec 4.3.1.1] Infinite RX Consumer Loop. |
|  |   └─ 🛠️ _handle_packet | S4.3.6 | 62 | [Spec 4.3.6] The Nervous System Logic Dispatcher. |
|  | 🏛️ operator | S4.1.2 | 109 | [Spec 4.1.2] Fleet Operator. |
|  |   └─ 🛠️ __init__ |  | 16 | Initializes the fleet manager and instantiates controllers for each limb. |
|  |   └─ 🛠️ start |  | 11 | Launches the nervous system processes. |
|  |   └─ 🛠️ polling_loop | S4.3 | 54 | [Spec 4.3] Master Polling Cycle. |
|  |   └─ 🛠️ send |  | 16 | High-level send interface used by the Coordinator. |
| lib/telemetry_router.py | 📄 telemetry_router.py | S19.0 | 249 | [Spec 19.0] Ninelives Telemetry Routing System (The Black Box). |
|  | 🏛️ TelemetryRouter | S19.0 | 193 | [Spec 19.0] The Telemetry Router. |
|  |   └─ 🛠️ __init__ | S19.5 | 9 | Initializes the router and the memory-safe GUI log buffer. |
|  |   └─ 🛠️ route_packet | S19.1 | 77 | [Spec 19.1] Primary Telemetry Ingestion Path. |
|  |   └─ 🛠️ _handle_live_log | S19.2 | 62 | [Spec 19.2] Live Operational Log Processor. |
|  |   └─ 🛠️ _handle_crash_log | S4.3.11 | 34 | [Spec 4.3.11] Flash-Resident Crash Log Handler. |
| mass_ota_flasher.py | 📄 mass_ota_flasher.py | S4.3.14 | 292 | [Spec 4.3.14] OTA System: File Transfer Orchestration. |
|  | 🔧 crc16_ccitt | S23.1 | 13 | [Spec 23.1] High-performance CRC-16-CCITT implementation. |
|  | 🔧 build_packet | S4.3.3 | 12 | [Spec 4.3.3] Constructs an MTIP wire-ready packet. |
|  | 🔧 parse_packet | S4.3 | 15 | [Spec 4.3] Robust Protocol Parser. |
|  | 🔧 wait_for_ack | S4.3.6.2 | 18 | [Spec 4.3.6.2] Brain Strategy: Command Accountability. |
|  | 🔧 check_alive | S4.3.7 | 19 | [Spec 4.3.7] Industrial Health Heartbeat check. |
|  | 🔧 flash_device | S4.3.14.4 | 99 | [Spec 4.3.14.4] The Update Lifecycle (Orchestration). |
|  | 🔧 main | S4.3.14.2.1 | 36 | [Spec 4.3.14.2.1] OTA System Entry Point. |
| safe_mode_gui.py | 🔧 read_last_logs |  | 9 | No docstring |
|  | 🔧 restart_system |  | 3 | No docstring |
|  | 🔧 reboot_pi |  | 2 | No docstring |

## Summary


Total Fleet Files:    18
Total Fleet Lines:    5066
Total Logical Classes: 20
Total Control Points:  141
Compliance Density:    62 Industrial Specs Identified
