# config/debug.py - Global Debug Configuration
# PURPOSE: Centralized control for system logging and verbosity.
# ARCHITECTURE: 'DEBUG_GLOBAL' acts as a master breaker. If False, all other flags are forced False.

# --- MASTER SWITCH ---
DEBUG_GLOBAL = True

# --- MODULE SPECIFIC FLAGS ---
DEBUG_TRANSPORT = True   # Switchboard.py: Connection status, timeouts
DEBUG_PACKETS   = False    # Switchboard.py: Raw hex dump of packets (Verbose!)
DEBUG_LOGIC     = False    # App.py: State machine transitions, event queue
DEBUG_TWIN      = False   # Machine_model.py: Sensor updates
DEBUG_GUI       = True   # Gui.py: UI performance/updates
DEBUG_ALARMS    = True    # App.py: Alarm Manager monitoring

# --- FILTERS ---
IGNORE_ECHOES   = True    # Switchboard.py: Ignore packets from self

# --- HIERARCHY ENFORCEMENT ---
# This ensures that if the Master Switch is OFF, no subsystem logs leak through.
# This prevents individual modules from needing to check DEBUG_GLOBAL manually.
if not DEBUG_GLOBAL:
    DEBUG_TRANSPORT = False
    DEBUG_PACKETS   = False
    DEBUG_LOGIC     = False
    DEBUG_TWIN      = False
    DEBUG_GUI       = False
    DEBUG_ALARMS    = False