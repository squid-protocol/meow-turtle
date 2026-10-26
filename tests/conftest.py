"""
Pytest configuration and shared fixtures for Ninelives Core 0 test suite.
"""

import sys
import os
import asyncio
import pytest

# Ensure Core 0 Commander is accessible on sys.path
CORE0_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core0 - Commander"))
if CORE0_PATH not in sys.path:
    sys.path.insert(0, CORE0_PATH)

from lib.coordinator import SystemCoordinator
from lib.digital_twin import GLOBAL_TWIN
import lib.machine_states as ms

@pytest.fixture(scope="session")
async def hub():
    """
    Spawns a session-wide SystemCoordinator configured with simulated virtual fleet loopback.
    Cleanly starts background tasks and tears them down after all tests complete.
    """
    GLOBAL_TWIN.host_state = ms.STATE_BOOT
    ports = {1: "/dev/ttyAMA0", 2: "/dev/ttyAMA2", 3: "/dev/ttyAMA3"}
    coord = SystemCoordinator(ports, simulate=True)
    await coord.start()
    await asyncio.sleep(0.5)

    yield coord

    # Teardown
    await coord.stop()
    await asyncio.sleep(0.2)
