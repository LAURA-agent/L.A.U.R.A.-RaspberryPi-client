#!/usr/bin/env python3

import asyncio
import time
import random
import select
from datetime import datetime
from pathlib import Path
from typing import Optional
from evdev import InputDevice, list_devices, ecodes
from colorama import Fore


class InputManager:
    """
    Manages all input detection including keyboard and wake word monitoring.
    
    Handles wake event detection, keyboard monitoring, and coordination
    between different input sources.
    """
    
    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.keyboard_device = None
        self.last_interaction = datetime.now()
        self.last_interaction_check = datetime.now()
        
        # Key state tracking for modifier detection
        self.keys_pressed = set()
        
        # Wake word detection attributes
        self.wake_detector = None
        self.wake_model_names = None
        self.wake_pa = None
        self.wake_stream = None
        self.wake_last_break = None
        
    def find_pi_keyboard(self):
        """Find the Pi 500 keyboard device with proper priority and logging"""
        if not InputDevice: 
            print(f"{Fore.YELLOW}[WARN] evdev not available, keyboard detection disabled{Fore.WHITE}")
            return None
            
        print(f"\n{Fore.CYAN}=== Keyboard Initialization ==={Fore.WHITE}")
        print(f"{Fore.CYAN}Available input devices:{Fore.WHITE}")
        
        keyboard_devices = []
        for path in list_devices():
            try:
                device = InputDevice(path)
                print(f"  - {device.path}: {device.name}")
                
                # Check if we can read from this device
                try:
                    select.select([device.fd], [], [], 0)
                    
                    # Check for Pi 500 keyboard specifically
                    if "Pi 500" in device.name and "Keyboard" in device.name:
                        priority = 0
                        if "event5" in device.path:
                            priority = 100  # Prioritize event5 as it receives KEY_LEFTMETA
                        elif "event10" in device.path:
                            priority = 90   # event10 is secondary
                        elif "Mouse" not in device.name and "Consumer" not in device.name and "System" not in device.name:
                            priority = 50
                            
                        if priority > 0:
                            try:
                                device.grab()
                                device.ungrab()
                                keyboard_devices.append((device, priority))
                                print(f"    {Fore.GREEN}✓ Pi 500 Keyboard found (priority: {priority}){Fore.WHITE}")
                            except Exception as e:
                                print(f"    {Fore.YELLOW}✗ Cannot grab device: {e}{Fore.WHITE}")
                                device.close()
                    else:
                        device.close()
                        
                except Exception as e:
                    print(f"    {Fore.YELLOW}✗ Cannot read device: {e}{Fore.WHITE}")
                    device.close()
                    
            except Exception as e:
                print(f"    {Fore.RED}Error with device {path}: {e}{Fore.WHITE}")

        if keyboard_devices:
            keyboard_devices.sort(key=lambda x: x[1], reverse=True)
            keyboard_device = keyboard_devices[0][0]
            print(f"{Fore.GREEN}✓ Using keyboard device: {keyboard_device.path} ({keyboard_device.name}){Fore.WHITE}")
            print(f"{Fore.GREEN}✓ Using keyboard without exclusive access to allow normal typing{Fore.WHITE}")
            return keyboard_device
        else:
            print(f"{Fore.YELLOW}✗ No valid Pi 500 Keyboard found{Fore.WHITE}")
            return None

    def initialize_keyboard(self):
        """Initialize keyboard input detection"""
        self.keyboard_device = self.find_pi_keyboard()
        return self.keyboard_device is not None

    def _listen_keyboard_sync(self) -> str | None:
        """Synchronous keyboard check for wake event"""
        if not self.keyboard_device or not ecodes:
            return None
            
        try:
            ready, _, _ = select.select([self.keyboard_device.fd], [], [], 0.001)
            if ready:
                for event in self.keyboard_device.read():
                    if event.type == ecodes.EV_KEY:
                        # Track key state changes
                        if event.value == 1:  # Key press
                            self.keys_pressed.add(event.code)
                        elif event.value == 0:  # Key release
                            self.keys_pressed.discard(event.code)
                        
                        # Check for left meta press
                        if (event.code == ecodes.KEY_LEFTMETA and event.value == 1):
                            # Check if shift is currently held
                            if ecodes.KEY_LEFTSHIFT in self.keys_pressed:
                                print("[INFO] SHIFT+Left Meta detected - routing to Claude Code")
                                return "keyboard_code"
                            else:
                                print("[INFO] Left Meta detected - routing to LAURA")
                                return "keyboard_laura"
                                
        except (BlockingIOError, OSError):
            pass
            
        return None

    async def wake_word_detection(self):
        """Wake word detection with notification-aware breaks"""
        import pyaudio
        import snowboydetect
        from communication.client_config import WAKE_WORDS_AND_SENSITIVITIES as WAKE_WORDS, WAKEWORD_RESOURCE_FILE
        
        # One-time initialization
        if not self.wake_detector:
            try:
                print(f"{Fore.YELLOW}Initializing wake word detector...{Fore.WHITE}")

                # Explicitly define resource path
                resource_path = Path(WAKEWORD_RESOURCE_FILE)

                # Set the directory where all wake word models are kept
                wakeword_dir = Path("/home/user/RP500-Client/wakewords")

                # Build model paths from filenames in WAKE_WORDS
                model_paths = [wakeword_dir / name for name in WAKE_WORDS.keys()]

                # Check for missing files
                missing = [str(path.absolute()) for path in [resource_path] + model_paths if not path.exists()]
                if missing:
                    print(f"ERROR: The following required file(s) are missing:\n" + "\n".join(missing))
                    return None

                # Build sensitivities list, ensuring order matches models
                sensitivities = []
                for p in model_paths:
                    sensitivity = WAKE_WORDS.get(p.name)
                    if sensitivity is None:
                        print(f"WARNING: No sensitivity found for {p.name}. Defaulting to 0.5.")
                        sensitivity = 0.5
                    sensitivities.append(str(sensitivity))
                if len(sensitivities) != len(model_paths):
                    print("ERROR: Sensitivities count does not match model paths count!")
                    return None

                # Initialize the detector
                self.wake_detector = snowboydetect.SnowboyDetect(
                    resource_filename=str(resource_path.absolute()).encode(),
                    model_str=",".join(str(p.absolute()) for p in model_paths).encode()
                )
                sensitivity_bytes = ",".join(sensitivities).encode()
                self.wake_detector.SetSensitivity(sensitivity_bytes)
                self.wake_model_names = [p.name for p in model_paths]
                self.wake_pa = pyaudio.PyAudio()
                self.wake_stream = None
                self.wake_last_break = time.time()
                print(f"{Fore.GREEN}Wake word detector initialized with models: {self.wake_model_names}{Fore.WHITE}")
            except Exception as e:
                print(f"Error initializing wake word detection: {e}")
                return None

        try:
            # Create/restart stream if needed
            if not self.wake_stream or not self.wake_stream.is_active():
                self.wake_stream = self.wake_pa.open(
                    rate=16000,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=1024
                )
                self.wake_stream.start_stream()

            # Periodic breaks for notifications (every 20 seconds)
            current_time = time.time()
            if (current_time - self.wake_last_break) >= 20:
                self.wake_last_break = current_time
                if self.wake_stream:
                    self.wake_stream.stop_stream()
                    await asyncio.sleep(1)  # 1-second break
                    self.wake_stream.start_stream()
                return None

            # Read audio with error handling
            try:
                data = self.wake_stream.read(1024, exception_on_overflow=False)
                if len(data) == 0:
                    print("Warning: Empty audio frame received")
                    return None
            except (IOError, OSError) as e:
                print(f"Stream read error: {e}")
                if self.wake_stream:
                    self.wake_stream.stop_stream()
                    self.wake_stream.close()
                    self.wake_stream = None
                return None

            result = self.wake_detector.RunDetection(data)
            if result > 0:
                print(f"{Fore.GREEN}Wake word detected! (Model {result}){Fore.WHITE}")
                self.last_interaction = datetime.now()
                self.last_interaction_check = datetime.now()
                return self.wake_model_names[result-1] if result <= len(self.wake_model_names) else None

            # Occasionally yield to event loop (much less frequently)
            if random.random() < 0.01:
                await asyncio.sleep(0)

            return None

        except Exception as e:
            print(f"Error in wake word detection: {e}")
            if self.wake_stream:
                self.wake_stream.stop_stream()
                self.wake_stream.close()
                self.wake_stream = None
            return None

    async def check_for_wake_events(self):
        """Check for wake events from keyboard or wake word"""
        wake_event_source = None
        
        # Check keyboard first
        keyboard_event = self._listen_keyboard_sync()
        if keyboard_event:
            wake_event_source = keyboard_event  # Can be "keyboard_laura" or "keyboard_code"
            print(f"[INFO] Wake event from keyboard: {keyboard_event}")
        else:
            # Check wake word
            wakeword_model = await self.wake_word_detection()
            if wakeword_model:
                wake_event_source = f"wakeword ({wakeword_model})"
                print(f"[INFO] Wake event from: {wake_event_source}")
        
        return wake_event_source

    def cleanup(self):
        """Clean up keyboard resources"""
        if self.keyboard_device:
            self.keyboard_device.close()
            self.keyboard_device = None