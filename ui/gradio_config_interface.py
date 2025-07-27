#!/usr/bin/env python3

import gradio as gr
import json
from pathlib import Path
import sys
import os

# Add the client directory to path so we can import client_config
sys.path.append(str(Path(__file__).parent))

from communication.client_config import (
    client_settings, load_client_settings, save_client_settings,
    get_active_tts_provider, set_active_tts_provider,
    VOSK_MODEL_PATHS_AVAILABLE, MOOD_COLORS
)

class RP500ConfigInterface:
    def __init__(self):
        self.load_current_settings()
    
    def load_current_settings(self):
        """Load current settings from config file"""
        load_client_settings()
        
    def save_and_reload(self, **kwargs):
        """Save settings and return success message"""
        try:
            # Update client_settings with new values
            for key, value in kwargs.items():
                if key in client_settings:
                    client_settings[key] = value
            
            save_client_settings()
            self.load_current_settings()
            return "✅ Settings saved successfully!"
        except Exception as e:
            return f"❌ Error saving settings: {str(e)}"
    
    def get_current_wake_words(self):
        """Get current wake word settings as formatted text"""
        wake_words = client_settings.get("WAKE_WORDS_AND_SENSITIVITIES", {})
        return "\n".join([f"{model}: {sensitivity}" for model, sensitivity in wake_words.items()])
    
    def update_wake_words(self, wake_word_text):
        """Update wake word settings from text input"""
        try:
            wake_words = {}
            for line in wake_word_text.strip().split('\n'):
                if ':' in line:
                    model, sensitivity = line.split(':', 1)
                    wake_words[model.strip()] = float(sensitivity.strip())
            
            client_settings["WAKE_WORDS_AND_SENSITIVITIES"] = wake_words
            save_client_settings()
            return "✅ Wake words updated successfully!"
        except Exception as e:
            return f"❌ Error updating wake words: {str(e)}"
    
    def get_current_vad_settings(self):
        """Get current VAD settings as JSON string"""
        vad = client_settings.get("vad_settings", {})
        return json.dumps(vad, indent=2)
    
    def update_vad_settings(self, vad_json):
        """Update VAD settings from JSON input"""
        try:
            vad_settings = json.loads(vad_json)
            client_settings["vad_settings"] = vad_settings
            save_client_settings()
            return "✅ VAD settings updated successfully!"
        except Exception as e:
            return f"❌ Error updating VAD settings: {str(e)}"
    
    def get_current_persona_configs(self):
        """Get current persona configs as JSON string"""
        personas = client_settings.get("persona_voice_configs", {})
        return json.dumps(personas, indent=2)
    
    def update_persona_configs(self, persona_json):
        """Update persona configs from JSON input"""
        try:
            persona_configs = json.loads(persona_json)
            client_settings["persona_voice_configs"] = persona_configs
            save_client_settings()
            return "✅ Persona configurations updated successfully!"
        except Exception as e:
            return f"❌ Error updating persona configurations: {str(e)}"

