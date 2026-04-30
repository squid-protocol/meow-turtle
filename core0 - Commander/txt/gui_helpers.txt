# lib/gui_helpers.py - UI Primitives, Log Logic, & Industrial Modals
# PURPOSE: Offloads logic from gui.py to maintain performance and buffer-safety.
# COMPLIANCE: Core 0 Spec Sections 4, 16.4, 19, 20.2

"""
[Spec 19.0] Ninelives GUI Utility Library.

This module provides the architectural scaffolding for the NiceGUI dashboard. 
It encapsulates high-frequency delta-update logic, robust telemetry parsing, 
and complex interactive modals (Inspector and Calibration Wizard).

Architectural Roles:
1. Performance Optimization (Spec 19.5): Implements the 'Delta-State' strategy to minimize DOM reflows.
2. Robust Parsing (Spec 4.3): Leverages centralized lib.protocol_parser for consistency.
3. System Observability (Spec 9.3): Implements the Hardware Inspector for forensic auditing.
4. Spatial Integrity (Spec 16.4): Orchestrates the live movement-to-pulse calibration routine.
"""

from nicegui import ui
import asyncio
import time
import json
import datetime
from . import meowprotocol
from .digital_twin import GLOBAL_TWIN
from .calibration import CALIBRATION
from . import machine_states as ms
from . import protocol_parser # Spec 4.3: Centralized Protocol Translator

class UIUtils:
    """
    [Spec 19.5] Industrial UI Primitives.
    
    Provides static methods for efficient DOM manipulation. These methods 
    utilize a local cache to ensure that element properties (text, style, 
    visibility) are only updated when the underlying data has changed.
    """
    
    @staticmethod
    def update_text(element, cache, key, value):
        """
        [Spec 19.5] Delta-State Text Update.
        
        Updates the text content of a NiceGUI element only if the new value 
        differs from the cached state. Prevents expensive browser reflows 
        during 5Hz heartbeat ticks.

        Args:
            element (ui.element): The NiceGUI element to update.
            cache (dict): The local UI state cache for delta comparison.
            key (str): Unique identifier for the element's text property.
            value (any): The new value to be displayed.
        """
        if cache.get(key) != value:
            element.set_text(str(value))
            cache[key] = value

    @staticmethod
    def update_style(element, cache, key, style_str):
        """
        [Spec 19.5] Delta-State CSS Update.
        
        Updates the inline style of an element only on value change. Used 
        primarily for dynamic color-coding of health metrics and state badges.

        Args:
            element (ui.element): The NiceGUI element to style.
            cache (dict): The local UI state cache.
            key (str): Unique identifier for the element's style.
            style_str (str): The CSS style string to apply.
        """
        if cache.get(f"{key}_style") != style_str:
            element.style(style_str)
            cache[f"{key}_style"] = style_str

    @staticmethod
    def update_classes(element, cache, key, class_str, remove=None):
        """
        [Spec 19.5] Delta-State Tailwind Update.
        
        Manages Tailwind CSS classes dynamically. Supports atomic removal of 
        conflicting classes (e.g., swapping 'bg-green' for 'bg-red') based 
        on cached state.

        Args:
            element (ui.element): The NiceGUI element to modify.
            cache (dict): The local UI state cache.
            key (str): Unique identifier for the element's class state.
            class_str (str): The Tailwind classes to add.
            remove (str, optional): Tailwind classes to remove before adding new ones.
        """
        cache_key = f"{key}_cls"
        if cache.get(cache_key) != class_str:
            if remove: element.classes(remove=remove)
            element.classes(class_str)
            cache[cache_key] = class_str

    @staticmethod
    def update_vis(element, cache, key, visible):
        """
        [Spec 19.5] Delta-State Visibility Management.
        
        Toggles element visibility on change. Used to prune complex UI 
        components (like log filters or debug tables) when not in use.

        Args:
            element (ui.element): The NiceGUI element to toggle.
            cache (dict): The local UI state cache.
            key (str): Unique identifier for the element's visibility.
            visible (bool): The target visibility state.
        """
        if cache.get(f"{key}_vis") != visible:
            element.set_visibility(visible)
            cache[f"{key}_vis"] = visible

    @staticmethod
    def parse_kv_payload(payload_str):
        """
        [Spec 4.3] Key-Value Parser Proxy.
        
        Offloads parsing logic to the centralized protocol_parser module. This 
        ensures that all components across the Ninelives architecture decode 
        hardware telemetry using the same hardened logic.

        Args:
            payload_str (str): The raw protocol payload string.

        Returns:
            dict: A Python dictionary containing the parsed keys and typed values.
        """
        return protocol_parser.parse_kv_payload(payload_str)

