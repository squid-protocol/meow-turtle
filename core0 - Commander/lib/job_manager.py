# lib/job_manager.py - Ninelives Core 0 (v6.3.1 Production Standard)
# ROLE: The Executive Assistant. Profiles, recipes, and complex state-transitions.
# COMPLIANCE: Spec 13 (States), Spec 14 (Profiles), Spec 16.4 (Calibration Wizard)
# VERSION: v6.3.1 - Phase 2: Calibration Sequence Implementation.

"""
[Spec 12.0] Ninelives Job Management System.

The JobManager serves as the 'Executive Assistant' of the Ninelives architecture. 
It is responsible for orchestrating complex, multi-stage state transitions and 
managing the 'Recipes' (Profiles) that define the machine's physical behavior.

Key Architectural Roles:
1. Arming Orchestration (Spec 7.2): Manages the transition from IDLE to FLOW.
2. Spatial Calibration (Spec 16.4): Executes automated belt pulse auditing.
3. Atomic Handshake (Spec 4.3.6.2): Verifies that configuration parameters are latched.
4. Profile Management (Spec 14.0): Validates and applies JSON-based operational parameters.
5. Adaptive Shutdown (Spec 13.2): Executes staggered stop sequences to prevent jams.
"""

import asyncio
import time
import json
import os
from lib.rp5_logger import logger
from lib.digital_twin import GLOBAL_TWIN
from lib.calibration import CALIBRATION
from lib import meowprotocol
from lib import machine_states as ms

