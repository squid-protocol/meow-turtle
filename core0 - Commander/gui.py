# gui.py - Operator Dashboard (v7.1 - Role Separation)
# PURPOSE: High-density vertical dashboard for Ninelives.shell coordination.
# COMPLIANCE: Core 0 Spec 19, Spec 20.2, Rectification 19.5 (Direct Primitives)
# CHANGES: 
#   - v7.1: Migrated Inspector Refresh (FETCH_VERSIONS) logic to Coordinator.
#   - v7.1: Removed local fetch_all_versions shim.

"""
[Spec 19.0] Ninelives Prototype GUI Dashboard.

The SorterGUI serves as the primary human-machine interface (HMI). It provides 
real-time visualization of the Digital Twin, exposing granular control over 
distributed hardware while maintaining strict performance through delta-state updates.

Key Architectural Features:
1. Vertical Strategy (Spec 19.1): Optimized for 1080x1920 industrial touchscreens.
2. Digital Twin Visualizer (Spec 19.2): Mirroring logic for sensor and actuator states.
3. Delta-State Management (Spec 19.5): Efficient DOM updates triggered only on state changes.
4. Asynchronous Log Hub: Integrates the 'Flight Recorder' stream with Bayesian filtering.
"""

from nicegui import ui, app
import asyncio
import time
import datetime
import os 
import json
from lib.digital_twin import GLOBAL_TWIN
from lib.telemetry_router import STREAM_ROUTER
from lib import machine_states as ms
from lib import meowprotocol
from lib.calibration import CALIBRATION 
from lib.gui_helpers import UIUtils, LogManager, GUIModals

try:
    import config.debug as dbg
    DEBUG_GUI = getattr(dbg, 'DEBUG_GUI', False) 
except ImportError:
    DEBUG_GUI = False

