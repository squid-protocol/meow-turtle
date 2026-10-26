# config/settings.py
# Purpose: Core Hardware Configuration

import os

# Serial Ports
# Mapped to Picos: 1=Loader, 2=Gatekeeper, 3=Distributor
SERIAL_PORTS = {1: "/dev/ttyAMA0", 2: "/dev/ttyAMA2", 3: "/dev/ttyAMA3"}

# Fleet Simulation Mode (enable via MEOW_SIMULATE=1 env var or --simulate CLI flag)
SIMULATE_FLEET = os.environ.get("MEOW_SIMULATE", "").lower() in ("1", "true", "yes")

# Network / API Keys (Future)
API_KEY = ""
DB_HOST = "localhost"

