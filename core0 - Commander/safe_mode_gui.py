# safe_mode_gui.py - The "Lifeboat" (v1.0)
# PURPOSE: Minimal UI that runs when app.py crashes repeatedly.
# DEPENDENCIES: Minimal (No lib/machine_model, No Serial).
# COMPLIANCE: Unbrickable Standard Section 10.3

import os
from nicegui import ui

# Path to the critical log file
LOG_FILE = "logs/core0_system.log"


def read_last_logs(n=50):
    if not os.path.exists(LOG_FILE):
        return ["Log file not found."]
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            return lines[-n:]
    except Exception as e:
        return [f"Error reading logs: {e}"]


def restart_system():
    # Trigger systemd restart
    os.system("sudo systemctl restart ninelives-core0")


def reboot_pi():
    os.system("sudo reboot")


# --- UI LAYOUT ---
with ui.card().classes(
    "w-full h-screen bg-red-900 flex flex-col items-center justify-center p-8 gap-4"
):
    ui.icon("warning", size="xl", color="white")
    ui.label("SAFE MODE ACTIVE").classes("text-4xl font-black text-white")

    ui.label("The main application failed to start.").classes("text-white text-lg")

    # Log Viewer
    with ui.expansion("View Crash Logs", icon="article").classes(
        "w-full max-w-2xl bg-red-800 text-white"
    ):
        log_text = "".join(read_last_logs())
        ui.code(log_text).classes("w-full h-64 text-xs")

    # Actions
    with ui.row().classes("gap-4 mt-8"):
        ui.button("RESTART APP", on_click=restart_system).props(
            "color=white text-color=red-900 size=lg"
        )
        ui.button("REBOOT PI", on_click=reboot_pi).props(
            "color=red-700 text-color=white size=lg"
        )

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="SAFE MODE - Ninelives", port=8080, dark=True)