class LogManager:
    """
    [Spec 19.5] Flight Recorder Management Engine.
    
    Responsible for log deduplication, signature matching, and maintaining 
    browser memory safety. It ensures that 'Log Storms' do not exhaust 
    client-side resources.
    """
    def __init__(self, debug_enabled=False):
        """
        Initializes the LogManager with deduplication state.

        Args:
            debug_enabled (bool): Whether to permit DEBUG level logs in the UI.
        """
        self.last_signature = None
        self.last_ui_element = None
        self.last_count = 1
        self.debug_enabled = debug_enabled

    def get_signature(self, tag, msg):
        """
        [Spec 19.5] Log Deduplication logic.
        
        Identifies repeating patterns in hardware errors to collapse them into 
        a single UI line with a counter.

        Args:
            tag (str): The 5-character source tag.
            msg (str): The log message content.

        Returns:
            str: A unique signature string used for identifying repeats.
        """
        if "Packet lost" in msg: return f"{tag}|PKT_LOST"
        if "SEQ SKIP" in msg: return f"{tag}|SEQ_SKIP"
        if "CRC ERROR" in msg: return f"{tag}|CRC_ERR"
        return f"{tag}|{msg}"

    def process_entry(self, entry, filters):
        """
        Filters and formats raw log entries for display.
        
        Determines the priority (level), source (tag), and content of an entry.
        Returns None if the entry is suppressed by active UI filters.

        Args:
            entry (dict|str): The log entry from the telemetry router.
            filters (dict): Map of log levels to boolean visibility states.

        Returns:
            tuple: (level, tag, message, filter_key) or (None, None, None, None)
        """
        if isinstance(entry, dict):
            lvl = entry.get('lvl', 'I')
            tag = entry.get('tag', 'SYS')
            msg = entry.get('msg', "")
        else:
            msg = str(entry)
            tag = 'RAW'
            lvl = 'E' if 'ERROR' in msg or 'CRITICAL' in msg else 'W' if 'WARN' in msg else 'I'
        
        # Level Normalization for filtering
        filter_key = 'E' if lvl == 'C' else lvl
        if not filters.get(filter_key, True):
            return None, None, None, None
            
        return lvl, tag, msg, filter_key

