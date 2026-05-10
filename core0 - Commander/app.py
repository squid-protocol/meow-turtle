# app.py - Ninelives Core 0 Launcher (v6.9.2 Architectural Standard)
# ROLE: High-Availability Bootstrap, GUI Logging Bridge, and Service Lifecycle.
# COMPLIANCE: Spec 10 (Unbrickable Standard), Spec 6.0 (Entry Point), Spec 10.3 (Safe Mode Bridge)
# VERSION: v6.9.2 - Decoupled Coordinator Launch.

"""
[Spec 6.0] Core 0 Main Entry Point.

This module serves as the primary bootstrap for the Ninelives.shell environment. 
It initializes the logging infrastructure, establishes the NiceGUI server, 
and launches the SystemCoordinator as a background service.

Architectural Role:
1. Lifeboat: Handles configuration failures by loading hardcoded safe defaults.
2. Bridge: Routes Python standard logs into the asynchronous Flight Recorder.
3. Host: Serves the high-density vertical dashboard for human operators.
"""

import asyncio
import logging
import multiprocessing as mp
from nicegui import ui, app

from lib.rp5_logger import logger
from lib.telemetry_router import STREAM_ROUTER
from lib.coordinator import SystemCoordinator
from gui import SorterGUI

# ------------------------------------------------------------------------------
# 1. CONFIG HYGIENE (Spec 10.4)
# ------------------------------------------------------------------------------
try:
    import config.settings
    SERIAL_PORTS = config.settings.SERIAL_PORTS
except Exception as e:
    """
    [Spec 10.4] Configuration Anti-Poison Logic.
    If the filesystem is corrupt or the settings file is missing, the system
    loads a minimal 'Lifeboat' configuration to maintain connectivity.
    """
    logger.critical(f"Config Import Failed: {e}. Loading SAFE_CONFIG.")
    SERIAL_PORTS = {1: '/dev/ttyAMA0', 2: '/dev/ttyAMA2', 3: '/dev/ttyAMA3'}

# ==============================================================================
# SECTION 2: LOGGING INFRASTRUCTURE
# ==============================================================================

class GuiLogBridge(logging.Handler):
    """
    [Spec 19.5] Industrial GUI Logging Bridge.
    
    Transforms standard Python logging records into structured dictionary entries
    compatible with the Asynchronous Flight Recorder (STREAM_ROUTER).
    
    Responsibilities:
    - Level Normalization: Converts logging.LEVEL to 'C', 'E', 'W', 'I', 'D'.
    - Tagging: Truncates logger names to 5-character uppercase tags (e.g., 'COORD').
    - Buffer Management: Appends formatted strings to the GUI consumer queue.
    """
    def emit(self, record):
        """
        [Spec 19.5.1] Record Interception and Transformation.
        
        This method is invoked by the Python logging framework whenever a message
        is logged. It performs real-time sanitization and schema mapping before
        injecting the record into the global STREAM_ROUTER buffer.

        Args:
            record (logging.LogRecord): The raw event record containing message, 
                                        level, and source metadata.
        """
        try:
            msg = self.format(record)
            lvl_char = 'I'
            if record.levelno >= logging.CRITICAL: lvl_char = 'C'
            elif record.levelno >= logging.ERROR: lvl_char = 'E'
            elif record.levelno >= logging.WARNING: lvl_char = 'W'
            elif record.levelno == logging.DEBUG: lvl_char = 'D'
            
            # Create a 5-char tag from the logger name for the Flight Recorder
            tag = record.name if len(record.name) < 6 else record.name[:5].upper()
            
            STREAM_ROUTER.gui_log_buffer.append({
                "ts": record.created,
                "src": "SYS",
                "lvl": lvl_char,
                "tag": tag,
                "msg": msg
            })
        except Exception:
            self.handleError(record)

def setup_logging():
    """
    Initializes the cross-domain logging synchronization.
    Attaches the GuiLogBridge to the root logger to ensure that all internal
    system decisions (Coordinator, Logic, Safety) are visible to the Operator GUI.
    """
    root_logger = logging.getLogger()
    bridge = GuiLogBridge()
    bridge.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(bridge)
    logger.info("GUI Log Bridge Attached.")

# ==============================================================================
# SECTION 3: SYSTEM INITIALIZATION
# ==============================================================================

# 1. Initialize Logging
setup_logging()

# 2. Global System Coordinator (Singleton)
# [Spec 5.1] The Coordinator acts as the central hub (The Hub).
# We instantiate this here to ensure it persists for the lifetime of the server.
coordinator = SystemCoordinator(SERIAL_PORTS)

@ui.page('/')
def index_page():
    """
    [Spec 6.0] NiceGUI Client Landing Page.
    
    Instantiates the SorterGUI for every new browser session. 
    By binding the GUI class to the singleton 'coordinator', multiple clients
    can observe the same 'Digital Twin' state simultaneously.
    """
    SorterGUI(coordinator)

# ------------------------------------------------------------------------------
# 3.1 Startup Hook
# ------------------------------------------------------------------------------
async def startup_service():
    """
    [Spec 7.2] Service Startup Sequence.
    
    Triggered by the NiceGUI server once the event loop is ready.
    This initiates the hardware discovery handshake and launches the 
    high-frequency Safety and Logic background tasks.
    """
    logger.info("[App] Service Startup: Booting Coordinator...")
    await coordinator.start()

app.on_startup(startup_service)

# ------------------------------------------------------------------------------
# 3.2 Shutdown Hook (The Anti-Zombie Protocol)
# ------------------------------------------------------------------------------
async def shutdown_service():
    """
    [Spec 7.3] Service Teardown Sequence.
    
    Triggered natively by NiceGUI when it catches a SIGINT (Ctrl+C) or app.shutdown().
    Forces the Coordinator to drop all hardware locks, close serial ports,
    and cleanly terminate background asyncio tasks before the OS kills the process.
    """
    logger.warning("[App] Shutdown Signal Caught. Initiating Graceful Hardware Teardown...")
    if hasattr(coordinator, 'stop'):
        await coordinator.stop()
    logger.info("[App] Teardown Complete. Safe to exit.")

app.on_shutdown(shutdown_service)

# ==============================================================================
# SECTION 4: MAIN ENTRY POINT
# ==============================================================================
if __name__ in {"__main__", "__mp_main__"}:
    """
    [Spec 10.1] Indestructible Entry Point.
    
    Launches the web server using the 'spawn' method to ensure cross-platform
    compatibility for the vision/multiprocessing components.
    
    Configuration Notes:
    - reload=False: Prevents hardware state loss from accidental code edits.
    - dark=True: Standard Industrial high-contrast dashboard theme.
    """
    # Compliance: Multiprocessing method must be 'spawn'
    mp.set_start_method('spawn', force=True)
    
    ui.run(
        title="Ninelives Core 0",
        port=8080,
        reload=False, 
        dark=True,
        show=False
    )