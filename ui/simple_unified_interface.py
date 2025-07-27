#!/usr/bin/env python3

import gradio as gr
import json
import time
import threading
from pathlib import Path
from PIL import Image
import numpy as np
import random

# Import configuration
from communication.client_config import client_settings, load_client_settings, get_mood_color_config
from system.conversation_history_reader import ConversationHistoryReader


class SimpleUnifiedInterface:
    """
    Simplified unified interface that focuses on core functionality
    without complex real-time updates that cause async issues.
    """
    
    def __init__(self):
        print("[SimpleUnifiedInterface] Initializing...")
        load_client_settings()
        
        # Chat history is managed by server, not client
        
        # Initialize display state
        self.current_state = 'boot'
        self.current_mood = 'casual'
        self.image_cache = {}
        self.base_path = Path('/home/user/RP500-Client/images/laura')
        
        # Load images into cache
        self.load_image_directories()
        
        # Create initial display image
        self.current_display_image = self.get_state_image(self.current_state, self.current_mood)
        self.placeholder_image = self.current_display_image
        
        print("[SimpleUnifiedInterface] Initialization complete")
    
    def load_image_directories(self):
        """Load all available images into cache for fast access"""
        print("[SimpleUnifiedInterface] Loading image directories...")
        
        # Available moods for speaking state
        moods = [
            "amused", "annoyed", "caring", "casual", "cheerful", "concerned", 
            "confused", "curious", "disappointed", "embarrassed", "excited", 
            "frustrated", "interested", "sassy", "scared", "surprised", 
            "suspicious", "thoughtful"
        ]
        
        # State directory mapping
        states = {
            'listening': str(self.base_path / 'listening'),
            'idle': str(self.base_path / 'idle'),
            'sleep': str(self.base_path / 'sleep'),
            'speaking': str(self.base_path / 'speaking'),
            'thinking': str(self.base_path / 'thinking'),
            'wake': str(self.base_path / 'wake'),
            'boot': str(self.base_path / 'boot'),
            'system': str(self.base_path / 'system'),
            'tool_use': str(self.base_path / 'tool_use'),
            'notification': str(self.base_path / 'speaking'),
            'code': str(self.base_path / 'code'),
            'error': str(self.base_path / 'error'),
            'disconnected': str(self.base_path / 'disconnected'),
        }
        
        for state_name, state_path in states.items():
            state_dir = Path(state_path)
            
            if not state_dir.exists():
                continue
                
            self.image_cache[state_name] = {}
            
            # For speaking state, load mood-based subdirectories
            if state_name == 'speaking':
                for mood in moods:
                    mood_dir = state_dir / mood
                    if mood_dir.exists():
                        mood_images = []
                        for img_file in mood_dir.glob('*.png'):
                            try:
                                mood_images.append(str(img_file))
                            except Exception as e:
                                print(f"Warning: Could not load {img_file}: {e}")
                        
                        if mood_images:
                            self.image_cache[state_name][mood] = mood_images
            else:
                # For other states, load images directly
                state_images = []
                for img_file in state_dir.glob('*.png'):
                    try:
                        state_images.append(str(img_file))
                    except Exception as e:
                        print(f"Warning: Could not load {img_file}: {e}")
                
                if state_images:
                    self.image_cache[state_name]['default'] = state_images
        
        print(f"[SimpleUnifiedInterface] Loaded images for {len(self.image_cache)} states")
    
    def get_state_image(self, state, mood='casual'):
        """Get an image for the given state and mood"""
        try:
            if state in self.image_cache:
                state_images = self.image_cache[state]
                
                # For speaking state, try to get mood-specific image
                if state == 'speaking' and mood and mood in state_images:
                    mood_images = state_images[mood]
                    if mood_images:
                        image_path = random.choice(mood_images)
                        return Image.open(image_path).resize((300, 300))
                
                # Fallback to default images for the state
                if 'default' in state_images:
                    default_images = state_images['default']
                    if default_images:
                        image_path = random.choice(default_images)
                        return Image.open(image_path).resize((300, 300))
            
            # Fallback to color-based image
            return self.create_color_image(mood)
            
        except Exception as e:
            print(f"[SimpleUnifiedInterface] Error loading image for {state}/{mood}: {e}")
            return self.create_color_image(mood)
    
    def create_color_image(self, mood='casual'):
        """Create a color-based image when no image files are available"""
        try:
            color_config = get_mood_color_config(mood)
            if color_config and 'gradient_colors' in color_config:
                color = color_config['gradient_colors'][0]
            else:
                color = (100, 150, 200)  # Default blue
            
            # Create a simple colored image
            img_array = np.full((300, 300, 3), color, dtype=np.uint8)
            
            # Add a circle in the center
            center = 150
            radius = 100
            y, x = np.ogrid[:300, :300]
            mask = (x - center) ** 2 + (y - center) ** 2 <= radius ** 2
            img_array[mask] = [min(255, c + 50) for c in color]  # Lighter center
            
            return Image.fromarray(img_array)
            
        except Exception as e:
            print(f"[SimpleUnifiedInterface] Error creating color image: {e}")
            # Ultimate fallback
            img_array = np.full((300, 300, 3), (128, 128, 128), dtype=np.uint8)
            return Image.fromarray(img_array)
    
    def update_display_state(self, state, mood='casual'):
        """Update the current display state and mood"""
        self.current_state = state
        self.current_mood = mood
        self.current_display_image = self.get_state_image(state, mood)
        print(f"[SimpleUnifiedInterface] Display updated - State: {state}, Mood: {mood}")
        return self.current_display_image
    
    def get_current_display_image(self):
        """Get the current display image"""
        return self.current_display_image
    
    def cycle_test_states(self):
        """Cycle through different states for testing"""
        test_states = ['boot', 'listening', 'thinking', 'speaking', 'idle']
        test_moods = ['casual', 'excited', 'curious', 'thoughtful', 'amused']
        
        import random
        state = random.choice(test_states)
        mood = random.choice(test_moods) if state == 'speaking' else 'casual'
        
        return self.update_display_state(state, mood)
    
    def get_conversation_html(self):
        """Get conversation history placeholder"""
        return """
        <div style="padding: 20px; text-align: center; color: #666;">
            <h3>💬 Conversation History</h3>
            <p>Chat history is managed by the server</p>
            <p>Use voice commands to interact with LAURA</p>
        </div>
        """
    
    def get_system_status(self):
        """Get current system status"""
        return {
            "Server URL": client_settings.get("SERVER_URL", "Unknown"),
            "Device ID": client_settings.get("DEVICE_ID", "Unknown"),
            "TTS Mode": client_settings.get("tts_mode", "Unknown"),
            "TTS Provider": client_settings.get("api_tts_provider", "Unknown"),
            "VOSK Model": client_settings.get("vosk_model_size", "Unknown"),
            "Audio Sample Rate": client_settings.get("AUDIO_SAMPLE_RATE", "Unknown"),
            "Status": "Code Mode Active" if True else "Connected"
        }
    
    def get_message_stats(self):
        """Get message statistics placeholder"""
        return "Chat statistics available on server"
    
    def refresh_conversation(self):
        """Refresh conversation placeholder"""
        return self.get_conversation_html(), self.get_message_stats()
    
    def search_conversations(self, query):
        """Search conversation placeholder"""
        return """
        <div style="padding: 20px; text-align: center; color: #666;">
            <h3>🔍 Search Not Available</h3>
            <p>Chat search is handled by the server</p>
        </div>
        """
    
    def update_config(self, server_url, device_id, tts_mode, tts_provider):
        """Update basic configuration"""
        try:
            client_settings.update({
                "SERVER_URL": server_url,
                "DEVICE_ID": device_id,
                "tts_mode": tts_mode,
                "api_tts_provider": tts_provider
            })
            
            # Save to file
            from communication.client_config import save_client_settings
            save_client_settings()
            
            return "✅ Configuration updated successfully!", self.get_system_status()
        except Exception as e:
            return f"❌ Error updating config: {e}", self.get_system_status()
    
    def create_interface(self):
        """Create the simplified Gradio interface"""
        
        # Store reference to self for use in nested functions
        interface_manager = self
        
        # Custom CSS for better appearance
        custom_css = """
        .main-container { max-width: 1200px; margin: 0 auto; }
        .conversation-panel { 
            height: 500px; overflow-y: auto; border: 1px solid #ddd; 
            border-radius: 8px; padding: 15px; background: #fafafa;
        }
        .display-panel { 
            text-align: center; padding: 20px; 
            border: 2px solid #ddd; border-radius: 12px; background: #f8f9fa;
        }
        .status-panel {
            background: #e3f2fd; border-radius: 8px; padding: 15px; 
            font-family: monospace; font-size: 12px;
        }
        .control-panel {
            background: #f1f8e9; border-radius: 8px; padding: 15px;
            border: 1px solid #c8e6c9;
        }
        """
        
        with gr.Blocks(title="LAURA - Unified Dashboard", css=custom_css) as interface:
            
            gr.Markdown("# 🎧 LAURA - Unified Dashboard")
            gr.Markdown("**Simplified interface for monitoring and controlling your voice assistant**")
            
            with gr.Row():
                # Left Column - Conversation History
                with gr.Column(scale=2):
                    gr.Markdown("### 💬 Conversation History")
                    
                    # Message statistics
                    message_stats = gr.Textbox(
                        value=self.get_message_stats(),
                        label="📊 Statistics",
                        interactive=False,
                        max_lines=1
                    )
                    
                    # Search bar
                    with gr.Row():
                        search_input = gr.Textbox(
                            placeholder="Search conversations...",
                            label="🔍 Search",
                            scale=3
                        )
                        search_btn = gr.Button("Search", scale=1, variant="secondary")
                        refresh_btn = gr.Button("🔄 Refresh", scale=1, variant="secondary")
                    
                    # Conversation display
                    conversation_display = gr.HTML(
                        value=self.get_conversation_html(),
                        elem_classes=["conversation-panel"]
                    )
                
                # Right Column - Display and Controls
                with gr.Column(scale=1):
                    gr.Markdown("### 🖼️ LAURA Display")
                    
                    # Display placeholder
                    display_image = gr.Image(
                        value=self.current_display_image,
                        height=300,
                        width=300,
                        elem_classes=["display-panel"],
                        interactive=False,
                        show_label=False
                    )
                    
                    # State/mood display info
                    state_info = gr.Textbox(
                        value=f"State: {self.current_state} | Mood: {self.current_mood}",
                        label="Current State",
                        interactive=False,
                        max_lines=1
                    )
                    
                    # System Status
                    gr.Markdown("### 📊 System Status")
                    status_display = gr.Textbox(
                        value=f"Server: {client_settings.get('SERVER_URL', 'Unknown')}\nDevice: {client_settings.get('DEVICE_ID', 'Unknown')}\nTTS: {client_settings.get('tts_mode', 'Unknown')}",
                        label="Current Status",
                        interactive=False,
                        max_lines=5,
                        elem_classes=["status-panel"]
                    )
            
            # Configuration Section
            with gr.Accordion("⚙️ Quick Configuration", open=False):
                with gr.Row():
                    with gr.Column():
                        config_server_url = gr.Textbox(
                            value=client_settings.get("SERVER_URL", ""),
                            label="Server URL",
                            placeholder="http://174.165.47.128:8765"
                        )
                        config_device_id = gr.Textbox(
                            value=client_settings.get("DEVICE_ID", ""),
                            label="Device ID",
                            placeholder="Pi500-og"
                        )
                    
                    with gr.Column():
                        config_tts_mode = gr.Dropdown(
                            choices=["api", "local"],
                            value=client_settings.get("tts_mode", "api"),
                            label="TTS Mode"
                        )
                        config_tts_provider = gr.Dropdown(
                            choices=["elevenlabs", "cartesia"],
                            value=client_settings.get("api_tts_provider", "elevenlabs"),
                            label="TTS Provider"
                        )
                
                config_save_btn = gr.Button("💾 Save Configuration", variant="primary")
                config_status = gr.Textbox(label="Configuration Status", interactive=False)
            
            # Event handlers
            def handle_search(query):
                return self.search_conversations(query)
            
            def handle_refresh():
                conv_html, stats = self.refresh_conversation()
                return conv_html, stats
            
            def handle_config_save(url, device, tts_mode, tts_prov):
                status, sys_status = self.update_config(url, device, tts_mode, tts_prov)
                status_text = f"Server: {sys_status.get('Server URL', 'Unknown')}\nDevice: {sys_status.get('Device ID', 'Unknown')}\nTTS: {sys_status.get('TTS Mode', 'Unknown')}"
                return status, status_text
            
            # Wire up events
            search_btn.click(
                handle_search,
                inputs=[search_input],
                outputs=[conversation_display]
            )
            
            refresh_btn.click(
                handle_refresh,
                outputs=[conversation_display, message_stats]
            )
            
            config_save_btn.click(
                handle_config_save,
                inputs=[config_server_url, config_device_id, config_tts_mode, config_tts_provider],
                outputs=[config_status, status_display]
            )
            
            # Test button for display updates
            with gr.Row():
                test_display_btn = gr.Button("🔄 Test Display", variant="secondary")
            
            def handle_test_display():
                new_image = interface_manager.cycle_test_states()
                state_text = f"State: {interface_manager.current_state} | Mood: {interface_manager.current_mood}"
                return new_image, state_text
            
            test_display_btn.click(
                handle_test_display,
                outputs=[display_image, state_info]
            )
            
            # Auto-refresh every 30 seconds
            interface.load(
                handle_refresh,
                outputs=[conversation_display, message_stats],
                every=30
            )
        
        return interface


def create_simple_interface():
    """Create and return the simplified interface"""
    interface_manager = SimpleUnifiedInterface()
    return interface_manager.create_interface()


if __name__ == "__main__":
    print("🚀 Starting LAURA Simple Unified Interface...")
    
    interface = create_simple_interface()
    
    try:
        interface.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=False,
            show_error=True,
            inbrowser=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Interface stopped")
    except Exception as e:
        print(f"❌ Error: {e}")