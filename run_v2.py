#!/usr/bin/env python3

import asyncio
import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style, init

# MCP Imports
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# Local Component Imports
from audio.audio_manager import AudioManager
from communication.client_tts_handler import TTSHandler
from audio.vosk_websocket_adapter import VoskTranscriber
from ui.display_manager import DisplayManager

# New Modular Components
from audio.speech_processor import SpeechProcessor
from system.conversation_manager import ConversationManager
from system.input_manager import InputManager
from system.notification_manager import NotificationManager
from system.system_command_manager import SystemCommandManager
from audio.audio_coordinator import AudioCoordinator

# Configuration and Utilities
from communication.client_config import (
    SERVER_URL, DEVICE_ID, VOSK_MODEL_PATH, AUDIO_SAMPLE_RATE,
    client_settings, save_client_settings, get_active_tts_provider, set_active_tts_provider
)
from audio.vosk_readiness_checker import vosk_readiness, ensure_vosk_ready

# Initialize colorama
init()


def get_random_audio(category: str, subtype: str = None):
    """Get random audio file for given category"""
    import random
    try:
        base_sound_dir = "/home/user/RP500-Client/sounds/laura"
        
        if category == "wake" and subtype in ["Laura.pmdl", "Wake_up_Laura.pmdl", "GD_Laura.pmdl"]:
            context_map = {
                "Laura.pmdl": "standard",
                "Wake_up_Laura.pmdl": "sleepy", 
                "GD_Laura.pmdl": "frustrated"
            }
            folder = context_map.get(subtype, "standard")
            audio_path = Path(f"{base_sound_dir}/wake_sentences/{folder}")
        else:
            audio_path = Path(f"{base_sound_dir}/{category}_sentences")
            if subtype and (Path(f"{audio_path}/{subtype}")).exists():
                audio_path = Path(f"{audio_path}/{subtype}")
        
        audio_files = []
        if audio_path.exists():
            audio_files = list(audio_path.glob('*.mp3')) + list(audio_path.glob('*.wav'))
        
        if audio_files:
            return str(random.choice(audio_files))
        return None
    except Exception as e:
        print(f"Error in get_random_audio: {str(e)}")
        return None


