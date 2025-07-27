#!/usr/bin/env python3

import gradio as gr
from pathlib import Path
from PIL import Image
import random
import json

# Load client settings
try:
    with open('/home/user/RP500-Client/client_settings.json', 'r') as f:
        client_settings = json.load(f)
except:
    client_settings = {}

class WorkingDisplay:
    def __init__(self):
        self.current_state = 'boot'
        self.current_mood = 'casual'
        self.base_path = Path('/home/user/RP500-Client/images/laura')
        self.current_image = self.load_state_image('boot')
    
    def load_state_image(self, state, mood='casual'):
        """Load an image for the given state"""
        try:
            state_path = self.base_path / state
            
            if state == 'speaking' and mood:
                mood_path = state_path / mood
                if mood_path.exists():
                    images = list(mood_path.glob('*.png'))
                    if images:
                        return Image.open(random.choice(images)).resize((300, 300))
            
            if state_path.exists():
                images = list(state_path.glob('*.png'))
                if images:
                    return Image.open(random.choice(images)).resize((300, 300))
            
            # Fallback to boot image
            boot_path = self.base_path / 'boot'
            if boot_path.exists():
                images = list(boot_path.glob('*.png'))
                if images:
                    return Image.open(images[0]).resize((300, 300))
        
        except Exception as e:
            print(f"Error loading image: {e}")
        
        # Ultimate fallback - create colored square
        import numpy as np
        img_array = np.full((300, 300, 3), (100, 150, 200), dtype=np.uint8)
        return Image.fromarray(img_array)
    
    def update_state(self, state, mood='casual'):
        """Update current state and return new image"""
        self.current_state = state
        self.current_mood = mood
        self.current_image = self.load_state_image(state, mood)
        return self.current_image
    
    def cycle_test_states(self):
        """Cycle through test states"""
        states = ['boot', 'listening', 'thinking', 'speaking', 'idle', 'wake']
        moods = ['casual', 'excited', 'curious', 'amused', 'thoughtful']
        
        state = random.choice(states)
        mood = random.choice(moods) if state == 'speaking' else 'casual'
        
        return self.update_state(state, mood)

# Create display manager
display = WorkingDisplay()

# Create simple interface
with gr.Blocks(title="LAURA", css=".container { max-width: 800px; margin: 0 auto; }") as interface:
    gr.Markdown("# 🎧 LAURA Display")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Display image
            display_image = gr.Image(
                value=display.current_image,
                height=300,
                width=300,
                interactive=False,
                show_label=False,
                container=False
            )
            
            # Current state info
            state_info = gr.Markdown(f"**State:** {display.current_state} | **Mood:** {display.current_mood}")
        
        with gr.Column(scale=1):
            gr.Markdown("### Controls")
            
            # Test button
            test_btn = gr.Button("🔄 Test Display", variant="primary", size="lg")
            
            # Manual state selection
            with gr.Row():
                state_dropdown = gr.Dropdown(
                    choices=['boot', 'listening', 'thinking', 'speaking', 'idle', 'wake', 'sleep', 'code', 'error'],
                    value='boot',
                    label="State"
                )
                mood_dropdown = gr.Dropdown(
                    choices=['casual', 'excited', 'curious', 'amused', 'thoughtful', 'concerned', 'confused'],
                    value='casual',
                    label="Mood"
                )
            
            update_btn = gr.Button("Update Display", variant="secondary")
            
            # System info
            gr.Markdown("### System Status")
            system_info = gr.JSON({
                "Server URL": client_settings.get("SERVER_URL", "Unknown"),
                "Device ID": client_settings.get("DEVICE_ID", "Unknown"),
                "TTS Mode": client_settings.get("tts_mode", "Unknown")
            })
    
    # Event handlers
    def handle_test():
        new_image = display.cycle_test_states()
        state_text = f"**State:** {display.current_state} | **Mood:** {display.current_mood}"
        return new_image, state_text
    
    def handle_update(state, mood):
        new_image = display.update_state(state, mood)
        state_text = f"**State:** {display.current_state} | **Mood:** {display.current_mood}"
        return new_image, state_text
    
    # Wire up events
    test_btn.click(
        handle_test,
        outputs=[display_image, state_info]
    )
    
    update_btn.click(
        handle_update,
        inputs=[state_dropdown, mood_dropdown],
        outputs=[display_image, state_info]
    )

if __name__ == "__main__":
    print("🎧 Starting LAURA Working Display...")
    interface.launch(
        server_name="127.0.0.1",
        server_port=7862,
        share=False,
        inbrowser=False
    )