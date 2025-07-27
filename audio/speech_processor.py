#!/usr/bin/env python3

import asyncio
import time
import traceback
import select
import numpy as np
from typing import Optional
from evdev import ecodes
from audio.vosk_readiness_checker import vosk_readiness


class SpeechProcessor:
    """
    Handles all speech capture and processing operations.
    
    Manages both VAD-based capture and push-to-talk modes with proper
    transcription coordination and manual stop handling.
    """
    
    def __init__(self, audio_manager, transcriber, keyboard_device=None):
        self.audio_manager = audio_manager
        self.transcriber = transcriber
        self.keyboard_device = keyboard_device
        
    async def _check_manual_vad_stop(self):
        """Check for manual VAD stop via keyboard"""
        if not self.keyboard_device or not ecodes: 
            return False
        try:
            if select.select([self.keyboard_device.fd], [], [], 0)[0]:
                for event in self.keyboard_device.read():
                    if event.type == ecodes.EV_KEY and event.code == ecodes.KEY_LEFTMETA and event.value == 1:
                        print("[VAD] Manual stop via keyboard.")
                        return True
        except BlockingIOError: 
            pass
        return False

    async def capture_speech_with_unified_vad(self, display_manager, is_follow_up=False) -> str | None:
        """Unified VAD function for speech capture"""
        # Check VOSK readiness before starting speech capture
        if not vosk_readiness.is_speech_enabled():
            print("[WARNING] VOSK server not ready - speech capture disabled")
            await display_manager.update_display("error", mood="confused", text="Speech Recognition Unavailable")
            return None
            
        print(f"[DEBUG VAD {time.time():.3f}] Starting VAD, is_follow_up={is_follow_up}")
        await display_manager.update_display("listening", mood="curious" if not is_follow_up else "attentive")
        print(f"[DEBUG VAD {time.time():.3f}] Display updated, initializing input...")
        await self.audio_manager.initialize_input()
        print(f"[DEBUG VAD {time.time():.3f}] Input initialized, starting listening...")
        audio_stream = await self.audio_manager.start_listening()
        print(f"[DEBUG VAD {time.time():.3f}] Audio stream started: {audio_stream}")
        
        if not audio_stream:
            print("[ERROR] Failed to start audio stream for VAD.")
            return None

        # Load VAD settings
        try:
            from audio.vad_settings import load_vad_settings
            vad_config = load_vad_settings()
            print(f"[VAD] Using calibrated settings: threshold={vad_config['energy_threshold']:.6f}")
        except Exception as e:
            print(f"[VAD] Error loading calibrated settings, using defaults: {e}")
            from communication.client_config import VAD_SETTINGS
            vad_config = VAD_SETTINGS

        # Extract parameters
        energy_threshold = vad_config['energy_threshold']
        continued_threshold = vad_config.get('continued_threshold', energy_threshold * 0.6)
        silence_duration = vad_config.get('silence_duration', 3.0)
        min_speech_duration = vad_config.get('min_speech_duration', 0.4)
        speech_buffer_time = vad_config.get('speech_buffer_time', 1.0)
        max_recording_time = vad_config.get('max_recording_time', 45.0)
        frame_history_length = 20

        # Timeout settings based on context
        initial_timeout = 4.0 if is_follow_up else 8.0

        print(f"[VAD] Starting {'follow-up' if is_follow_up else 'initial'} listening")

        # Initialize state variables
        self.transcriber.reset()
        overall_start_time = time.monotonic()
        speech_start_time = 0
        voice_started = False
        silence_frames_count = 0
        
        
        # Calculate frame timing
        frames_per_second = self.audio_manager.sample_rate / self.audio_manager.frame_length
        silence_frames_needed = int(silence_duration * frames_per_second)
        frame_history = []
        
        try:
            while True:
                current_time = time.monotonic()
                
                # Check for manual stop via keyboard
                if await self._check_manual_vad_stop():
                    if voice_started and (current_time - speech_start_time) > min_speech_duration:
                        await asyncio.sleep(speech_buffer_time)
                    else:
                        self.transcriber.reset()
                    break

                # Timeout checks
                if not voice_started and (current_time - overall_start_time > initial_timeout):
                    print(f"[VAD] Initial timeout ({initial_timeout:.1f}s). No voice detected.")
                    return None
                    
                if voice_started and (current_time - speech_start_time > max_recording_time):
                    print(f"[VAD] Max recording time ({max_recording_time:.1f}s) reached.")
                    break

                # Read audio frame
                pcm_bytes = self.audio_manager.read_audio_frame()
                if not pcm_bytes:
                    await asyncio.sleep(0.005)
                    continue

                # Validate frame size
                expected_frame_size = self.audio_manager.frame_length * 2
                if len(pcm_bytes) != expected_frame_size:
                    continue

                # Calculate energy
                frame_data_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
                frame_data_float32 = frame_data_int16.astype(np.float32) / 32768.0
                current_energy = np.sqrt(np.mean(frame_data_float32**2)) if len(frame_data_float32) > 0 else 0.0
                
                # Maintain frame history for smoothing
                frame_history.append(current_energy)
                if len(frame_history) > frame_history_length:
                    frame_history.pop(0)
                avg_energy = sum(frame_history) / len(frame_history) if frame_history else 0.0

                # Process with transcriber
                try:
                    is_final_vosk, confidence_score, partial_text_vosk = self.transcriber.process_frame(pcm_bytes)
                    
                    # Apply confidence filtering
                    if partial_text_vosk and len(partial_text_vosk.strip()) > 0:
                        if confidence_score is None or confidence_score > 0.3 or len(partial_text_vosk.split()) >= 2:
                            current_partial = partial_text_vosk.strip()
                        else:
                            current_partial = None
                    else:
                        current_partial = None
                        
                except Exception as vosk_error:
                    print(f"[VAD] Vosk processing error: {vosk_error}")
                    is_final_vosk = False
                    current_partial = None

                # VAD State Machine
                if not voice_started:
                    if avg_energy > energy_threshold:
                        voice_started = True
                        speech_start_time = current_time
                        silence_frames_count = 0
                        print(f"[VAD] Voice started. Energy: {avg_energy:.6f} > {energy_threshold:.6f}")
                else:
                    # Voice has started - check for continuation
                    if avg_energy > continued_threshold:
                        silence_frames_count = 0
                    else:
                        silence_frames_count += 1

                    speech_duration = current_time - speech_start_time
                    
                    # End conditions
                    if silence_frames_count >= silence_frames_needed and speech_duration >= min_speech_duration:
                        print(f"[VAD] End of speech by silence. Duration: {speech_duration:.2f}s")
                        await asyncio.sleep(speech_buffer_time)
                        break
                        
                    if is_final_vosk and speech_duration >= min_speech_duration:
                        print(f"[VAD] End of speech by Vosk final. Duration: {speech_duration:.2f}s")
                        break

                # Display partial results
                if current_partial:
                    if not hasattr(self, "last_partial_print_time") or (current_time - getattr(self, "last_partial_print_time", 0) > 0.5):
                        print(f"[VAD] Partial: {current_partial}")
                        self.last_partial_print_time = current_time

            # Get final transcript
            final_transcript = self.transcriber.get_final_text()
            print(f"[VAD] Raw final transcript: '{final_transcript}'")

            if final_transcript:
                final_transcript = final_transcript.strip()
                
                # Apply filtering logic
                if not final_transcript:
                    print("[VAD] Transcript empty after stripping.")
                    return None

                # Background noise filter - reject if transcript is just "the" (common noise artifact)
                if final_transcript.lower().strip() == "the":
                    print(f"[VAD] Rejecting background noise artifact: '{final_transcript}'")
                    return None

                num_words = len(final_transcript.split())
                min_chars_single = 2
                min_words_overall = 1
                min_transcript_length = 2

                # Validation checks
                if num_words == 0 or len(final_transcript) < min_transcript_length:
                    print(f"[VAD] Rejecting (too short: {len(final_transcript)} chars): '{final_transcript}'")
                    return None
                    
                if num_words < min_words_overall:
                    print(f"[VAD] Rejecting (too few words: {num_words}): '{final_transcript}'")
                    return None
                    
                if num_words == 1 and len(final_transcript) < min_chars_single:
                    print(f"[VAD] Rejecting (single short word): '{final_transcript}'")
                    return None

                print(f"[VAD] Accepted final transcript: '{final_transcript}'")
                return final_transcript

            print("[VAD] No final transcript obtained.")
            return None

        except Exception as e:
            print(f"[ERROR] Error during VAD/transcription: {e}")
            traceback.print_exc()
            return None
            
        finally:
            await self.audio_manager.stop_listening()
            if hasattr(self, "last_partial_print_time"):
                del self.last_partial_print_time

    async def capture_speech_push_to_talk(self, display_manager) -> str | None:
        """Push-to-talk mode: 1 minute capture with no VAD timeouts"""
        # Check VOSK readiness before starting speech capture
        if not vosk_readiness.is_speech_enabled():
            print("[WARNING] VOSK server not ready - push-to-talk disabled")
            await display_manager.update_display("error", mood="confused", text="Speech Recognition Unavailable")
            return None
            
        print(f"[PUSH-TO-TALK] Starting extended capture mode (60s max)")
        await display_manager.update_display("listening", mood="attentive")
        await self.audio_manager.initialize_input()
        audio_stream = await self.audio_manager.start_listening()
        
        if not audio_stream:
            print("[ERROR] Failed to start audio stream for push-to-talk.")
            return None

        # Initialize transcriber
        self.transcriber.reset()
        start_time = time.monotonic()
        max_recording_time = 60.0  # 1 minute max
        
        try:
            while True:
                current_time = time.monotonic()
                
                # Check for manual stop via keyboard (press again to stop)
                if await self._check_manual_vad_stop():
                    print("[PUSH-TO-TALK] Manual stop via keyboard.")
                    break
                
                # Max time check
                if current_time - start_time > max_recording_time:
                    print(f"[PUSH-TO-TALK] Max recording time ({max_recording_time}s) reached.")
                    break
                
                # Read and process audio frame
                pcm_bytes = self.audio_manager.read_audio_frame()
                if not pcm_bytes:
                    await asyncio.sleep(0.005)
                    continue
                
                # Process with transcriber
                try:
                    is_final_vosk, confidence_score, partial_text_vosk = self.transcriber.process_frame(pcm_bytes)
                    
                    # Show partial results
                    if partial_text_vosk and len(partial_text_vosk.strip()) > 0:
                        if not hasattr(self, "last_partial_print_time") or (current_time - getattr(self, "last_partial_print_time", 0) > 0.5):
                            print(f"[PUSH-TO-TALK] Partial: {partial_text_vosk}")
                            self.last_partial_print_time = current_time
                            
                except Exception as vosk_error:
                    print(f"[PUSH-TO-TALK] Vosk processing error: {vosk_error}")
            
            # Get final transcript
            final_transcript = self.transcriber.get_final_text()
            print(f"[PUSH-TO-TALK] Final transcript: '{final_transcript}'")
            
            if final_transcript:
                final_transcript = final_transcript.strip()
                
                # Background noise filter - reject if transcript is just "the" (common noise artifact)
                if final_transcript.lower().strip() == "the":
                    print(f"[PUSH-TO-TALK] Rejecting background noise artifact: '{final_transcript}'")
                    return None
                
                if final_transcript:
                    return final_transcript
                    
            return None
            
        except Exception as e:
            print(f"[ERROR] Error during push-to-talk capture: {e}")
            traceback.print_exc()
            return None
            
        finally:
            await self.audio_manager.stop_listening()
            if hasattr(self, "last_partial_print_time"):
                del self.last_partial_print_time