class JobManager:
    """
    [Spec 12.0] The Job Manager.
    
    Orchestrates high-level system behaviors like arming sequences, 
    recipe validation, and the automated Spatial Calibration Wizard.
    """

    def __init__(self, coordinator):
        """
        Initializes the Job Manager and locates the profile manifest.
        
        :param coordinator: Reference to the SystemCoordinator (The Hub).
        """
        self.coord = coordinator
        self.current_profile = None
        self.active_job = None
        
        # Path Strategy (Spec 10.4): Try config subfolder, then local
        self.profile_path = os.path.join("config", "profiles.json")
        if not os.path.exists(self.profile_path):
            self.profile_path = "profiles.json"

        logger.info("[Job] JobManager Initialized with Atomic Handshake and Calibration logic.")

    # --------------------------------------------------------------------------
    # CORE ORCHESTRATION: THE ARMING SEQUENCE
    # --------------------------------------------------------------------------
    async def run_arming_sequence(self, profile_name):
        """
        [Spec 7.2] Orchestrates the transition: IDLE -> ARMING -> FLOW.
        
        This method enforces a strict 5-stage startup protocol:
        1. Safety Interlock Verification (Spec 18.2).
        2. Profile Validation (Spec 14.1).
        3. Configuration Dispatch (Atomic Handshake Phase 1).
        4. Hardware Verification (Atomic Handshake Phase 2).
        5. Staggered Ignition (Upstream -> Downstream sequence).
        """
        if GLOBAL_TWIN.host_state == ms.STATE_ERROR:
            self.coord._notify("Arming Blocked: System in ERROR. Reset required.", type='negative')
            return False
            
        if not self.coord.safety.is_safe_to_arm():
            self.coord._notify("Arming Blocked: Critical hardware alarms active.", type='negative')
            return False

        if self.active_job:
            self.coord._notify(f"Arming Blocked: {self.active_job} in progress.", type='warning')
            return False

        self.active_job = "ARMING"
        GLOBAL_TWIN.set_state(ms.STATE_ARMING)
        self.coord._notify(f"ARMING: Preparing {profile_name}...", type='info')
        
        profile_data = self._load_profile(profile_name)
        if not profile_data:
            GLOBAL_TWIN.set_state(ms.STATE_IDLE)
            self.active_job = None
            return False

        try:
            pending_acks = await self._dispatch_configs(profile_data)
            success = await self._verify_hardware_readiness(pending_acks)
            
            if not success:
                self.coord._notify("Arming Failed: Hardware failed to acknowledge profile.", type='negative')
                GLOBAL_TWIN.set_state(ms.STATE_ERROR)
                return False

            logger.info("[Job] Ignition Phase: Starting kinetic stream...")
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, "FLOW") 
            await self.coord.send_physical(2, meowprotocol.MSG_TYPE_CMD, "FLOW") 
            await asyncio.sleep(0.5) 
            await self.coord.send_physical(1, meowprotocol.MSG_TYPE_CMD, "FLOW") 
            
            GLOBAL_TWIN.set_state(ms.STATE_FLOW)
            self.coord._notify(f"SUCCESS: System Flowing ({profile_name})", type='positive')
            return True

        except Exception as e:
            logger.error(f"[Job] Arming Sequence Failure: {e}")
            self.coord._notify("ARMING_CRASH", type='negative')
            GLOBAL_TWIN.set_state(ms.STATE_ERROR)
            return False
        finally:
            self.active_job = None

    # --------------------------------------------------------------------------
    # PHASE 2: CALIBRATION KINETICS (Spec 16.4)
    # --------------------------------------------------------------------------
    async def run_calibration_sequence(self):
        """
        [Spec 16.4] Automated Spatial Calibration Sequence.
        Executes a controlled kinetic burst to measure pulse-to-distance ratios.
        
        Logic:
        1. Verify safety state (IDLE/DEV required).
        2. Record baseline odometer from P2 (Gatekeeper).
        3. Drive P3 (Distributor) belt at 0.5 duty for 5.0s.
        4. Calculate pulse delta and update the Digital Twin via CALIBRATION.
        """
        if GLOBAL_TWIN.host_state not in [ms.STATE_IDLE, ms.STATE_DEV]:
            self.coord._notify("Calibration Blocked: System must be IDLE or DEV.", type='negative')
            return

        if self.active_job:
            self.coord._notify(f"Job Collision: {self.active_job} is running.", type='warning')
            return

        self.active_job = "CALIBRATION_WIZARD"
        try:
            self.coord._notify("Calibration: Capturing baseline pulses...", type='info')
            
            # Identify Odometer Source (P2 Gatekeeper)
            p2_limb = GLOBAL_TWIN.limbs.get(2)
            if not p2_limb:
                raise Exception("Gatekeeper (P2) Offline. Odometer inaccessible.")
            
            # Capture Start State
            start_pulses = p2_limb.sensors.get('pulse_count')
            start_val = getattr(start_pulses, 'raw_value', 0) if start_pulses else 0

            self.coord._notify("Calibration: 5s Kinetic Burst active...", type='warning')
            
            # Ignition: Drive Distributor Conveyor
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, "ACT:conveyor=0.5")
            
            # Precise timing window for measurement
            await asyncio.sleep(5.0)
            
            # Shutdown
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, "ACT:conveyor=0.0")
            self.coord._notify("Calibration: Burst complete. Settling...", type='info')
            await asyncio.sleep(1.5) # Allow encoder lag to settle

            # Capture End State
            end_pulses = p2_limb.sensors.get('pulse_count')
            end_val = getattr(end_pulses, 'raw_value', 0) if end_pulses else 0
            
            pulse_delta = abs(end_val - start_val)
            
            if pulse_delta < 50:
                raise Exception(f"Insufficient Motion ({pulse_delta}p). Check belt/P2 link.")

            # Calculate New Ratio (Standard test length: 250mm)
            test_distance_mm = 250.0
            new_ratio = test_distance_mm / pulse_delta
            
            # Atomic Update to Calibration Library
            CALIBRATION.update_pulse_ratio('distributor', new_ratio)
            CALIBRATION.save()
            
            self.coord._notify(f"CALIBRATION SUCCESS: {new_ratio:.4f} mm/p", type='positive')
            logger.info(f"[Job] Calibration Wizard Success. Delta: {pulse_delta}p, Ratio: {new_ratio:.6f}")

        except Exception as e:
            logger.error(f"[Job] Calibration Wizard Failed: {e}")
            self.coord._notify(f"CALIBRATION ERROR: {str(e)}", type='negative')
            # Safety: Force Belt Stop
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, "ACT:conveyor=0.0")
        finally:
            self.active_job = None

    # --------------------------------------------------------------------------
    # PROFILE & CONFIG LOGIC
    # --------------------------------------------------------------------------
    def _load_profile(self, name):
        """[Spec 14.1] Loads and performs safety bounds-checking on profile parameters."""
        try:
            with open(self.profile_path, 'r') as f:
                profiles = json.load(f)
            
            data = profiles.get(name)
            if not data:
                logger.error(f"[Job] Profile '{name}' missing from manifest.")
                return None
            
            dist_cfg = data.get('distributor', {})
            if 'belt_speed' in dist_cfg:
                speed = float(dist_cfg['belt_speed'])
                if speed < 0 or speed > 1.0:
                    logger.error(f"[Job] CRITICAL: Profile speed {speed} is OOB.")
                    return None
                    
            return data
        except Exception as e:
            logger.error(f"[Job] Profile Load Fail: {e}")
            return None

    async def _dispatch_configs(self, profile):
        """[Spec 4.3.6.2 Phase 1] Dispatches configuration parameters to the fleet."""
        handshake_list = []
        
        loader_cfg = profile.get('loader', {})
        if 'vibration_freq' in loader_cfg:
            f_val = loader_cfg['vibration_freq']
            seq = await self.coord.send_physical(1, meowprotocol.MSG_TYPE_SET_CFG, f"CFG:ACT:feeder:freq={f_val}")
            if seq: handshake_list.append((1, seq))
            
        if 'flow_rate' in loader_cfg:
            r_val = loader_cfg['flow_rate']
            seq = await self.coord.send_physical(1, meowprotocol.MSG_TYPE_SET_CFG, f"CFG:ACT:feeder:flow={r_val}")
            if seq: handshake_list.append((1, seq))
        
        dist_cfg = profile.get('distributor', {})
        if 'belt_speed' in dist_cfg:
            s_val = dist_cfg['belt_speed']
            seq = await self.coord.send_physical(3, meowprotocol.MSG_TYPE_SET_CFG, f"CFG:ACT:conveyor:speed={s_val}")
            if seq: handshake_list.append((3, seq))
            
        return handshake_list

    async def _verify_hardware_readiness(self, pending_acks):
        """[Spec 4.3.6.2 Phase 2] Verifies receipt of configuration parameters."""
        if not pending_acks:
            return True

        timeout_at = time.time() + 3.0
        while time.time() < timeout_at:
            all_ready = True
            for pid, seq in pending_acks:
                limb = GLOBAL_TWIN.limbs.get(pid)
                if limb and limb.last_acked_seq != seq:
                    all_ready = False
                    break
            
            if all_ready:
                logger.info("[Job] Atomic Handshake Verified. Fleet Ready.")
                return True
                
            for limb in GLOBAL_TWIN.limbs.values():
                if limb.remote_state == ms.STATE_ERROR:
                    logger.error(f"[Job] Arming Aborted: Pico {limb.id} reported ERROR state.")
                    return False
            
            await asyncio.sleep(0.1)
            
        logger.warning("[Job] Handshake TIMEOUT. One or more Picos failed to ACK.")
        return False

    async def enter_idle_sequence(self):
        """[Spec 13.2] Adaptive Stop Management (Production Clear-Out)."""
        was_in_flow = (GLOBAL_TWIN.host_state == ms.STATE_FLOW)
        GLOBAL_TWIN.set_state(ms.STATE_IDLE)
        
        if was_in_flow:
            await self.coord.send_physical(1, meowprotocol.MSG_TYPE_CMD, "IDLE")
            logger.info("[Job] Loader Paused. Clearing conveyor (5s delay)...")
            await asyncio.sleep(5.0)
            await self.coord.send_physical(3, meowprotocol.MSG_TYPE_CMD, "IDLE")
            await self.coord.send_physical(2, meowprotocol.MSG_TYPE_CMD, "IDLE")
        else:
            for pid in [1, 2, 3]:
                await self.coord.send_physical(pid, meowprotocol.MSG_TYPE_CMD, "IDLE")
        
        self.coord._notify("System Secured (IDLE)", type='info')