class PiMCPClient:
    """
    Modular MCP Client for Pi 500 with clean separation of concerns.
    
    This orchestrator coordinates between all the specialized managers
    while maintaining a minimal footprint for the main client logic.
    """
    
    def __init__(self, server_url: str, device_id: str):
        self.server_url = server_url
        self.device_id = device_id
        self.session_id: str | None = None
        self.mcp_session: ClientSession | None = None
        
        # Initialize core components
        self.audio_manager = AudioManager(sample_rate=AUDIO_SAMPLE_RATE)
        self.tts_handler = TTSHandler()
        self.display_manager = DisplayManager(
            svg_path=client_settings.get("DISPLAY_SVG_PATH"),
            boot_img_path=client_settings.get("DISPLAY_BOOT_IMG_PATH"),
            window_size=client_settings.get("DISPLAY_WINDOW_SIZE")
        )
        self.transcriber = VoskTranscriber(sample_rate=AUDIO_SAMPLE_RATE)
        
        # Initialize specialized managers
        self.input_manager = InputManager(self.audio_manager)
        self.audio_coordinator = AudioCoordinator(self.audio_manager)
        self.speech_processor = SpeechProcessor(
            self.audio_manager, 
            self.transcriber, 
            None  # Will be set after keyboard initialization
        )
        self.conversation_manager = ConversationManager(
            self.speech_processor,
            self.audio_coordinator,
            self.tts_handler,
            client_settings
        )
        self.notification_manager = NotificationManager(
            self.audio_coordinator,
            self.tts_handler
        )
        self.system_command_manager = SystemCommandManager(
            client_settings,
            save_client_settings,
            get_active_tts_provider,
            set_active_tts_provider
        )
        
        # Initialize keyboard
        self.input_manager.initialize_keyboard()
        self.speech_processor.keyboard_device = self.input_manager.keyboard_device

    async def initialize_session(self):
        """Initialize the client session with the MCP server"""
        try:
            if not self.mcp_session:
                print("[ERROR] MCP session object not available for registration.")
                return False
                
            print("[INFO] Performing MCP handshake with server...")
            await self.mcp_session.initialize()
            print("[INFO] MCP handshake completed successfully.")
            
            await asyncio.sleep(2.0)  # Give server time to be ready

            registration_payload = {
                "device_id": self.device_id,
                "capabilities": {
                    "input": ["text", "audio"],
                    "output": ["text", "audio"],
                    "tts_mode": client_settings.get("tts_mode", "api"),
                    "api_tts_provider": get_active_tts_provider(),
                    "supports_caching": True
                }
            }
            
            print(f"[INFO] Calling 'register_device' tool with payload: {registration_payload}")
            response_obj = await self.mcp_session.call_tool("register_device", arguments=registration_payload)

            if hasattr(response_obj, 'content') and response_obj.content:
                text_content = response_obj.content[0].text
                response_data = json.loads(text_content)
            else:
                response_data = response_obj

            if isinstance(response_data, dict) and response_data.get("session_id"):
                self.session_id = response_data["session_id"]
                print(f"[INFO] Device registration successful. Session ID: {self.session_id}")
                return True
            else:
                print(f"[ERROR] Device registration failed. Response: {response_data}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error during session initialization: {e}")
            traceback.print_exc()
            return False

    async def send_to_server(self, transcript: str) -> dict | None:
        """Send text to MCP server and get response"""
        if not self.session_id or not self.mcp_session:
            print("[ERROR] Session not initialized. Cannot send message.")
            return {"text": "Error: Client session not ready.", "mood": "error"}
            
        try:
            tool_call_args = {
                "session_id": self.session_id,
                "input_type": "text",
                "payload": {"text": transcript},
                "output_mode": ["text", "audio"],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            print(f"[INFO] Calling 'run_LAURA' tool...")
            response_payload = await self.mcp_session.call_tool("run_LAURA", arguments=tool_call_args)
            
            # Parse response properly
            parsed_response = None
            if hasattr(response_payload, 'content') and response_payload.content:
                json_str = response_payload.content[0].text
                parsed_response = json.loads(json_str)
            elif isinstance(response_payload, dict):
                parsed_response = response_payload
            else:
                print(f"[ERROR] Unexpected response format: {type(response_payload)}")
                return {"text": "Sorry, I received an unexpected response format.", "mood": "confused"}

            if isinstance(parsed_response, dict) and "text" in parsed_response:
                return parsed_response
            else:
                print(f"[ERROR] Invalid response: {parsed_response}")
                return {"text": "Sorry, I received an unexpected response.", "mood": "confused"}
                
        except (ConnectionError, ConnectionRefusedError, OSError) as e:
            print(f"[ERROR] Connection lost during server call: {e}")
            # Clear session to trigger reconnection
            self.mcp_session = None
            self.session_id = None
            return {"text": "Connection lost. Reconnecting...", "mood": "error"}
        except Exception as e:
            print(f"[ERROR] Failed to call server: {e}")
            traceback.print_exc()
            return {"text": "Sorry, a communication problem occurred.", "mood": "error"}

    async def run_main_loop(self):
        """Main interaction loop with natural conversation flow"""
        print("[INFO] Main interaction loop started.")
        
        while True:
            try:
                current_state = self.display_manager.current_state
                
                # Only check for wake events during sleep/idle/code
                if current_state in ['sleep', 'idle', 'code']:
                    # Check for wake events
                    wake_event_source = await self.input_manager.check_for_wake_events()
                    
                    # If no wake event, continue monitoring
                    if not wake_event_source:
                        await asyncio.sleep(0.05)  # Optimized for faster wake word detection
                        continue
                    
                    # Handle wake event - play contextual audio efficiently
                    if 'wakeword' in wake_event_source:
                        model_name = wake_event_source.split('(')[1].rstrip(')')
                        print(f"[DEBUG] Extracted model_name: '{model_name}'")
                        
                        # Check if this is a medicine acknowledgment wake word
                        if model_name == "tookmycrazypills.pmdl":
                            print("[INFO] Medicine taken acknowledgment via wake word")
                            # Clear the medicine reminder
                            await self.system_command_manager.system_manager.clear_reminder("medicine", self.mcp_session, self.session_id)
                            # Play success sound (same as startup)
                            success_sound = "/home/user/RP500-Client/sounds/sound_effects/successfulloadup.mp3"
                            if os.path.exists(success_sound):
                                await self.audio_coordinator.play_audio_file(success_sound)
                            await self.display_manager.update_display("idle")
                            continue  # Skip everything else
                        
                        # Normal wake word handling
                        wake_audio = get_random_audio('wake', model_name)
                        print(f"[DEBUG] get_random_audio returned: {wake_audio}")
                        if wake_audio:
                            print(f"[DEBUG] About to play wake audio: {wake_audio}")
                            await self.audio_coordinator.play_audio_file(wake_audio)
                        else:
                            print(f"[DEBUG] No wake audio returned for model: {model_name}")

                    # Go directly to listening
                    await self.display_manager.update_display('listening')

                    # Capture speech - use push-to-talk mode for keyboard, VAD for wakeword
                    if wake_event_source in ["keyboard_laura", "keyboard_code"]:
                        print("[INFO] Using push-to-talk mode (no VAD timeouts)")
                        transcript = await self.speech_processor.capture_speech_push_to_talk(self.display_manager)
                    else:
                        print("[INFO] Using VAD mode with timeouts")
                        transcript = await self.speech_processor.capture_speech_with_unified_vad(self.display_manager, is_follow_up=False)
                    
                    if not transcript:
                        print("[INFO] No speech detected, returning to previous state")
                        await self.display_manager.update_display("code" if current_state == "code" else "idle")
                        continue
                    
                    # In code mode, route everything to Claude Code (except system commands)
                    if current_state == "code":
                        print(f"[INFO] Code mode active - routing to Claude Code: '{transcript}'")
                        await self.display_manager.update_display('thinking')
                        await self.route_to_claude_code(transcript)
                        await self.display_manager.update_display('code')
                        continue
                    
                    # Route to Claude Code if SHIFT+Left Meta was used OR specific wake word
                    if wake_event_source == "keyboard_code" or self._should_route_to_claude_code(wake_event_source):
                        print(f"[INFO] Routing to Claude Code: '{transcript}'")
                        await self.display_manager.update_display('thinking')
                        await self.route_to_claude_code(transcript)
                        await self.display_manager.update_display('idle')
                        continue
                    
                    # Check for note transfer wake word
                    if self._should_send_note_to_mac(wake_event_source):
                        print(f"[INFO] Note transfer wake word detected - sending pi500_note.txt to Mac")
                        await self.display_manager.update_display('thinking')
                        await self.send_note_to_mac()
                        await self.display_manager.update_display('idle')
                        continue
                    
                    # Check for system commands
                    is_cmd, cmd_type, cmd_arg = self.system_command_manager.detect_system_command(transcript)
                    if is_cmd:
                        await self.system_command_manager.handle_system_command(
                            cmd_type, cmd_arg, self.mcp_session, self.session_id, 
                            self.tts_handler, self.audio_coordinator
                        )
                        await self.display_manager.update_display('idle')
                        continue
                    
                    # Check for document uploads
                    await self.system_command_manager.check_and_upload_documents(self.mcp_session, self.session_id)
                    
                    # Process normal conversation
                    await self.display_manager.update_display('thinking')
                    response = await self.send_to_server(transcript)
                    
                    # Handle response through conversation manager
                    await self.conversation_manager.process_initial_response(
                        response, self.display_manager, self, self.system_command_manager
                    )
                        
                else:
                    # In other states, brief sleep
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"[ERROR] Error in main loop: {e}")
                traceback.print_exc()
                await self.display_manager.update_display("error", text="System Error")
                await asyncio.sleep(2)
                # Return to appropriate state based on current mode
                return_state = "code" if self.display_manager.current_state == "code" else "idle"
                await self.display_manager.update_display(return_state)

    async def run(self):
        """Main client run loop with multi-task architecture"""
        print(f"{Fore.CYAN}PiMCPClient v2 run loop started.{Fore.WHITE}")
        await self.display_manager.update_display("boot")

        # Start background tasks
        background_tasks = [
            asyncio.create_task(self.display_manager.rotate_background()),
            asyncio.create_task(self.notification_manager.check_for_notifications_loop(
                self.mcp_session, self.session_id, self.display_manager
            )),
        ]

        connection_attempts = 0
        handshake_failures = 0
        connection_failures = 0  # Track connection failures separately
        code_mode_active = False
        
        while True:
            try:
                # If in code mode, handle it differently
                if code_mode_active:
                    # Run main loop without server connection
                    print("[INFO] Running in code mode - server connection bypassed")
                    await self.display_manager.update_display("code")
                    
                    # Add main loop task and run it
                    main_loop_task = asyncio.create_task(self.run_main_loop())
                    all_tasks = background_tasks + [main_loop_task]
                    
                    try:
                        await asyncio.gather(*all_tasks, return_exceptions=True)
                    except Exception as e:
                        print(f"[ERROR] Task execution error in code mode: {e}")
                    finally:
                        # Cancel main loop task
                        main_loop_task.cancel()
                        try:
                            await main_loop_task
                        except asyncio.CancelledError:
                            pass
                    
                    # Check if user wants to try reconnecting (wait a bit)
                    await asyncio.sleep(10)
                    continue
                
                connection_attempts += 1
                if connection_attempts > 1:
                    print(f"[INFO] Reconnection attempt #{connection_attempts - 1}")
                print(f"[INFO] Attempting to connect to MCP server at {self.server_url}...")
                
                async with sse_client(f"{self.server_url}/events/sse", headers={}) as (read, write):
                    print("[INFO] SSE client connected. Creating ClientSession...")
                    connection_attempts = 0  # Reset counter on successful connection
                    
                    async with ClientSession(read, write) as session:
                        self.mcp_session = session
                        print("[INFO] ClientSession active.")

                        if not await self.initialize_session():
                            print("[ERROR] Failed to initialize session. Reconnecting...")
                            handshake_failures += 1
                            raise Exception("Session initialization failed")

                        # Reset failures on successful connection
                        handshake_failures = 0
                        connection_failures = 0
                        code_mode_active = False
                        
                        await self.display_manager.update_display("idle")
                        print(f"{Fore.CYAN}✓ Session initialized successfully{Fore.WHITE}")
                        
                        # Play startup sound and transition to sleep (only on first connection)
                        if connection_attempts == 0:
                            print(f"\n{Fore.CYAN}=== Startup Sequence ==={Fore.WHITE}")
                            startup_sound = "/home/user/RP500-Client/sounds/sound_effects/successfulloadup.mp3"
                            if os.path.exists(startup_sound):
                                try:
                                    print(f"{Fore.CYAN}Playing startup audio...{Fore.WHITE}")
                                    await self.display_manager.update_display('sleep')
                                    await self.audio_coordinator.play_audio_file(startup_sound)
                                    print(f"{Fore.GREEN}✓ Startup audio complete{Fore.WHITE}")
                                except Exception as e:
                                    print(f"{Fore.YELLOW}Warning: Could not play startup sound: {e}{Fore.WHITE}")
                        else:
                            # Reconnection success - brief audio notification
                            print(f"{Fore.GREEN}✓ Reconnected to MCP server{Fore.WHITE}")
                            await self.display_manager.update_display('sleep')
                        
                        print(f"{Fore.MAGENTA}🎧 Listening for wake word or press Raspberry button to begin...{Fore.WHITE}")
                        
                        # Update notification manager with session info
                        background_tasks[1].cancel()
                        background_tasks[1] = asyncio.create_task(
                            self.notification_manager.check_for_notifications_loop(
                                self.mcp_session, self.session_id, self.display_manager
                            )
                        )
                        
                        # Add main loop to tasks and run all concurrently
                        main_loop_task = asyncio.create_task(self.run_main_loop())
                        all_tasks = background_tasks + [main_loop_task]
                        
                        try:
                            await asyncio.gather(*all_tasks, return_exceptions=True)
                        except Exception as e:
                            print(f"[ERROR] Task execution error: {e}")
                        finally:
                            # Cancel main loop task when connection ends
                            main_loop_task.cancel()
                            try:
                                await main_loop_task
                            except asyncio.CancelledError:
                                pass
                                
            except asyncio.CancelledError:
                print("[INFO] Main loop cancelled.")
                break
            except (ConnectionRefusedError, ConnectionError, OSError) as e:
                print(f"[ERROR] Connection failed: {e}. Server may be down.")
                connection_failures += 1
                
                # Check if we should enter code mode after 2 connection failures
                if connection_failures >= 2 and not code_mode_active:
                    print(f"[INFO] {connection_failures} connection failures detected. Entering code mode...")
                    await self.display_manager.update_display("code")
                    print("[INFO] Code mode active - speech will be routed to Claude Code")
                    code_mode_active = True
                else:
                    await self.display_manager.update_display("error", text="Server Offline")
                
                if not code_mode_active:
                    print(f"[INFO] Retrying connection in 30 seconds...")
                    await asyncio.sleep(30)
                else:
                    print("[INFO] Code mode active - stopping connection attempts. Use voice commands or keyboard.")
                    await asyncio.sleep(5)  # Short sleep before trying again to see if user wants to exit code mode
            except Exception as e:
                print(f"[ERROR] Unhandled connection-level exception: {e}")
                traceback.print_exc()
                connection_failures += 1  # Also count general exceptions as connection failures
                
                # Check if we should enter code mode after 2 connection failures
                if connection_failures >= 2 and not code_mode_active:
                    print(f"[INFO] {connection_failures} connection failures detected. Entering code mode...")
                    await self.display_manager.update_display("code")
                    print("[INFO] Code mode active - speech will be routed to Claude Code")
                    code_mode_active = True
                else:
                    await self.display_manager.update_display("error", text="Connection Error")
                
                if not code_mode_active:
                    print(f"[INFO] Retrying connection in 30 seconds...")
                    await asyncio.sleep(30)
                else:
                    print("[INFO] Code mode active - stopping connection attempts. Use voice commands or keyboard.")
                    await asyncio.sleep(5)  # Short sleep before trying again to see if user wants to exit code mode
            finally:
                self.mcp_session = None
                if connection_attempts == 0:  # Only show disconnected state if we were previously connected
                    await self.display_manager.update_display("disconnected")
        
        # Cancel background tasks
        for task in background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
    async def cleanup(self):
        """Clean up resources"""
        print("[INFO] Starting client cleanup...")
        if self.audio_coordinator: 
            await self.audio_coordinator.cleanup()
        if self.audio_manager: 
            await self.audio_manager.cleanup()
        if self.display_manager: 
            self.display_manager.cleanup()
        if self.input_manager: 
            self.input_manager.cleanup()
        print("[INFO] Client cleanup finished.")
    
    async def route_to_claude_code(self, transcript: str):
        """Route speech transcript to Claude Code with health check and session management"""
        from claude.claude_code_healthcheck import execute_claude_code_with_health_check
        
        try:
            print(f"[INFO] Routing to Claude Code: '{transcript}'")
            
            # Update display to show processing
            await self.display_manager.update_display("thinking", mood="focused")
            
            # Process with Claude Code using health check and session management
            result = await execute_claude_code_with_health_check(transcript)
            
            if result["success"]:
                response = result.get("response", "")
                execution_time = result.get("execution_time", 0)
                session_info = result.get("session_info", "Unknown session")
                
                print(f"[INFO] Claude Code completed in {execution_time:.1f}s via {session_info}")
                print(f"[INFO] Response: {response[:100]}{'...' if len(response) > 100 else ''}")
                
                # Determine if we should speak the response
                should_speak = self._should_speak_claude_response(response, transcript)
                
                if should_speak and response:
                    # Speak the response via TTS
                    await self.display_manager.update_display("speaking", mood="helpful")
                    
                    # Use a shorter summary for very long responses
                    if len(response) > 300:
                        speech_text = "Task completed successfully. Check the output for details."
                    else:
                        speech_text = response
                        
                    try:
                        # Use the existing TTS system
                        audio_file = await self.tts_handler.synthesize_speech(
                            speech_text,
                            voice_id="default"
                        )
                        
                        if audio_file:
                            await self.audio_manager.play_audio(audio_file)
                    except Exception as tts_error:
                        print(f"[ERROR] TTS failed: {tts_error}")
                        # Fall back to success sound
                        await self.audio_manager.play_audio(
                            "/home/user/RP500-Client/sounds/sound_effects/successfulloadup.mp3"
                        )
                else:
                    # Just confirm completion without speaking the full response
                    await self.audio_manager.play_audio(
                        "/home/user/RP500-Client/sounds/sound_effects/successfulloadup.mp3"
                    )
                    
            else:
                # Handle error
                error = result.get("error", "Unknown error")
                print(f"[ERROR] Claude Code failed: {error}")
                
                # Speak error notification
                await self.display_manager.update_display("speaking", mood="confused")
                try:
                    error_text = f"Claude Code error: {error}"
                    audio_file = await self.tts_handler.synthesize_speech(
                        error_text[:200],  # Limit error message length
                        voice_id="default"
                    )
                    if audio_file:
                        await self.audio_manager.play_audio(audio_file)
                except:
                    # Fall back to error sound if TTS fails
                    pass
                    
        except Exception as e:
            print(f"[ERROR] Failed to route to Claude Code: {e}")
            # Handle error gracefully
            
        finally:
            # Return to idle state
            await self.display_manager.update_display("idle", mood="casual")
    
    def _should_speak_claude_response(self, response: str, original_command: str) -> bool:
        """Determine if Claude Code response should be spoken"""
        if not response:
            return False
            
        # Don't speak very long responses
        if len(response) > 500:
            return False
            
        # Don't speak responses that look like code
        code_indicators = ['```', 'def ', 'class ', 'import ', 'function', '{', '}', 'const ', 'let ', 'var ']
        if any(indicator in response for indicator in code_indicators):
            return False
            
        # Don't speak file paths or technical output
        if response.startswith('/') or 'http://' in response or 'https://' in response:
            return False
            
        # Check for coding-related commands
        coding_keywords = ['create', 'write', 'implement', 'code', 'function', 'debug', 'fix', 'refactor']
        is_coding_command = any(keyword in original_command.lower() for keyword in coding_keywords)
        
        # For coding commands, be more conservative about speaking
        if is_coding_command and len(response) > 200:
            return False
            
        # Speak conversational responses
        return True
    
    def _should_route_to_claude_code(self, wake_event_source: str) -> bool:
        """
        Determine if wake event should route to Claude Code CLI
        
        Args:
            wake_event_source: The wake event source (e.g., "wakeword (YourNewModel.pmdl)")
            
        Returns:
            bool: True if should route to Claude Code, False for regular chat
        """
        if not wake_event_source or 'wakeword' not in wake_event_source:
            return False
            
        # Extract model name from wake event source
        if '(' in wake_event_source and ')' in wake_event_source:
            model_name = wake_event_source.split('(')[1].rstrip(')')
            
            # Define wake words that should route to Claude Code
            claude_code_wake_words = [
                "claudecode.pmdl",
            ]
            
            return model_name in claude_code_wake_words
            
        return False
    
    def _should_send_note_to_mac(self, wake_event_source: str) -> bool:
        """
        Determine if wake event should trigger note transfer to Mac
        
        Args:
            wake_event_source: The wake event source (e.g., "wakeword (sendnote.pmdl)")
            
        Returns:
            bool: True if should send note to Mac, False otherwise
        """
        if not wake_event_source or 'wakeword' not in wake_event_source:
            return False
            
        # Extract model name from wake event source
        if '(' in wake_event_source and ')' in wake_event_source:
            model_name = wake_event_source.split('(')[1].rstrip(')')
            
            # Define wake words that should trigger note transfer
            note_transfer_wake_words = [
                "sendnote.pmdl",
            ]
            
            return model_name in note_transfer_wake_words
            
        return False
    
    async def send_note_to_mac(self):
        """Send pi500_note.txt to Mac server via MCP endpoint"""
        try:
            from send_note_to_mac import Pi500NoteSender
            
            sender = Pi500NoteSender()
            result = sender.send_note()
            
            if result["success"]:
                # Success - play confirmation sound and speak result
                success_sound = "/home/user/RP500-Client/sounds/sound_effects/successfulloadup.mp3"
                if os.path.exists(success_sound):
                    await self.audio_coordinator.play_audio_file(success_sound)
                
                message = "Note successfully sent to Mac server!"
                print(f"[INFO] {message}")
                
                # Speak confirmation
                await self.tts_handler.speak_text(
                    message,
                    voice_params={"persona": "laura"},
                    coordinator=self.audio_coordinator
                )
                
            else:
                # Error - play error sound and speak error
                error_sound = "/home/user/RP500-Client/sounds/sound_effects/error.mp3"
                if os.path.exists(error_sound):
                    await self.audio_coordinator.play_audio_file(error_sound)
                
                message = f"Failed to send note: {result.get('error', 'Unknown error')}"
                print(f"[ERROR] {message}")
                
                # Speak error
                await self.tts_handler.speak_text(
                    "Sorry, I couldn't send the note to Mac. Check the connection.",
                    voice_params={"persona": "laura"},
                    coordinator=self.audio_coordinator
                )
                
        except Exception as e:
            print(f"[ERROR] Exception in send_note_to_mac: {e}")
            
            # Play error sound
            error_sound = "/home/user/RP500-Client/sounds/sound_effects/error.mp3"
            if os.path.exists(error_sound):
                await self.audio_coordinator.play_audio_file(error_sound)
            
            # Speak error
            await self.tts_handler.speak_text(
                "Sorry, there was an error sending the note.",
                voice_params={"persona": "laura"},
                coordinator=self.audio_coordinator
            )


async def main():
    """Main entry point with multi-task architecture"""
    from communication.client_config import load_client_settings
    load_client_settings()
    
    # Check VOSK server readiness before starting client
    print("[INFO] Checking VOSK server readiness...")
    if not await ensure_vosk_ready(timeout=30):
        print("[ERROR] VOSK server not ready - cannot start speech features")
        print("[ERROR] Please ensure VOSK server is running: ./start_vosk_server.sh")
        return
    
    print("[INFO] VOSK server ready - speech features enabled")
    
    client = PiMCPClient(server_url=SERVER_URL, device_id=DEVICE_ID)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received.")
    finally:
        print("[INFO] Main function finished. Performing final cleanup...")
        await client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Application terminated by user.")
    finally:
        print("[INFO] Application shutdown complete.")