class GUIModals:
    """
    [Spec 19.0] Industrial HMI Modals.
    
    Encapsulates large interactive UI blocks that require dedicated state 
    management, such as the Hardware Inspector and the Spatial Calibration Wizard.
    """
    
    @staticmethod
    def open_inspector(pid):
        """
        [Spec 9.3] Comprehensive Hardware Inspector.
        
        Provides a detailed diagnostic view of a specific Pico Limb, displaying 
        system identity, uptime, firmware manifests, and runtime configuration.

        Args:
            pid (int): The Port ID of the limb to inspect.
        """
        limb = GLOBAL_TWIN.limbs.get(pid)
        if not limb: return
        
        with ui.dialog() as dialog, ui.card().classes('bg-slate-900 border border-slate-700 w-[500px] p-0 overflow-hidden'):
            with ui.row().classes('w-full bg-slate-950 p-2 border-b border-slate-800 items-center justify-between'):
                ui.label(f"HARDWARE INSPECTOR :: PICO {pid}").classes('text-xs font-black text-cyan-400 tracking-widest')
                ui.button(icon='close', on_click=dialog.close).props('flat dense size=sm color=slate-500')
            
            with ui.column().classes('p-4 w-full gap-4 max-h-[80vh] overflow-y-auto'):
                # 1. Identity Block
                with ui.column().classes('gap-1'):
                    ui.label('SYSTEM IDENTITY').classes('text-[10px] font-black text-slate-500')
                    with ui.grid(columns=2).classes('w-full gap-x-4 gap-y-1 bg-black/20 p-2 rounded'):
                        ui.label('Role:').classes('text-xs text-slate-400')
                        ui.label(limb.name).classes('text-xs font-bold text-white')
                        ui.label('Uptime:').classes('text-xs text-slate-400')
                        ui.label(f"{limb.uptime} seconds").classes('text-xs font-mono text-cyan-400')
                        ui.label('Firmware:').classes('text-xs text-slate-400')
                        ui.label(limb.firmware_version).classes('text-xs font-mono text-emerald-400')

                # 2. Version Manifest (Spec 9.3 Forensic Record)
                ui.label('VERSION MANIFEST').classes('text-[10px] font-black text-slate-500')
                v_box = ui.column().classes('w-full bg-black/40 p-2 rounded border border-slate-800 max-h-[150px] overflow-y-auto gap-0.5')
                versions = getattr(limb, 'remote_versions', {})
                with v_box:
                    if not versions: ui.label('No manifest loaded.').classes('text-[10px] italic text-slate-600')
                    for k, v in sorted(versions.items()):
                        with ui.row().classes('w-full justify-between no-wrap'):
                            ui.label(k).classes('text-[10px] font-bold text-slate-500')
                            ui.label(str(v)).classes('text-[10px] font-mono text-cyan-500')

                # 3. Runtime Configuration Block
                ui.label('RUNTIME CONFIGURATION').classes('text-[10px] font-black text-slate-500')
                c_box = ui.column().classes('w-full bg-black/40 p-2 rounded border border-slate-800 max-h-[200px] overflow-y-auto gap-1')
                configs = getattr(limb, 'remote_config', {})
                with c_box:
                    if not configs: ui.label('No config loaded.').classes('text-[10px] italic text-slate-600')
                    for k, v in sorted(configs.items()):
                        with ui.row().classes('w-full gap-2 items-start h-auto'):
                            ui.label(f"• {k}:").classes('text-[11px] font-bold text-slate-500 shrink-0')
                            val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                            ui.label(val_str).classes('text-[11px] font-mono text-amber-400 break-all')

            with ui.row().classes('w-full p-2 bg-slate-950 border-t border-slate-800 justify-end gap-2'):
                ui.button('REFRESH ALL', on_click=lambda: (
                    GLOBAL_TWIN.coordinator._bg_task(GLOBAL_TWIN.coordinator.fleet.send(pid, meowprotocol.MSG_TYPE_CMD_VER, "")),
                    GLOBAL_TWIN.coordinator._bg_task(GLOBAL_TWIN.coordinator.fleet.send(pid, meowprotocol.MSG_TYPE_CMD_CFG, ""))
                )).props('outline dense size=sm color=cyan')
            dialog.open()

    @staticmethod
    def open_calibration_wizard(coord):
        """
        [Spec 16.4] Interactive Spatial Calibration Wizard.
        
        Guides the operator through the calculation of 'mm_per_pulse' by 
        executing live test runs and committing physical ratios to storage.

        Args:
            coord (SystemCoordinator): The active system coordinator instance.
        """
        if GLOBAL_TWIN.host_state != ms.STATE_DEV:
            coord._notify("ENABLE DEV MODE FIRST", type='negative'); return

        with ui.dialog() as dialog, ui.card().classes('w-[450px] bg-slate-900 border border-slate-700 p-0 overflow-hidden'):
            wizard = {'running': False, 'start_p': 0, 'delta_p': 0}
            
            def get_current_pulses():
                """Internal helper to retrieve pulse count from the Distributor Twin."""
                p3 = GLOBAL_TWIN.limbs.get(3)
                if p3:
                    for k in ['pulse_count', 'enc', 'fg']:
                        v = p3.sensors.get(k)
                        if v is not None: return getattr(v, 'raw_value', 0)
                return 0

            async def toggle_test():
                """Manages the two-phase calibration run (Start/Capture)."""
                if not wizard['running']:
                    # Phase 1: Begin Capture
                    wizard['start_p'] = get_current_pulses()
                    wizard['running'] = True
                    await coord.fleet.send(3, meowprotocol.MSG_TYPE_CMD, "SET:conveyor=0.75")
                    btn_run.props('color=red icon=stop').set_text('STOP TEST RUN')
                    lbl_status.set_text("MOTOR RUNNING - CAPTURING PULSES...").classes('text-emerald-400')
                else:
                    # Phase 2: Finalize Delta
                    wizard['running'] = False
                    await coord.fleet.send(3, meowprotocol.MSG_TYPE_CMD, "SET:conveyor=0.0")
                    wizard['delta_p'] = abs(get_current_pulses() - wizard['start_p'])
                    btn_run.disable()
                    lbl_status.set_text(f"TEST COMPLETE: {wizard['delta_p']} Pulses Captured").classes('text-white')
                    input_col.set_visibility(True)

            def finalize():
                """Calculates and saves the mm/pulse ratio based on operator measurement."""
                try:
                    dist = float(dist_input.value)
                    if dist > 0 and wizard['delta_p'] > 0:
                        CALIBRATION.update_pulse_ratio(dist, wizard['delta_p'])
                        coord._notify(f"Calibration Saved: {dist/wizard['delta_p']:.5f} mm/p", type='positive')
                        dialog.close()
                except: coord._notify("Invalid Distance Input", type='negative')

            # UI Component Layout
            with ui.row().classes('w-full bg-slate-950 p-3 border-b border-slate-800 items-center justify-between'):
                ui.label('CONVEYOR SPATIAL CALIBRATION').classes('text-sm font-black text-cyan-400')
                ui.button(icon='close', on_click=dialog.close).props('flat dense color=slate-500')

            with ui.column().classes('p-4 w-full gap-4'):
                ui.label("This wizard determines the exact movement ratio by running the belt and measuring physical distance.").classes('text-xs text-slate-400 italic')
                
                btn_run = ui.button('START CALIBRATION RUN', on_click=toggle_test).classes('w-full py-4 text-lg font-black')
                lbl_status = ui.label('Ready to begin.').classes('text-center w-full font-mono text-slate-500')
                
                input_col = ui.column().classes('w-full hidden bg-black/40 p-4 rounded border border-slate-800 gap-3')
                with input_col:
                    ui.label("STEP 2: Enter measured distance").classes('text-[10px] font-bold text-amber-500')
                    dist_input = ui.input('Physical Distance (mm)').props('type=number outlined dark dense suffix="mm"')
                    ui.button('CALCULATE & COMMIT TO DISK', on_click=finalize).props('color=cyan').classes('w-full font-bold')

            # Ensure motor is stopped if dialog is closed prematurely
            dialog.on('close', lambda: asyncio.create_task(coord.fleet.send(3, meowprotocol.MSG_TYPE_CMD, "SET:conveyor=0.0")))
            dialog.open()