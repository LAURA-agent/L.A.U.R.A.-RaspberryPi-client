#!/usr/bin/env python3
"""
VOSK WebSocket Client
Replacement for direct VoskTranscriber that connects to shared VOSK server
"""

import asyncio
import websockets
import json
import logging
import time
import threading
import queue
from typing import Optional, Tuple

logger = logging.getLogger('vosk_client')


class VoskWebSocketClient:
    """
    Drop-in replacement for VoskTranscriber that uses WebSocket server
    Maintains the same interface as the original VoskTranscriber
    """
    
    def __init__(self, server_url: str = "ws://localhost:8765", sample_rate: int = 16000):
        self.server_url = server_url
        self.sample_rate = sample_rate
        self.websocket = None
        self.session_id = None
        self.connected = False
        
        # Response handling
        self.response_queue = queue.Queue()
        self.partial_text = ""
        self.complete_text = ""
        
        # Event loop for async operations
        self.loop = None
        self.loop_thread = None
        self.connect_event = threading.Event()
        
        # Start background event loop
        self._start_background_loop()
        
    def _start_background_loop(self):
        """Start background event loop for WebSocket operations"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
            
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Wait for loop to be ready
        time.sleep(0.1)
        
    async def _connect(self):
        """Connect to VOSK WebSocket server"""
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=10**7,  # 10MB max message size
                ping_interval=20,
                ping_timeout=10
            )
            
            # Wait for connection confirmation
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get('type') == 'connection' and data.get('status') == 'connected':
                self.session_id = data.get('session_id')
                self.connected = True
                logger.info(f"Connected to VOSK server: {self.session_id}")
                
                # Start message handler
                asyncio.create_task(self._message_handler())
                
                return True
            else:
                logger.error(f"Unexpected connection response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to VOSK server: {e}")
            self.connected = False
            return False
            
    async def _message_handler(self):
        """Handle incoming messages from server"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.response_queue.put(data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            self.connected = False
            
    def connect(self) -> bool:
        """Connect to VOSK server (synchronous)"""
        if not self.loop:
            return False
            
        future = asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
        try:
            return future.result(timeout=10.0)
        except Exception as e:
            logger.error(f"Connection timeout: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from server"""
        if self.websocket and self.connected:
            future = asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
            try:
                future.result(timeout=5.0)
            except:
                pass
            self.connected = False
            
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def reset(self):
        """Reset transcriber state for new utterance"""
        self.complete_text = ""
        self.partial_text = ""
        
        if not self.connected:
            if not self.connect():
                raise RuntimeError("Failed to connect to VOSK server")
                
        # Send reset command
        command = {'type': 'reset'}
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(json.dumps(command)), 
            self.loop
        )
        try:
            future.result(timeout=5.0)
        except Exception as e:
            logger.error(f"Reset command failed: {e}")
            
        # Clear response queue
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
                
    def process_frame(self, frame_data_bytes: bytes) -> Tuple[bool, bool, str]:
        """
        Process audio frame and return transcription results
        
        Returns:
            Tuple of (is_final_chunk_result, is_speech_in_frame, current_full_text)
        """
        if not self.connected:
            return False, False, ""
            
        # Send audio data
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(frame_data_bytes), 
            self.loop
        )
        try:
            future.result(timeout=1.0)
        except Exception as e:
            logger.error(f"Failed to send audio frame: {e}")
            return False, False, ""
            
        # Check for immediate responses (non-blocking)
        try:
            response = self.response_queue.get(timeout=0.1)
            return self._process_response(response)
        except queue.Empty:
            return False, False, self._get_current_text()
            
    def _process_response(self, response: dict) -> Tuple[bool, bool, str]:
        """Process a response from the server"""
        response_type = response.get('type')
        
        if response_type == 'final':
            text = response.get('text', '').strip()
            if text:
                if self.complete_text:
                    self.complete_text = f"{self.complete_text} {text}"
                else:
                    self.complete_text = text
                self.partial_text = ""
                return True, True, self.complete_text
            else:
                return True, False, self.complete_text
                
        elif response_type == 'partial':
            self.partial_text = response.get('text', '').strip()
            is_speech = bool(self.partial_text)
            return False, is_speech, self._get_current_text()
            
        elif response_type == 'error':
            logger.error(f"Server error: {response.get('message')}")
            
        return False, False, self._get_current_text()
        
    def _get_current_text(self) -> str:
        """Get current combined text"""
        if self.complete_text and self.partial_text:
            return f"{self.complete_text} {self.partial_text}"
        elif self.complete_text:
            return self.complete_text
        elif self.partial_text:
            return self.partial_text
        else:
            return ""
            
    def get_final_text(self) -> str:
        """Get final transcription result"""
        if not self.connected:
            logger.warning("Not connected, returning current complete_text")
            return self.complete_text.strip()
            
        # Debug logging
        logger.info(f"Getting final text - current state: complete='{self.complete_text}', partial='{self.partial_text}', queue_size={self.response_queue.qsize()}")
        
        # Send final command
        command = {'type': 'final'}
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(json.dumps(command)), 
            self.loop
        )
        try:
            future.result(timeout=5.0)
            logger.info("Final command sent successfully")
        except Exception as e:
            logger.error(f"Final command failed: {e}")
            return self.complete_text.strip()
            
        # Wait for final result - process all queued messages
        start_time = time.time()
        timeout = 2.0
        
        while time.time() - start_time < timeout:
            try:
                response = self.response_queue.get(timeout=0.1)
                if response.get('type') == 'final_result':
                    final_text = response.get('text', '').strip()
                    if final_text:
                        self.complete_text = final_text
                    break
                elif response.get('type') == 'partial':
                    # Update partial text in case it's the latest
                    partial = response.get('text', '').strip()
                    if partial:
                        self.partial_text = partial
                elif response.get('type') == 'final':
                    # Handle final chunks too
                    text = response.get('text', '').strip()
                    if text:
                        if self.complete_text:
                            self.complete_text = f"{self.complete_text} {text}"
                        else:
                            self.complete_text = text
                        self.partial_text = ""
            except queue.Empty:
                continue
                
        # Ensure we have something to return
        if not self.complete_text and self.partial_text:
            # If we only have partial text, use it as the final result
            self.complete_text = self.partial_text
            logger.info(f"Using partial text as final: '{self.partial_text}'")
        
        final_result = self.complete_text.strip()
        logger.info(f"Returning final text: '{final_result}'")
        return final_result
        
    def cleanup(self):
        """Clean up resources"""
        self.disconnect()
        
    def __del__(self):
        """Destructor"""
        try:
            self.cleanup()
        except:
            pass


# Convenience function for drop-in replacement
def VoskTranscriber(model_path: str = None, sample_rate: int = 16000, server_url: str = "ws://localhost:8765"):
    """
    Drop-in replacement for original VoskTranscriber
    Ignores model_path and uses WebSocket server instead
    """
    return VoskWebSocketClient(server_url=server_url, sample_rate=sample_rate)