def create_interface():
    config_manager = RP500ConfigInterface()
    
    with gr.Blocks(title="RP500-Client Configuration") as interface:
        gr.Markdown("# 🎧 RP500-Client Configuration Interface")
        gr.Markdown("Configure your voice assistant settings through this web interface instead of manually editing files.")
        
        with gr.Tabs():
            # Basic Settings Tab
            with gr.Tab("🔧 Basic Settings"):
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
                        tts_mode = gr.Dropdown(
                            label="TTS Mode",
                            choices=["api", "local"],
                            value=client_settings.get("tts_mode", "api")
                        )
                        api_tts_provider = gr.Dropdown(
                            label="API TTS Provider",
                            choices=["elevenlabs", "cartesia", "piper"],
                            value=client_settings.get("api_tts_provider", "elevenlabs")
                        )
                        vosk_model = gr.Dropdown(
                            label="VOSK Model Size",
                            choices=list(VOSK_MODEL_PATHS_AVAILABLE.keys()),
                            value=client_settings.get("vosk_model_size", "medium")
                        )
                
                basic_save_btn = gr.Button("💾 Save Basic Settings", variant="primary")
                basic_status = gr.Textbox(label="Status", interactive=False)
                
                def save_basic_settings(url, dev_id, rate, tts_m, tts_prov, vosk_m):
                    return config_manager.save_and_reload(
                        SERVER_URL=url,
                        DEVICE_ID=dev_id,
                        AUDIO_SAMPLE_RATE=int(rate),
                        tts_mode=tts_m,
                        api_tts_provider=tts_prov,
                        vosk_model_size=vosk_m
                    )
                
                basic_save_btn.click(
                    save_basic_settings,
                    inputs=[server_url, device_id, sample_rate, tts_mode, api_tts_provider, vosk_model],
                    outputs=basic_status
                )
            
            # Wake Words Tab
            with gr.Tab("👂 Wake Words"):
                gr.Markdown("### Configure wake word models and their sensitivities")
                gr.Markdown("Format: `model_name.pmdl: sensitivity_value` (one per line)")
                
                wake_words_text = gr.Textbox(
                    label="Wake Words Configuration",
                    value=config_manager.get_current_wake_words(),
                    lines=8,
                    placeholder="Laura.pmdl: 0.45\nWake_up_Laura.pmdl: 0.5"
                )
                
                wake_save_btn = gr.Button("💾 Save Wake Words", variant="primary")
                wake_status = gr.Textbox(label="Status", interactive=False)
                
                wake_save_btn.click(
                    config_manager.update_wake_words,
                    inputs=wake_words_text,
                    outputs=wake_status
                )
            
            # VAD Settings Tab
            with gr.Tab("🎙️ Voice Activity Detection"):
                gr.Markdown("### Configure Voice Activity Detection parameters")
                gr.Markdown("Advanced settings for speech detection sensitivity and timing")
                
                vad_json = gr.Code(
                    label="VAD Settings (JSON)",
                    value=config_manager.get_current_vad_settings(),
                    language="json",
                    lines=15
                )
                
                vad_save_btn = gr.Button("💾 Save VAD Settings", variant="primary")
                vad_status = gr.Textbox(label="Status", interactive=False)
                
                vad_save_btn.click(
                    config_manager.update_vad_settings,
                    inputs=vad_json,
                    outputs=vad_status
                )
            
            # TTS/Voice Settings Tab
            with gr.Tab("🗣️ Voice & TTS"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### ElevenLabs Settings")
                        eleven_voice = gr.Textbox(
                            label="Default Voice ID",
                            value=client_settings.get("elevenlabs_default_voice_name", ""),
                            placeholder="qEwI395unGwWV1dn3Y65"
                        )
                        eleven_model = gr.Textbox(
                            label="Default Model",
                            value=client_settings.get("elevenlabs_default_model", ""),
                            placeholder="eleven_flash_v2_5"
                        )
                    
                    with gr.Column():
                        gr.Markdown("### Cartesia Settings")
                        cartesia_voice = gr.Textbox(
                            label="Default Voice ID",
                            value=client_settings.get("cartesia_default_voice_id", ""),
                            placeholder="78f71eb3-187f-48b4-a763-952f2f4f838a"
                        )
                        cartesia_model = gr.Textbox(
                            label="Default Model",
                            value=client_settings.get("cartesia_default_model", ""),
                            placeholder="sonic-en"
                        )
                
                gr.Markdown("### Persona Voice Configurations")
                gr.Markdown("Configure different voices for different personas (JSON format)")
                
                persona_json = gr.Code(
                    label="Persona Configurations (JSON)",
                    value=config_manager.get_current_persona_configs(),
                    language="json",
                    lines=20
                )
                
                voice_save_btn = gr.Button("💾 Save Voice Settings", variant="primary")
                voice_status = gr.Textbox(label="Status", interactive=False)
                
                def save_voice_settings(e_voice, e_model, c_voice, c_model, persona_json_val):
                    try:
                        # Save basic TTS defaults
                        result1 = config_manager.save_and_reload(
                            elevenlabs_default_voice_name=e_voice,
                            elevenlabs_default_model=e_model,
                            cartesia_default_voice_id=c_voice,
                            cartesia_default_model=c_model
                        )
                        
                        # Save persona configs
                        result2 = config_manager.update_persona_configs(persona_json_val)
                        
                        if "successfully" in result1 and "successfully" in result2:
                            return "✅ All voice settings saved successfully!"
                        else:
                            return f"⚠️ Mixed results: {result1} | {result2}"
                    except Exception as e:
                        return f"❌ Error saving voice settings: {str(e)}"
                
                voice_save_btn.click(
                    save_voice_settings,
                    inputs=[eleven_voice, eleven_model, cartesia_voice, cartesia_model, persona_json],
                    outputs=voice_status
                )
            
            # Display Settings Tab
            with gr.Tab("🖥️ Display & UI"):
                with gr.Row():
                    with gr.Column():
                        display_svg = gr.Textbox(
                            label="Display SVG Path",
                            value=client_settings.get("DISPLAY_SVG_PATH", ""),
                            placeholder="/home/user/RP500-Client/svg files/silhouette.svg"
                        )
                        boot_img = gr.Textbox(
                            label="Boot Image Path",
                            value=client_settings.get("DISPLAY_BOOT_IMG_PATH", ""),
                            placeholder="/home/user/RP500-Client/images/laura/boot/interested01.png"
                        )
                    
                    with gr.Column():
                        window_size = gr.Number(
                            label="Display Window Size",
                            value=client_settings.get("DISPLAY_WINDOW_SIZE", 512),
                            precision=0
                        )
                        audio_visualizer = gr.Checkbox(
                            label="Enable Audio Visualizer",
                            value=client_settings.get("enable_display_audio_visualizer", True)
                        )
                
                gr.Markdown("### Available Mood Colors")
                mood_info = gr.HTML(
                    value="<br>".join([f"<strong>{mood}</strong>: {config['name']}" 
                                     for mood, config in MOOD_COLORS.items()])
                )
                
                display_save_btn = gr.Button("💾 Save Display Settings", variant="primary")
                display_status = gr.Textbox(label="Status", interactive=False)
                
                def save_display_settings(svg_path, boot_path, win_size, audio_viz):
                    return config_manager.save_and_reload(
                        DISPLAY_SVG_PATH=svg_path,
                        DISPLAY_BOOT_IMG_PATH=boot_path,
                        DISPLAY_WINDOW_SIZE=int(win_size),
                        enable_display_audio_visualizer=audio_viz
                    )
                
                display_save_btn.click(
                    save_display_settings,
                    inputs=[display_svg, boot_img, window_size, audio_visualizer],
                    outputs=display_status
                )
            
            # File Paths Tab
            with gr.Tab("📁 File Paths"):
                query_files_dir = gr.Textbox(
                    label="Query Files Directory",
                    value=client_settings.get("QUERY_FILES_DIR", ""),
                    placeholder="/home/user/RP500-Client/query_files"
                )
                query_offload_dir = gr.Textbox(
                    label="Query Offload Directory", 
                    value=client_settings.get("QUERY_OFFLOAD_DIR", ""),
                    placeholder="/home/user/RP500-Client/query_offload"
                )
                wakeword_model_dir = gr.Textbox(
                    label="Wakeword Model Directory",
                    value=client_settings.get("WAKEWORD_MODEL_DIR", ""),
                    placeholder="/home/user/RP500-Client/wakewords"
                )
                wakeword_resource = gr.Textbox(
                    label="Wakeword Resource File",
                    value=client_settings.get("WAKEWORD_RESOURCE_FILE", ""),
                    placeholder="/home/user/RP500-Client/snowboy/resources/common.res"
                )
                
                paths_save_btn = gr.Button("💾 Save File Paths", variant="primary")
                paths_status = gr.Textbox(label="Status", interactive=False)
                
                def save_paths(query_dir, offload_dir, wake_dir, wake_res):
                    return config_manager.save_and_reload(
                        QUERY_FILES_DIR=query_dir,
                        QUERY_OFFLOAD_DIR=offload_dir,
                        WAKEWORD_MODEL_DIR=wake_dir,
                        WAKEWORD_RESOURCE_FILE=wake_res
                    )
                
                paths_save_btn.click(
                    save_paths,
                    inputs=[query_files_dir, query_offload_dir, wakeword_model_dir, wakeword_resource],
                    outputs=paths_status
                )
        
        # Global actions
        with gr.Row():
            gr.Markdown("### 🔄 Global Actions")
        
        with gr.Row():
            reload_btn = gr.Button("🔄 Reload Settings from File", variant="secondary")
            export_btn = gr.Button("📤 Export Current Config", variant="secondary")
            
        global_status = gr.Textbox(label="Status", interactive=False)
        config_export = gr.Code(label="Exported Configuration", language="json")
        
        def reload_settings():
            config_manager.load_current_settings()
            return "✅ Settings reloaded from file successfully!"
        
        def export_config():
            try:
                config_json = json.dumps(client_settings, indent=2, default=str)
                return "✅ Configuration exported successfully!", config_json
            except Exception as e:
                return f"❌ Error exporting config: {str(e)}", ""
        
        reload_btn.click(reload_settings, outputs=global_status)
        export_btn.click(
            export_config, 
            outputs=[global_status, config_export]
        )
    
    return interface

if __name__ == "__main__":
    # Launch the interface
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",  # Allow access from other devices on network
        server_port=7860,       # Default Gradio port
        share=False,            # Set to True if you want a public link
        debug=True
    )