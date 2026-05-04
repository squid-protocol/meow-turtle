# config/debug.py - Global Debug Configuration
# PURPOSE: Centralized control for system logging and verbosity.
# ARCHITECTURE: 'DEBUG_GLOBAL' acts as a master breaker. If False, all other flags are forced False.

# --- MASTER SWITCH ---
DEBUG_GLOBAL = True

# --- MODULE SPECIFIC FLAGS ---
DEBUG_TRANSPORT = True   # Keep ON: Good to know if a Pico physically unplugs
DEBUG_PACKETS   = False  # TURN OFF: Silences the 15Hz polling spam!
DEBUG_LOGIC     = True   # TURN ON: Crucial for seeing your custom Python scripts fire
DEBUG_TWIN      = False  # Keep OFF: Unless you want to see every single sensor value printed to console
DEBUG_GUI       = True   # Keep ON
DEBUG_ALARMS    = True   # Keep ON: Critical safety visibility

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