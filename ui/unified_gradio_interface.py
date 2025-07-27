#!/usr/bin/env python3

import gradio as gr
import json
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image

# Import our custom components
from ui.gradio_display_manager import GradioDisplayManager
from system.conversation_history_reader import ConversationHistoryReader
from communication.client_config import (
    client_settings, load_client_settings, save_client_settings,
    get_active_tts_provider, set_active_tts_provider,
    VOSK_MODEL_PATHS_AVAILABLE, MOOD_COLORS
)


class UnifiedRP500Interface:
    """
    Unified Gradio interface for the RP500-Client that combines:
    - Real-time pygame display
    - Conversation history 
    - Quick controls
    - Configuration options
    """
    
    def __init__(self):
        print("[UnifiedRP500Interface] Initializing unified interface...")
        
        # Load current settings
        load_client_settings()
        
        # Initialize display manager
        self.display_manager = GradioDisplayManager(
            window_size=client_settings.get("DISPLAY_WINDOW_SIZE", 512),
            update_callback=self._on_display_update
        )
        
        # Initialize conversation history reader
        self.conversation_reader = ConversationHistoryReader()
        self.conversation_reader.set_update_callback(self._on_conversation_update)
        
        # State tracking
        self.current_status = "Initializing..."
        self.current_state = "boot"
        self.current_mood = "casual"
        
        # Gradio components (will be set during interface creation)
        self.display_image = None
        self.conversation_html = None
        self.status_display = None
        self.message_count_display = None
        
        # Background tasks
        self.background_tasks = []
        self.shutdown_event = threading.Event()
        
        print("[UnifiedRP500Interface] Initialization complete")
    
    def _on_display_update(self, pil_image: Image.Image):
        """Called when display manager updates the image"""
        try:
            if self.display_image is not None:
                # Store the image for the next interface refresh
                # Note: Gradio Image components update automatically with the interface
                pass
        except Exception as e:
            print(f"[UnifiedRP500Interface] Error updating display: {e}")
    
    def _on_conversation_update(self):
        """Called when conversation history is updated"""
        try:
            if self.conversation_html is not None:
                # Update conversation display
                html_content = self.conversation_reader.get_formatted_chat_html()
                self.conversation_html.update(value=html_content)
                
            if self.message_count_display is not None:
                # Update message count
                stats = self.conversation_reader.get_today_message_count()
                stats_text = f"Today: {stats['total_messages']} messages ({stats['user_messages']} user, {stats['assistant_messages']} AI)"
                self.message_count_display.update(value=stats_text)
                
        except Exception as e:
            print(f"[UnifiedRP500Interface] Error updating conversation: {e}")
    
    def get_system_status(self) -> Dict[str, str]:
        """Get current system status information"""
        return {
            "status": self.current_status,
            "state": self.current_state,
            "mood": self.current_mood,
            "tts_provider": get_active_tts_provider(),
            "tts_mode": client_settings.get("tts_mode", "api"),
            "vosk_model": client_settings.get("vosk_model_size", "medium"),
            "server_url": client_settings.get("SERVER_URL", ""),
        }
    
    def update_display_state(self, state: str, mood: str = "casual"):
        """Update the display state (for external control)"""
        self.current_state = state
        self.current_mood = mood
        
        # Update display manager asynchronously
        async def update_async():
            await self.display_manager.update_display(state, mood)
        
        # Run in background thread if not in async context
        try:
            asyncio.create_task(update_async())
        except RuntimeError:
            # If no event loop, run in thread
            threading.Thread(target=lambda: asyncio.run(update_async())).start()
    
    def create_interface(self):
        """Create the unified Gradio interface"""
        
        # Custom CSS for better styling
        custom_css = """
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .conversation-panel {
            height: 600px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px;
        }
        .display-panel {
            text-align: center;
            padding: 20px;
        }
        .quick-controls {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        .status-indicator {
            background: #e3f2fd;
            border-radius: 5px;
            padding: 10px;
            margin: 5px 0;
            font-family: monospace;
        }
        """
        
        with gr.Blocks(title="LAURA - Unified Control Interface", css=custom_css) as interface:
            
            gr.Markdown("# 🎧 LAURA - Unified Control Interface")
            gr.Markdown("Real-time voice assistant monitoring and control")
            
            with gr.Tabs() as tabs:
                
                # Main Dashboard Tab
                with gr.Tab("📊 Dashboard", id="dashboard"):
                    
                    with gr.Row():
                        # Left column - Conversation History
                        with gr.Column(scale=2):
                            gr.Markdown("### 💬 Conversation History")
                            
                            # Message count and stats
                            self.message_count_display = gr.Textbox(
                                label="Statistics",
                                value="Loading conversation history...",
                                interactive=False,
                                container=True
                            )
                            
                            # Conversation display
                            self.conversation_html = gr.HTML(
                                value=self.conversation_reader.get_formatted_chat_html(),
                                elem_classes=["conversation-panel"]
                            )
                            
                            # Search functionality
                            with gr.Row():
                                search_input = gr.Textbox(
                                    placeholder="Search conversations...",
                                    scale=3
                                )
                                search_btn = gr.Button("🔍 Search", scale=1)
                        
                        # Right column - Display and Controls
                        with gr.Column(scale=1):
                            gr.Markdown("### 🖼️ LAURA Display")
                            
                            # Main pygame display
                            self.display_image = gr.Image(
                                value=self.display_manager.get_current_image(),
                                height=400,
                                width=400,
                                elem_classes=["display-panel"],
                                interactive=False,
                                show_label=False
                            )
                            
                            # System status
                            with gr.Group():
                                gr.Markdown("### ⚡ Quick Controls")
                                
                                # LLM Provider Selection
                                llm_provider = gr.Radio(
                                    label="🧠 LLM Provider",
                                    choices=["Anthropic (Claude)", "OpenAI (GPT)", "Local Inference"],
                                    value="Anthropic (Claude)",
                                    interactive=True
                                )
                                
                                # Voice/Persona Selection
                                voice_persona = gr.Dropdown(
                                    label="🎭 Voice Persona",
                                    choices=["Laura", "Max", "Custom"],
                                    value="Laura",
                                    interactive=True
                                )
                                
                                # TTS Mode
                                tts_mode = gr.Radio(
                                    label="🔊 TTS Mode",
                                    choices=["API (Cloud)", "Local"],
                                    value="API (Cloud)" if client_settings.get("tts_mode") == "api" else "Local",
                                    interactive=True
                                )
                                
                                # TTS Provider (when in API mode)
                                tts_provider = gr.Dropdown(
                                    label="🎤 TTS Provider",
                                    choices=["ElevenLabs", "Cartesia"],
                                    value="ElevenLabs" if get_active_tts_provider() == "elevenlabs" else "Cartesia",
                                    interactive=True
                                )
                            
                            # Status Display
                            with gr.Group():
                                gr.Markdown("### 📊 System Status")
                                
                                self.status_display = gr.JSON(
                                    value=self.get_system_status(),
                                    label="Current Status",
                                    elem_classes=["status-indicator"]
                                )
                                
                                # Manual refresh button
                                refresh_btn = gr.Button("🔄 Refresh Status", variant="secondary")
                
                # Configuration Tab
                with gr.Tab("⚙️ Configuration", id="config"):
                    gr.Markdown("### 🔧 Advanced Configuration")
                    gr.Markdown("Detailed system configuration options")
                    
                    with gr.Tabs():
                        # Basic Settings
                        with gr.Tab("Basic Settings"):
                            with gr.Row():
                                with gr.Column():
                                    server_url = gr.Textbox(
                                        label="Server URL",
                                        value=client_settings.get("SERVER_URL", ""),
                                        placeholder="http://174.165.47.128:8765"
                                    )
                                    device_id = gr.Textbox(
                                        label="Device ID",
                                        value=client_settings.get("DEVICE_ID", ""),
                                        placeholder="Pi500-og"
                                    )
                                    sample_rate = gr.Number(
                                        label="Audio Sample Rate",
                                        value=client_settings.get("AUDIO_SAMPLE_RATE", 16000),
                                        precision=0
                                    )
                                
                                with gr.Column():
                                    vosk_model = gr.Dropdown(
                                        label="VOSK Model Size",
                                        choices=list(VOSK_MODEL_PATHS_AVAILABLE.keys()),
                                        value=client_settings.get("vosk_model_size", "medium")
                                    )
                                    window_size = gr.Number(
                                        label="Display Window Size",
                                        value=client_settings.get("DISPLAY_WINDOW_SIZE", 512),
                                        precision=0
                                    )
                            
                            config_save_btn = gr.Button("💾 Save Configuration", variant="primary")
                            config_status = gr.Textbox(label="Status", interactive=False)
                        
                        # Wake Words
                        with gr.Tab("Wake Words"):
                            gr.Markdown("### Configure wake word models and sensitivities")
                            
                            wake_words_text = gr.Textbox(
                                label="Wake Words Configuration",
                                value=self._get_current_wake_words(),
                                lines=8,
                                placeholder="Laura.pmdl: 0.45\nWake_up_Laura.pmdl: 0.5"
                            )
                            
                            wake_save_btn = gr.Button("💾 Save Wake Words", variant="primary")
                            wake_status = gr.Textbox(label="Status", interactive=False)
                        
                        # Export/Import
                        with gr.Tab("Export/Import"):
                            gr.Markdown("### Export and import configuration")
                            
                            with gr.Row():
                                export_btn = gr.Button("📤 Export Config", variant="secondary")
                                import_btn = gr.Button("📥 Import Config", variant="secondary")
                            
                            config_export = gr.Code(label="Configuration JSON", language="json")
                            import_status = gr.Textbox(label="Status", interactive=False)
                
                # Logs and Monitoring Tab
                with gr.Tab("📋 Logs", id="logs"):
                    gr.Markdown("### 📋 System Logs and Monitoring")
                    
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### Recent Activity")
                            log_display = gr.Textbox(
                                value="System logs will appear here...",
                                lines=20,
                                interactive=False,
                                label="System Logs"
                            )
                        
                        with gr.Column():
                            gr.Markdown("### Conversation Analytics")
                            analytics_display = gr.JSON(
                                value=self.conversation_reader.get_today_message_count(),
                                label="Today's Statistics"
                            )
            
            # Event handlers
            def save_basic_config(url, dev_id, rate, vosk_m, win_size):
                try:
                    client_settings.update({
                        "SERVER_URL": url,
                        "DEVICE_ID": dev_id,
                        "AUDIO_SAMPLE_RATE": int(rate),
                        "vosk_model_size": vosk_m,
                        "DISPLAY_WINDOW_SIZE": int(win_size)
                    })
                    save_client_settings()
                    return "✅ Configuration saved successfully!"
                except Exception as e:
                    return f"❌ Error saving configuration: {str(e)}"
            
            def update_quick_controls(llm, voice, tts_mode_val, tts_prov):
                try:
                    # Update TTS settings
                    new_tts_mode = "api" if tts_mode_val == "API (Cloud)" else "local"
                    new_tts_provider = "elevenlabs" if tts_prov == "ElevenLabs" else "cartesia"
                    
                    client_settings["tts_mode"] = new_tts_mode
                    client_settings["api_tts_provider"] = new_tts_provider
                    save_client_settings()
                    
                    return self.get_system_status()
                except Exception as e:
                    print(f"Error updating quick controls: {e}")
                    return self.get_system_status()
            
            def search_conversations(query):
                if query.strip():
                    results = self.conversation_reader.search_messages(query)
                    # Format search results
                    html_parts = ['<div style="padding: 10px;">']
                    html_parts.append(f'<h4>Search Results for "{query}" ({len(results)} found)</h4>')
                    
                    for msg in results:
                        role_label = "You" if msg['role'] == 'user' else "LAURA"
                        bg_color = "#e3f2fd" if msg['role'] == 'user' else "#f1f8e9"
                        
                        html_parts.append(f'''
                        <div style="background: {bg_color}; margin: 10px 0; padding: 10px; border-radius: 5px;">
                            <strong>{role_label}</strong> <small>({msg['time']})</small><br>
                            {msg['content']}
                        </div>
                        ''')
                    
                    html_parts.append('</div>')
                    return ''.join(html_parts)
                else:
                    return self.conversation_reader.get_formatted_chat_html()
            
            def export_config():
                try:
                    config_json = json.dumps(client_settings, indent=2, default=str)
                    return config_json, "✅ Configuration exported successfully!"
                except Exception as e:
                    return "", f"❌ Error exporting config: {str(e)}"
            
            # Wire up event handlers
            config_save_btn.click(
                save_basic_config,
                inputs=[server_url, device_id, sample_rate, vosk_model, window_size],
                outputs=config_status
            )
            
            # Quick controls auto-update
            for component in [llm_provider, voice_persona, tts_mode, tts_provider]:
                component.change(
                    update_quick_controls,
                    inputs=[llm_provider, voice_persona, tts_mode, tts_provider],
                    outputs=self.status_display
                )
            
            search_btn.click(
                search_conversations,
                inputs=search_input,
                outputs=self.conversation_html
            )
            
            refresh_btn.click(
                lambda: self.get_system_status(),
                outputs=self.status_display
            )
            
            export_btn.click(
                export_config,
                outputs=[config_export, import_status]
            )
        
        return interface
    
    def _get_current_wake_words(self):
        """Get current wake word settings as formatted text"""
        wake_words = client_settings.get("WAKE_WORDS_AND_SENSITIVITIES", {})
        return "\n".join([f"{model}: {sensitivity}" for model, sensitivity in wake_words.items()])
    
    def start_background_tasks(self):
        """Start background monitoring tasks"""
        print("[UnifiedRP500Interface] Starting background tasks...")
        
        # Start conversation monitoring
        self.conversation_reader.start_monitoring()
        
        # Start display rotation task
        def run_display_rotation():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.display_manager.rotate_background())
        
        rotation_thread = threading.Thread(target=run_display_rotation, daemon=True)
        rotation_thread.start()
        self.background_tasks.append(rotation_thread)
        
        print("[UnifiedRP500Interface] Background tasks started")
    
    def stop_background_tasks(self):
        """Stop all background tasks"""
        print("[UnifiedRP500Interface] Stopping background tasks...")
        
        self.shutdown_event.set()
        self.conversation_reader.stop_monitoring()
        
        for task in self.background_tasks:
            if hasattr(task, 'cancel'):
                task.cancel()
        
        print("[UnifiedRP500Interface] Background tasks stopped")
    
    def cleanup(self):
        """Clean up resources"""
        print("[UnifiedRP500Interface] Cleaning up...")
        self.stop_background_tasks()
        self.display_manager.cleanup()
        self.conversation_reader.cleanup()
        print("[UnifiedRP500Interface] Cleanup complete")


def create_unified_interface():
    """Create and return the unified interface"""
    interface_manager = UnifiedRP500Interface()
    interface = interface_manager.create_interface()
    
    # Start background tasks
    interface_manager.start_background_tasks()
    
    # Store reference for cleanup
    interface.interface_manager = interface_manager
    
    return interface


if __name__ == "__main__":
    # Launch the unified interface
    print("🚀 Starting LAURA Unified Interface...")
    
    interface = create_unified_interface()
    
    try:
        interface.launch(
            server_name="0.0.0.0",  # Allow access from other devices
            server_port=7860,       # Default Gradio port
            share=False,            # Set to True for public access
            debug=True,
            show_error=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        if hasattr(interface, 'interface_manager'):
            interface.interface_manager.cleanup()
        print("✅ Shutdown complete")