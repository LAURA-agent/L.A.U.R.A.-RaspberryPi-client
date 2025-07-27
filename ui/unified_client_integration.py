#!/usr/bin/env python3

"""
Integration module for connecting the unified Gradio interface with the main RP500-Client.
Provides seamless communication between the client and the web interface.
"""

import asyncio
import threading
import time
from typing import Optional, Dict, Any
from pathlib import Path

from ui.gradio_display_manager import GradioDisplayManager
from system.conversation_history_reader import ConversationHistoryReader
from ui.simple_unified_interface import SimpleUnifiedInterface


class UnifiedClientBridge:
    """
    Bridge between the main RP500-Client and the unified Gradio interface.
    Provides real-time synchronization of display states and conversation history.
    """
    
    def __init__(self):
        self.gradio_display_manager: Optional[GradioDisplayManager] = None
        self.conversation_reader: Optional[ConversationHistoryReader] = None
        self.interface_manager: Optional[SimpleUnifiedInterface] = None
        self.bridge_active = False
        self.sync_thread = None
        
        print("[UnifiedClientBridge] Initialized")
    
    def connect_to_interface(self, interface_manager: SimpleUnifiedInterface):
        """Connect to the unified interface manager"""
        self.interface_manager = interface_manager
        # SimpleUnifiedInterface doesn't use separate display/conversation managers
        self.gradio_display_manager = None
        self.conversation_reader = None
        
        print("[UnifiedClientBridge] Connected to simple unified interface")
    
    def start_bridge(self):
        """Start the bridge for real-time synchronization"""
        if self.bridge_active:
            return
        
        self.bridge_active = True
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        
        print("[UnifiedClientBridge] Bridge started")
    
    def stop_bridge(self):
        """Stop the bridge"""
        self.bridge_active = False
        if self.sync_thread:
            self.sync_thread.join(timeout=2)
        
        print("[UnifiedClientBridge] Bridge stopped")
    
    def update_display_state(self, state: str, mood: str = "casual", text: str = None):
        """Update the display state in the unified interface"""
        if self.interface_manager:
            # Update the simple interface state
            self.interface_manager.update_display_state(state, mood)
            print(f"[UnifiedClientBridge] Updated display: {state}/{mood}")
    
    def update_system_status(self, status: str):
        """Update the system status in the unified interface"""
        if self.interface_manager:
            self.interface_manager.current_status = status
    
    def _sync_worker(self):
        """Background worker for synchronization tasks"""
        while self.bridge_active:
            try:
                # Perform any periodic synchronization tasks here
                time.sleep(5)
            except Exception as e:
                print(f"[UnifiedClientBridge] Sync error: {e}")
                time.sleep(1)


class UnifiedPiMCPClient:
    """
    Modified version of PiMCPClient that can optionally use the unified Gradio interface
    instead of the separate pygame window.
    """
    
    def __init__(self, server_url: str, device_id: str, use_unified_interface: bool = False, 
                 interface_port: int = 7860):
        # Import original client components
        from run_v2 import PiMCPClient
        
        # Store configuration
        self.use_unified_interface = use_unified_interface
        self.interface_port = interface_port
        self.bridge: Optional[UnifiedClientBridge] = None
        self.interface_thread: Optional[threading.Thread] = None
        self.unified_interface = None
        
        if use_unified_interface:
            print("[UnifiedPiMCPClient] Initializing with unified interface...")
            self._setup_unified_interface()
            
            # Initialize the original client without display manager
            self.original_client = PiMCPClient(server_url, device_id)
            
            # Replace the display manager with our bridge
            self._replace_display_manager()
        else:
            print("[UnifiedPiMCPClient] Initializing with standard interface...")
            self.original_client = PiMCPClient(server_url, device_id)
    
    def _setup_unified_interface(self):
        """Set up the unified Gradio interface"""
        try:
            # Create the unified interface in a separate thread
            def launch_interface():
                self.unified_interface = SimpleUnifiedInterface()
                interface = self.unified_interface.create_interface()
                
                # Store reference (SimpleUnifiedInterface doesn't need background tasks)
                interface.interface_manager = self.unified_interface
                
                # Launch the interface
                interface.launch(
                    server_name="0.0.0.0",
                    server_port=self.interface_port,
                    share=False,
                    debug=False,
                    show_error=True,
                    prevent_thread_lock=True,
                    quiet=True
                )
            
            self.interface_thread = threading.Thread(target=launch_interface, daemon=True)
            self.interface_thread.start()
            
            # Wait a moment for the interface to start
            time.sleep(2)
            
            # Set up the bridge
            self.bridge = UnifiedClientBridge()
            if self.unified_interface:
                self.bridge.connect_to_interface(self.unified_interface)
                self.bridge.start_bridge()
            
            print(f"[UnifiedPiMCPClient] Unified interface available at http://localhost:{self.interface_port}")
            
        except Exception as e:
            print(f"[UnifiedPiMCPClient] Error setting up unified interface: {e}")
            self.use_unified_interface = False
    
    def _replace_display_manager(self):
        """Replace the original display manager with bridge integration"""
        if not self.bridge:
            return
        
        # Store original display manager
        original_display_manager = self.original_client.display_manager
        
        # Create a proxy display manager that forwards to the bridge
        class ProxyDisplayManager:
            def __init__(self, bridge):
                self.bridge = bridge
                self.current_state = 'boot'
                self.current_mood = 'casual'
            
            async def update_display(self, state, mood=None, text=None):
                self.current_state = state
                self.current_mood = mood or 'casual'
                self.bridge.update_display_state(state, self.current_mood, text)
                print(f"Display updated via bridge - State: {state}, Mood: {self.current_mood}")
            
            async def rotate_background(self):
                """Background rotation is handled by the unified interface"""
                # The GradioDisplayManager handles rotation, so this is a no-op
                while True:
                    await asyncio.sleep(60)  # Keep the task alive but do nothing
            
            def cleanup(self):
                pass  # Handled by bridge
        
        # Replace the display manager
        self.original_client.display_manager = ProxyDisplayManager(self.bridge)
    
    async def run(self):
        """Run the client with optional unified interface"""
        try:
            if self.use_unified_interface and self.bridge:
                self.bridge.update_system_status("Starting client...")
            
            # Run the original client
            await self.original_client.run()
            
        except Exception as e:
            print(f"[UnifiedPiMCPClient] Error in run: {e}")
            if self.use_unified_interface and self.bridge:
                self.bridge.update_system_status(f"Error: {e}")
            raise
    
    async def cleanup(self):
        """Clean up resources"""
        print("[UnifiedPiMCPClient] Cleaning up...")
        
        # Clean up original client
        await self.original_client.cleanup()
        
        # Clean up unified interface
        if self.bridge:
            self.bridge.stop_bridge()
        
        if self.unified_interface:
            self.unified_interface.cleanup()
        
        print("[UnifiedPiMCPClient] Cleanup complete")
    
    def __getattr__(self, name):
        """Delegate unknown attributes to the original client"""
        return getattr(self.original_client, name)


def create_unified_client(server_url: str, device_id: str, use_unified_interface: bool = False,
                         interface_port: int = 7860) -> UnifiedPiMCPClient:
    """
    Factory function to create a unified client
    
    Args:
        server_url: MCP server URL
        device_id: Device identifier
        use_unified_interface: Whether to use the unified Gradio interface
        interface_port: Port for the Gradio interface
    
    Returns:
        UnifiedPiMCPClient instance
    """
    return UnifiedPiMCPClient(
        server_url=server_url,
        device_id=device_id,
        use_unified_interface=use_unified_interface,
        interface_port=interface_port
    )