class SorterGUI:
    """
    [Spec 19.0] Master GUI Controller.
    
    Orchestrates the lifecycle of the NiceGUI dashboard. It binds the in-memory
    Digital Twin to visual elements and provides an interface for system-wide
    commands (START, STOP, RESET, CALIBRATE).
    """
    # =========================================================================
    # SECTION 1: INITIALIZATION & STATE MANAGEMENT
    # =========================================================================
    def __init__(self, coordinator):
        """
        Initializes the GUI Controller.
        
        Establishes the link to the SystemCoordinator, initializes the 
        delta-update cache, and builds the visual DOM.
        
        :param coordinator: The SystemCoordinator instance (The Hub).
        """
        self.coord = coordinator
        self.boot_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_file_path = os.path.abspath("logs/core0_system.log") 
        
        # --- UI Element References (For Dynamic Delta Updates) ---
        self.status_labels = {}    
        self.actuator_labels = {}  
        self.sensor_labels = {}    
        self.health_labels = {}    
        self.watchdog_labels = {}
        self.limb_cards = {}       
        self.maintenance_rows = {} 
        self.cpu_bars = []
        
        # Configuration/Version Delta Tracking Containers
        self.config_uis = {}      
        self.config_hashes = {}   
        self.version_uis = {}     
        self.version_hashes = {}  
        self.limb_titles = {} 

        # Log Management Engine & Deduplication State
        self.log_elements = []
        self.auto_scroll = True 
        self.log_filters = {'D': DEBUG_GUI, 'I': True, 'W': True, 'E': True}        
        self.log_manager = LogManager(debug_enabled=DEBUG_GUI)
        
        # Filter feedback state (Purple Flash logic)
        self.hidden_log_counters = {'D': 0, 'I': 0, 'W': 0, 'E': 0}

        # Internal State Cache (Prevents unnecessary DOM reflows)
        self._cache = {}          
        self.last_slider_cmd = 0  
        self.background_tasks = set() 

        # Build the Visual DOM
        self.setup_ui()

    def _bg_task(self, coro):
        """
        [ASYNC SAFETY] Internal helper to launch non-blocking coroutines.
        Ensures that GUI interactions do not freeze the main event loop while
        holding strong references to prevent garbage collection of active tasks.
        """
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    # =========================================================================
    # SECTION 2: PRIMARY LAYOUT CONSTRUCTION
    # =========================================================================
    def setup_ui(self):
        """
        [Spec 19.1] Constructs the high-density grid layout.
        
        Implements a 2-column x 3-row layout optimized for vertical touch displays.
        Initializes the heartbeat timer (5Hz) to drive the Update Tick.
        """
        ui.query('body').style('background-color: #020617; color: #f8fafc; font-family: "Noto Sans", sans-serif; overflow: hidden;')
        
        # minmax(0, ...) fixes the CSS grid blowout bug so scroll areas activate properly.
        # 0.8fr and 1.2fr ratios force the middle row to be smaller than the bottom row.
        with ui.grid(columns=2, rows='28vh minmax(0, 0.8fr) minmax(0, 1.2fr)').classes('w-full h-screen p-2 gap-1'):
            self.build_system_status_block()
            self.build_flight_recorder_block()
            self.build_limb_block(1, "LOADER CORE")
            self.build_gatekeeper_block()
            self.build_limb_block(3, "DISTRIBUTOR")
            self.build_imaging_block()

        # Kick off the high-frequency UI heartbeat (5Hz)
        ui.timer(0.2, self.update_tick)

    def build_system_status_block(self):
        """
        [Section 13] Top Left: Global System Health, CPU, and Primary Controls.
        """
        with ui.card().classes('bg-slate-900 border border-slate-800 p-2 h-full gap-1'):
            with ui.row().classes('items-center gap-2 mb-1 w-full'):
                ui.icon('pets', color='cyan-400').classes('text-2xl')
                with ui.column().classes('gap-0'):
                    ui.label('MEOW TURTLE').classes('text-lg font-black tracking-tighter text-cyan-500 leading-none')
                    ui.label(f'BOOT: {self.boot_time}').classes('text-[10px] font-mono text-cyan-800 tracking-wider')
                self.host_state_badge = ui.badge('BOOT').classes('ml-auto px-2 py-0.5 font-black text-[10px] bg-cyan-600')

            self.alarm_banner = ui.label('SYSTEM NORMAL').classes('w-full text-center py-0.5 rounded text-[10px] font-bold bg-emerald-900/30 text-emerald-400 border border-emerald-500/20 mb-1')

            with ui.row().classes('w-full items-end justify-between'):
                with ui.column().classes('gap-0'):
                    ui.label('01 :: SYSTEM OVERVIEW').classes('text-[10px] font-black text-cyan-400 uppercase tracking-widest')
                    self.host_temp_label = ui.label('--°C').classes('text-xl font-black text-slate-500 leading-none mt-1')
                with ui.column().classes('items-end'):
                    self.big_state = ui.label('IDLE').classes('text-5xl font-black text-cyan-500 tracking-tighter leading-none')
                    ui.label('OPERATIONAL MODE').classes('text-[10px] text-slate-600 font-bold')

            with ui.column().classes('w-full gap-0.5 mb-1'):
                ui.label('HOST CPU').classes('text-[8px] text-slate-500 font-bold')
                with ui.row().classes('w-full gap-1'):
                    for i in range(4):
                        bar = ui.linear_progress(value=0, show_value=False).classes('h-1 bg-slate-800 flex-grow').props('color=cyan-400')
                        self.cpu_bars.append(bar)

            with ui.grid(columns=2).classes('w-full gap-1 mt-auto'):
                ui.button('FLOW', on_click=lambda: self._bg_task(self.coord.send_cmd("START"))).props('color=emerald size=sm dense')
                ui.button('IDLE', on_click=lambda: self._bg_task(self.coord.send_cmd("IDLE"))).props('color=slate-700 size=sm dense')
                ui.button('LOGS', on_click=lambda: self._bg_task(self.coord.send_cmd("FETCH_LOGS"))).props('outline color=cyan size=sm dense icon=history')
                # PHASE 1: Delegated to Hub
                ui.button('VER', on_click=lambda: self._bg_task(self.coord.send_cmd("FETCH_VERSIONS"))).props('outline color=cyan size=sm dense icon=info')
                ui.button('CFG', on_click=lambda: self._bg_task(self.coord.send_cmd("FETCH_CONFIG"))).props('outline color=purple size=sm dense icon=download')
                ui.button('DEV', on_click=lambda: self._bg_task(self.coord.send_cmd("DEV_TOGGLE"))).props('outline color=amber size=sm dense')
                ui.button('RESET FLEET', on_click=lambda: self._bg_task(self.coord.send_cmd("RESET"))).props('outline color=blue size=sm dense').classes('col-span-2')
                
                # Split the bottom row into E-STOP and a clean OS-level SHUTDOWN button
                ui.button('E-STOP', on_click=lambda: self._bg_task(self.coord.broadcast_stop())).props('color=purple-900 size=md icon=emergency').classes('font-bold')
                ui.button('SHUTDOWN', on_click=app.shutdown).props('color=red-900 size=md icon=power_settings_new').classes('font-bold')
                
    def build_flight_recorder_block(self):
        """
        [Spec 19.5] Top Right: Real-time Log Stream with Bayesian Filtering & Deduplication.
        """
        with ui.card().classes('bg-black border border-slate-800 p-0 h-full overflow-hidden flex flex-col'):
            with ui.row().classes('w-full bg-slate-900/80 p-1 px-2 border-b border-slate-800 items-center shrink-0'):
                ui.label('02 :: FLIGHT RECORDER').classes('text-[10px] font-black text-cyan-400 uppercase tracking-widest')
                with ui.row().classes('ml-2 gap-0'):
                    ui.button('PING', on_click=lambda: STREAM_ROUTER.route_packet(0, meowprotocol.MSG_TYPE_LIVE_LOG, b"I|GUI|Manual Ping Test")).props('dense flat size=xs color=cyan').classes('text-[9px]')
                    ui.button(icon='delete', on_click=self.clear_logs).props('dense flat size=xs color=slate-500')
                    self.scroll_btn = ui.button(icon='vertical_align_bottom', on_click=self.toggle_autoscroll).props('dense flat size=xs color=cyan')
                
                with ui.row().classes('ml-auto gap-0.5 mr-2'):
                    def mk_btn(txt, key):
                        btn = ui.button(txt, on_click=lambda: self._toggle_log_filter(key)).props('dense flat size=xs round').classes('text-[8px] px-0 min-w-[1.5em] font-black')
                        setattr(self, f"btn_{key.lower()}", btn)
                        return btn
                    mk_btn('D', 'D'); mk_btn('I', 'I'); mk_btn('W', 'W'); mk_btn('E', 'E')
                ui.spinner('audio', size='xs', color='cyan-900')

            self.log_scroll = ui.scroll_area().classes('w-full flex-1 min-h-0 bg-black p-2')
            with self.log_scroll:
                self.log_container = ui.column().classes('w-full gap-0 font-mono text-[10px]')
                
            with ui.row().classes('w-full bg-slate-950 p-1 border-t border-slate-900 justify-between'):
                self.buffer_stats = ui.label('Buf: 0').classes('text-[9px] font-mono text-slate-600')
                self.log_path_lbl = ui.label(f'LOG: {self.log_file_path}').classes('text-[8px] font-mono text-slate-700 truncate max-w-[150px]')
        self._refresh_log_filter_buttons()

    def build_limb_block(self, pid, name):
        """
        [Spec 6.2] Standard layout for Loader (P1) and Distributor (P3).
        """
        card = ui.card().classes('bg-slate-900 border border-slate-800 p-3 h-full flex flex-col overflow-hidden transition-all duration-500')
        self.limb_cards[pid] = card
        with card:
            with ui.scroll_area().classes('w-full h-full pr-1'):
                with ui.column().classes('w-full gap-1'):
                    with ui.row().classes('w-full items-center border-b border-slate-800 pb-1 mb-1 shrink-0'):
                        ui.label(f"PICO {pid}: {name}").classes('text-[10px] font-black text-cyan-400 uppercase tracking-widest')
                        self.status_labels[pid] = ui.label('OFFLINE').classes('text-[10px] font-mono ml-auto')
                        self.watchdog_labels[pid] = ui.label('WD: --').classes('text-[10px] font-mono text-slate-600 ml-2')

                    with ui.row().classes('w-full items-center justify-end gap-1 mb-1') as row:
                        self.maintenance_rows[pid] = row
                        ui.button('INSPECT', on_click=lambda: GUIModals.open_inspector(pid)).props('flat dense size=xs color=cyan').classes('text-[9px]')
                        ui.button('SAVE', on_click=lambda: self._bg_task(self.coord.send_cmd(f"SAVE_P{pid}"))).props('flat dense size=xs color=amber').classes('text-[9px]')
                        ui.button('REBOOT', on_click=lambda: self._bg_task(self.coord.send_cmd(f"REBOOT_P{pid}"))).props('flat dense size=xs color=red').classes('text-[9px]')

                    self._add_health_dashboard(pid)
                    
                    ui.label('ACTUATOR MATRIX').classes('text-[10px] font-bold text-slate-600 uppercase tracking-tighter mt-1')
                    if pid == 1:
                        self.add_vibratory_control(1, "TVIB"); self.add_vibratory_control(1, "SVIB")
                        with ui.grid(columns=2).classes('w-full gap-1 mt-1'):
                             self.add_solenoid_button(1, "SOL_TUP"); self.add_solenoid_button(1, "SOL_TDWN")
                    elif pid == 3:
                        self.actuator_labels[(3, 'CONVEYOR', 'cal')] = ui.label('Ratio: --').classes('text-[9px] text-slate-600 font-mono w-full text-right')
                        self.add_conveyor_control(3, "CONVEYOR")
                        with ui.grid(columns=5).classes('w-full gap-1 mt-1'):
                            for i in range(1, 11): self.add_solenoid_button(3, f"SOL_{i}")
                            
                    ui.label('SENSOR TELEMETRY').classes('text-[10px] font-bold text-slate-600 mt-2 uppercase tracking-tighter')
                    if pid == 1: self._build_gyro_table(pid)
                    setattr(self, f"sensor_box_p{pid}", ui.column().classes('w-full gap-0.5'))
                    self._add_version_table(pid); self._add_config_table(pid)
                    
    def build_gatekeeper_block(self):
        """
        [Spec 6.2.2] Pico 2: Specialized Pulse/Breakbeam Sync monitor.
        """
        pid = 2
        card = ui.card().classes('bg-slate-900 border border-slate-800 p-3 h-full flex flex-col overflow-hidden transition-all duration-500')
        self.limb_cards[pid] = card
        with card:
            with ui.scroll_area().classes('w-full h-full pr-1'):
                with ui.column().classes('w-full gap-1'):
                    with ui.row().classes('w-full items-center border-b border-slate-800 pb-1 mb-1 shrink-0'):
                        ui.label(f"PICO 2: GATEKEEPER").classes('text-[10px] font-black text-cyan-400 uppercase tracking-widest')
                        self.status_labels[pid] = ui.label('OFFLINE').classes('text-[10px] font-mono ml-auto')
                        self.watchdog_labels[pid] = ui.label('WD: --').classes('text-[10px] font-mono text-slate-600 ml-2')

                    with ui.row().classes('w-full items-center justify-end gap-1 mb-1') as row:
                        self.maintenance_rows[pid] = row
                        ui.button('INSPECT', on_click=lambda: GUIModals.open_inspector(pid)).props('flat dense size=xs color=cyan').classes('text-[9px]')
                        ui.button('SAVE', on_click=lambda: self._bg_task(self.coord.send_cmd(f"SAVE_P{pid}"))).props('flat dense size=xs color=amber').classes('text-[9px]')
                        ui.button('REBOOT', on_click=lambda: self._bg_task(self.coord.send_cmd(f"REBOOT_P{pid}"))).props('flat dense size=xs color=red').classes('text-[9px]')

                    self._add_health_dashboard(pid)
                    
                    with ui.row().classes('w-full bg-black border border-slate-800 p-2 items-center justify-between rounded mt-1'):
                        ui.label('GLOBAL ODOMETER').classes('text-[9px] text-cyan-600 font-bold uppercase')
                        self.pulse_label = ui.label('00000').classes('text-xl font-mono text-cyan-400 font-black')
                    
                    self.scan_indicator = ui.card().classes('w-full h-[60px] bg-black border-2 border-slate-800 flex items-center justify-center')
                    with self.scan_indicator: self.scan_label = ui.label('CLEAR').classes('text-2xl font-black text-emerald-600 uppercase')
                    
                    setattr(self, f"sensor_box_p{pid}", ui.column().classes('w-full gap-0.5 mt-1'))
                    self._add_version_table(pid); self._add_config_table(pid)
                    
    # =========================================================================
    # SECTION 4: REUSABLE UI BUILDING BLOCKS
    # =========================================================================
    def _add_health_dashboard(self, pid):
        """
        [Spec 20.1] Technical grid displaying critical limb health metrics.
        """
        with ui.grid(columns=5).classes('w-full gap-0.5 p-1 bg-slate-950/40 rounded border border-slate-800/50'):
            self.health_labels[pid] = {}
            metrics = [
                ('UPT', 'UPTIME', 'cyan'), ('V', 'VOLTS', 'emerald'), ('VM', 'V-MIN', 'amber'),
                ('T', 'TEMP C', 'orange'), ('LQI', 'LQI %', 'cyan'),
                ('LA', 'LOOP AVG', 'blue'), ('LM', 'LOOP MAX', 'indigo'),
                ('RA', 'LAT AVG', 'purple'), ('RL', 'LAT MAX', 'pink'), ('CE', 'CRC ERR', 'red'),
                ('IE', 'I2C ERR', 'red'), ('CSE', 'PKT ERR', 'red'), ('WC', 'WRITE', 'slate'),
                ('RST', 'RESET', 'slate')
            ]
            for key, label, color in metrics:
                with ui.column().classes('gap-0 items-center p-0.5'):
                    ui.label(label).classes('text-[7px] font-bold text-slate-600 uppercase')
                    self.health_labels[pid][key] = ui.label('--').classes(f'text-[10px] font-mono text-{color}-400 font-black')

    def _build_gyro_table(self, pid):
        """
        [Spec 6.2.1] IMU visualization table for stability monitoring.
        """
        with ui.column().classes('w-full gap-0 mb-1 bg-slate-950/30 rounded p-1 border border-slate-800/30'):
            with ui.grid(columns=3).classes('w-full gap-1 mb-0.5'):
                ui.label('AXIS').classes('text-[8px] text-slate-500 font-bold')
                ui.label('GYRO 1').classes('text-[8px] text-cyan-600 font-bold text-center')
                ui.label('GYRO 2').classes('text-[8px] text-cyan-600 font-bold text-center')
            for m in ['AX', 'AY', 'AZ', 'GX', 'GY', 'GZ', 'TEMP']:
                 with ui.grid(columns=3).classes('w-full gap-1 items-center'):
                    ui.label(m).classes('text-[8px] text-slate-400 font-bold')
                    self.sensor_labels[(pid, f"MAIN_GYRO_{m}")] = ui.label('--').classes('text-[9px] font-mono text-cyan-400 text-center leading-none')
                    self.sensor_labels[(pid, f"AUX_GYRO_{m}")] = ui.label('--').classes('text-[9px] font-mono text-cyan-400 text-center leading-none')

    def _add_config_table(self, pid):
        """Displays the 'Persistent Metadata' (Spec 4.4) retrieved from the Pico flash."""
        ui.separator().classes('bg-slate-800 mt-2 mb-1')
        ui.label('RUNTIME CONFIG').classes('text-[10px] font-bold text-slate-500 uppercase tracking-tighter')
        self.config_uis[pid] = ui.column().classes('w-full gap-1 bg-black/20 p-1 rounded border border-slate-800/30 max-h-[150px] overflow-y-auto')
        with self.config_uis[pid]: ui.label('No Config Loaded').classes('text-[9px] italic text-slate-700')

    def _add_version_table(self, pid):
        """Displays the firmware 'Version Manifest' (Spec 9.3) for forensic auditing."""
        ui.separator().classes('bg-slate-800 mt-2 mb-1')
        ui.label('VERSION MANIFEST').classes('text-[10px] font-bold text-slate-500 uppercase tracking-tighter')
        self.version_uis[pid] = ui.column().classes('w-full gap-1 bg-black/20 p-1 rounded border border-slate-800/30 max-h-[80px] overflow-y-auto')
        with self.version_uis[pid]: ui.label('No Manifest Loaded').classes('text-[9px] italic text-slate-700')

    # =========================================================================
    # SECTION 5: CONTROL INPUTS & WIDGETS
    # =========================================================================
    
    def send_throttled_cfg(self, pid, cmd):
        """
        [Spec 19.5] Resource Management: Prevents flooding the RS-485 bus.
        """
        now = time.time()
        if now - self.last_slider_cmd > 0.2:
            self._bg_task(self.coord.send_physical(pid, meowprotocol.MSG_TYPE_SET_CFG, cmd))
            self.last_slider_cmd = now

    async def flash_freq(self, pid, act_id, val):
        """
        [Section 4.3.10 Mechanism 3] Atomic Hardware Frequency Flash.
        """
        self.coord._notify(f"Flashing {val}Hz to Pico {pid}...", type='info')
        await self.coord.send_physical(pid, meowprotocol.MSG_TYPE_SET_CFG, f"CFG:ACT:{act_id}:freq={int(val)}")
        await asyncio.sleep(0.1)
        await self.coord.send_physical(pid, meowprotocol.MSG_TYPE_CMD, "CFG:SAVE")
        
    def add_vibratory_control(self, pid, act_id):
        """
        [Spec 19.3] High-fidelity dual-slider control for material singulation.
        """
        with ui.column().classes('w-full gap-1 p-1.5 bg-slate-950/50 rounded'):
            with ui.row().classes('w-full items-center'):
                self.actuator_labels[(pid, act_id, 'icon')] = ui.icon('waves', size='xs').classes('mr-1 text-slate-700')
                ui.label(f"{act_id.upper()}").classes('text-[10px] font-bold text-emerald-500')
                self.actuator_labels[(pid, act_id)] = ui.label('UNM').classes('text-[10px] px-1 bg-slate-800 rounded ml-auto font-mono font-bold')
            
            # Strength (Duty)
            with ui.row().classes('w-full items-center no-wrap gap-1'):
                ui.label('STR').classes('text-[10px] w-6 text-slate-500')
                s_d = ui.slider(min=0, max=1, step=0.01, value=0.5).classes('flex-grow').props('dense size=xs debounce="200" label')
                s_d.on('change', lambda e: self._bg_task(self.coord.send_manual_command(pid, act_id, e.args)))
                
            # Frequency (Hz)
            with ui.row().classes('w-full items-center no-wrap gap-1'):
                ui.label('FRQ').classes('text-[10px] w-6 text-slate-500')
                s_f = ui.slider(min=1000, max=30000, step=100, value=12000).classes('flex-grow').props('color=amber dense size=xs debounce="200" label')
                s_f.on('change', lambda e: self.send_throttled_cfg(pid, f"CFG:ACT:{act_id}:freq={int(e.args)}")) 
                ui.button(icon='save', on_click=lambda: self._bg_task(self.flash_freq(pid, act_id, s_f.value))).props('flat dense size=xs color=amber')
                
    def add_conveyor_control(self, pid, act_id):
        """
        [Spec 19.4] Precision speed control for sorting transport.
        """
        with ui.column().classes('w-full gap-1 p-1.5 bg-slate-950/50 rounded'):
            with ui.row().classes('w-full items-center'):
                self.actuator_labels[(pid, act_id, 'icon')] = ui.icon('conveyor_belt', size='xs').classes('mr-1 text-slate-700')
                ui.label(f"{act_id.upper()}").classes('text-[10px] font-bold text-cyan-500')
                ui.button(icon='construction', on_click=lambda: GUIModals.open_calibration_wizard(self.coord)).props('flat dense size=xs color=amber').classes('ml-1')
                self.actuator_labels[(pid, act_id)] = ui.label('UNM').classes('text-[10px] px-1 bg-slate-800 rounded ml-auto font-mono font-bold')
            ui.slider(min=0, max=1, step=0.01).props('dense size=xs label debounce="200"').on('change', lambda e: self._bg_task(self.coord.send_manual_command(pid, act_id, e.args)))

    def add_solenoid_button(self, pid, act_id):
        """[Spec 19.3] Simplified one-shot trigger interface for pneumatic actuators."""
        with ui.column().classes('items-center gap-0'):
            self.actuator_labels[(pid, act_id)] = ui.label('UNM').classes('text-[8px] font-bold text-slate-600 mb-0.5')
            
            # Catch the NiceGUI event 'e' so it doesn't overwrite our local variables
            async def fire_solenoid(e):
                await self.coord.send_manual_command(pid, act_id, 1.0)
                
            btn = ui.button(act_id.split('_')[-1].upper(), on_click=fire_solenoid)
            btn.props('flat dense color=slate-400 size=xs').classes('text-[10px] border border-slate-800 w-full px-0')
    # =========================================================================
    # SECTION 6: THE HEARTBEAT TICK
    # =========================================================================
    def update_tick(self):
        """
        [Spec 19.5] The Primary UI Heartbeat Loop (5Hz).
        
        Uses lib.gui_helpers.UIUtils for efficient delta-state updates.
        """
        try:
            now = time.time()
            # 1. Host Resources (Polling is now handled by Coordinator task)
            UIUtils.update_text(self.host_temp_label, self._cache, "host_temp", f"{GLOBAL_TWIN.host.temp:.1f}°C")
            UIUtils.update_text(self.host_state_badge, self._cache, "sys_badge", GLOBAL_TWIN.host_state)
            UIUtils.update_text(self.big_state, self._cache, "big_state", GLOBAL_TWIN.host_state)
            
            for i, load in enumerate(GLOBAL_TWIN.host.cpu_cores):
                if i < len(self.cpu_bars): self.cpu_bars[i].set_value(load / 100)

            # 2. Dynamic Alarm Styling
            active_alarms = self.coord.alarms.get_active_list() if hasattr(self.coord, 'alarms') else {}
            if active_alarms:
                name, sev = next(iter(active_alarms.items()))
                UIUtils.update_text(self.alarm_banner, self._cache, "alarm_txt", f"FAULT: {name}")
                style = 'background-color: #7f1d1d; color: #fecaca; border-color: #f87171;' if sev == "CRITICAL" else 'background-color: #78350f; color: #fef3c7; border-color: #fbbf24;'
                UIUtils.update_style(self.alarm_banner, self._cache, "alarm_style", style)
            else:
                UIUtils.update_text(self.alarm_banner, self._cache, "alarm_txt", "SYSTEM OPERATIONAL")
                UIUtils.update_style(self.alarm_banner, self._cache, "alarm_style", 'background-color: #064e3b; color: #a7f3d0; border-color: #10b981;')

            # 3. Limb Iteration
            for pid, limb in GLOBAL_TWIN.limbs.items():
                # Stale Greying (10s Timeout)
                is_stale = (now - limb.last_update) > 10.0
                if pid in self.limb_cards:
                    UIUtils.update_classes(self.limb_cards[pid], self._cache, f"stale_{pid}", "opacity-50 grayscale" if is_stale else "", remove="opacity-50 grayscale")

                # --- NEW: Synapse Bus / Part Detection Flash Trigger ---
                if getattr(limb, 'ui_flash_trigger', False):
                    if pid == 2 and hasattr(self, 'scan_indicator'):
                        # 1. Trigger the red flash
                        self.scan_indicator.classes('bg-red-900 border-red-500', remove='bg-black border-slate-800')
                        self.scan_label.set_text('PART DETECTED!')
                        self.scan_label.classes('text-white', remove='text-emerald-600')
                        
                        # 2. Acknowledge the trigger so it doesn't loop
                        limb.ui_flash_trigger = False 
                        
                        # 3. Schedule the cleanup (return to normal) after 0.5 seconds
                        ui.timer(0.5, lambda: self.scan_indicator.classes('bg-black border-slate-800', remove='bg-red-900 border-red-500'), once=True)
                        ui.timer(0.5, lambda: self.scan_label.set_text('CLEAR'), once=True)
                        ui.timer(0.5, lambda: self.scan_label.classes('text-emerald-600', remove='text-white'), once=True)

                # Status Label Colors
                if pid in self.status_labels:
                    lbl = self.status_labels[pid]
                    s_val = str(limb.remote_state).upper()
                    s_col = "#ef4444" 
                    if s_val == "FLOW": s_col = "#10b981"
                    elif s_val == "IDLE": s_col = "#f59e0b"
                    elif (now - limb.last_update) < 2.5: s_col = "#6366f1" 
                    UIUtils.update_style(lbl, self._cache, f"stat_col_{pid}", f'color: {s_col}')
                    UIUtils.update_text(lbl, self._cache, f"stat_txt_{pid}", s_val)

                # 4. Health Grid
                if pid in self.health_labels:
                    h = self.health_labels[pid]
                    lqi = getattr(limb, 'lqi', 100.0)
                    UIUtils.update_text(h['UPT'], self._cache, f"upt_{pid}", f"{limb.uptime}s")
                    UIUtils.update_text(h['LQI'], self._cache, f"lqi_{pid}", f"{lqi:.1f}%")
                    UIUtils.update_text(h['CE'],  self._cache, f"ce_{pid}",  f"{limb.crc_errors}")
                    UIUtils.update_text(h['V'],   self._cache, f"v_{pid}",   f"{limb.voltage:.2f}v")
                    UIUtils.update_text(h['VM'],  self._cache, f"vm_{pid}",  f"{limb.voltage_min:.2f}v")
                    UIUtils.update_text(h['WC'],  self._cache, f"wc_{pid}",  f"{limb.write_count}")
                    
                    # Missing telemetry pipelines connected to Digital Twin
                    UIUtils.update_text(h['T'],   self._cache, f"t_{pid}",   f"{limb.temp}C")
                    UIUtils.update_text(h['LA'],  self._cache, f"la_{pid}",  f"{limb.loop_avg}us")
                    UIUtils.update_text(h['LM'],  self._cache, f"lm_{pid}",  f"{limb.loop_max}us")
                    UIUtils.update_text(h['RA'],  self._cache, f"ra_{pid}",  f"{limb.resp_avg}ms")
                    UIUtils.update_text(h['RL'],  self._cache, f"rl_{pid}",  f"{limb.resp_max}ms")
                    UIUtils.update_text(h['IE'],  self._cache, f"ie_{pid}",  f"{limb.i2c_errors}")
                    UIUtils.update_text(h['CSE'], self._cache, f"cse_{pid}", f"{limb.chk_errors}")
                    UIUtils.update_text(h['RST'], self._cache, f"rst_{pid}", f"{limb.reset_cause}")
                    
                # 5. Actuator Verification
                for act_id, act in getattr(limb, 'actuators', {}).items():
                    key = (pid, act_id)
                    if key in self.actuator_labels:
                        lbl = self.actuator_labels[key]
                        v_state = getattr(act, 'verification_state', "UNMEASURED")
                        v_text, v_col = "UNM", "#475569"
                        if v_state == ms.ACT_CONFIRMED_ON: v_text, v_col = "ON", "#10b981"
                        elif v_state == ms.ACT_CONFIRMED_OFF: v_text, v_col = "OFF", "#64748b"
                        elif v_state == ms.ACT_VERIFYING: v_text, v_col = "VFY", "#fbbf24"
                        elif v_state == ms.ACT_FAULT_STALL: v_text, v_col = "STALL", "#ef4444"
                        UIUtils.update_text(lbl, self._cache, f"act_txt_{key}", v_text)
                        UIUtils.update_style(lbl, self._cache, f"act_col_{key}", f'color: {v_col}')
                        
                        icon_key = (pid, act_id, 'icon')
                        if icon_key in self.actuator_labels:
                            icon = self.actuator_labels[icon_key]
                            is_on = (v_state == ms.ACT_CONFIRMED_ON)
                            UIUtils.update_classes(icon, self._cache, f"icon_anim_{key}", "animate-spin" if is_on else "", remove="animate-spin")
                            UIUtils.update_classes(icon, self._cache, f"icon_col_{key}", "text-emerald-500" if is_on else "text-slate-700", remove="text-emerald-500 text-slate-700")

                # 6. Calibration Ratio (P3 Only)
                if pid == 3:
                    cal_key = (3, 'conveyor', 'cal')
                    if cal_key in self.actuator_labels:
                        mm_p = CALIBRATION.data['distributor'].get('mm_per_pulse', 0.05)
                        UIUtils.update_text(self.actuator_labels[cal_key], self._cache, "cal_lbl", f"Ratio: {mm_p:.4f} mm/p")

                # 7. Sensors
                sns_box = getattr(self, f"sensor_box_p{pid}", None)
                if sns_box:
                    if pid == 2 and hasattr(self, 'pulse_label'):
                        pc = limb.sensors.get('pulse_count')
                        val = getattr(pc, 'raw_value', 0) if pc else 0
                        UIUtils.update_text(self.pulse_label, self._cache, "pulse_val", f"{val:05d}")
                    for s_id, sensor_obj in limb.sensors.items():
                        val = getattr(sensor_obj, 'raw_value', sensor_obj)
                        key = (pid, s_id)
                        if key not in self.sensor_labels:
                            with sns_box:
                                with ui.row().classes('w-full justify-between items-center px-1'):
                                    ui.label(s_id.replace('_',' ')).classes('text-[10px] text-slate-500 font-black uppercase')
                                    self.sensor_labels[key] = ui.label(str(val)).classes('text-base font-black font-mono text-cyan-400 tracking-tighter')
                        else: UIUtils.update_text(self.sensor_labels[key], self._cache, f"sns_{key}", str(val))

                # 8. Formatted JSON Data Tables
                for key, uis, hashes in [('remote_config', self.config_uis, self.config_hashes), 
                                         ('remote_versions', self.version_uis, self.version_hashes)]:
                    data = getattr(limb, key, {})
                    sig = str(data)
                    if hashes.get(pid) != sig:
                        hashes[pid] = sig
                        container = uis.get(pid)
                        if container:
                            container.clear()
                            with container:
                                if not data: ui.label('NO DATA LOADED').classes('text-[9px] italic text-slate-700')
                                for k, v in sorted(data.items()):
                                    val_str = json.dumps(v, separators=(', ', ':')) if isinstance(v, (dict, list)) else str(v)
                                    val_str = val_str.replace('\n', ' ').replace('\r', '').strip()
                                    with ui.row().classes('w-full gap-2 items-start h-auto'):
                                        ui.label(f"• {k}:").classes('text-[11px] font-bold text-slate-500 shrink-0')
                                        ui.label(val_str).classes('text-[11px] font-mono text-cyan-400 break-all')

            # 9. Flight Recorder Logic (with Purple Button Flash)
            processed = 0
            while len(STREAM_ROUTER.gui_log_buffer) > 0 and processed < 100:
                entry = STREAM_ROUTER.gui_log_buffer.popleft(); processed += 1
                lvl, tag, msg, fk = self.log_manager.process_entry(entry, self.log_filters)
                
                # Feedback logic for hidden logs
                if not lvl:
                    fk_hidden = 'E' if entry.get('lvl') == 'C' else entry.get('lvl', 'I')
                    btn_name = f"btn_{fk_hidden.lower()}"
                    if hasattr(self, btn_name):
                        UIUtils.update_classes(getattr(self, btn_name), self._cache, f"flash_{fk_hidden}", "text-purple-400")
                    continue
                else:
                    btn_name = f"btn_{fk.lower()}"
                    if hasattr(self, btn_name):
                        UIUtils.update_classes(getattr(self, btn_name), self._cache, f"flash_{fk}", "", remove="text-purple-400")

                sig = self.log_manager.get_signature(tag, msg)
                if sig == self.log_manager.last_signature and self.log_manager.last_ui_element:
                    self.log_manager.last_count += 1
                    self.log_manager.last_ui_element.set_text(f"[{tag}] {msg} (x{self.log_manager.last_count})")
                    continue
                
                self.log_manager.last_signature, self.log_manager.last_count = sig, 1
                color = '#f87171' if lvl in {'E', 'C'} else '#fbbf24' if lvl == 'W' else '#22d3ee'
                with self.log_container:
                    el = ui.label(f"[{tag}] {msg}").style(f'color: {color}')
                    self.log_manager.last_ui_element = el
                    self.log_elements.append((el, fk))

            if len(self.log_elements) > 1200:
                for el, _ in self.log_elements[:200]: el.delete()
                self.log_elements = self.log_elements[200:]
            if self.auto_scroll: self.log_scroll.scroll_to(percent=1.0)
            
            # 10. Notification Queue Consumption
            if hasattr(self.coord, 'ui_notification_queue'):
                while not self.coord.ui_notification_queue.empty():
                    m, t = self.coord.ui_notification_queue.get_nowait(); ui.notify(m, type=t)
        except Exception as e: print(f"Update Tick Error: {e}")

    # =========================================================================
    # SECTION 7: INTERNAL UTILITIES
    # =========================================================================
    def _toggle_log_filter(self, key):
        """Toggles the visibility filter for specific log levels (D/I/W/E)."""
        self.log_filters[key] = not self.log_filters[key]
        self._refresh_log_filter_buttons()
        for el, fk in self.log_elements: el.set_visibility(self.log_filters.get(fk, True))

    def _refresh_log_filter_buttons(self):
        """Updates the visual state of filter buttons to reflect active filters."""
        def upd(btn, k, col): 
            if self.log_filters[k]: btn.classes(f'text-{col}-400 bg-slate-800', remove='text-slate-600 bg-transparent')
            else: btn.classes('text-slate-600 bg-transparent', remove=f'text-{col}-400 bg-slate-800')
        upd(self.btn_d, 'D', 'slate'); upd(self.btn_i, 'I', 'cyan'); upd(self.btn_w, 'W', 'amber'); upd(self.btn_e, 'E', 'red')

    def clear_logs(self): 
        """Wipes the 'Flight Recorder' visualization and resets the deduplication state."""
        self.log_container.clear(); self.log_elements = []
    
    def toggle_autoscroll(self): 
        """Enables or disables automatic scroll-to-bottom for the log stream."""
        self.auto_scroll = not self.auto_scroll; self.scroll_btn.props(f'color={"cyan" if self.auto_scroll else "slate-700"}')
    
    def build_imaging_block(self): 
        """[Placeholder] UI container for the Vision system output."""
        with ui.card().classes('bg-slate-950 border border-slate-900 h-full p-3'):
            ui.label('06 :: IMAGING CORE').classes('text-[10px] font-black text-cyan-400 uppercase tracking-widest')
            ui.icon('videocam_off', size='xl', color='slate-900').classes('mx-auto mt-6')