#!/usr/bin/env python3

import asyncio
import time
import random
from pathlib import Path
import pygame
from communication.client_config import get_mood_color_config


class DisplayManager:
    """
    Manages visual display states and image rendering using pygame.
    
    Handles state transitions, mood-based image selection, background rotation,
    and coordination with the overall system state.
    """
    
    def __init__(self, svg_path=None, boot_img_path=None, window_size=512):
        print(f"[DisplayManager] Initializing pygame...")
        pygame.init()
        print(f"[DisplayManager] Creating window of size {window_size}x{window_size}")
        self.window_size = window_size
        self.screen = pygame.display.set_mode((window_size, window_size))
        pygame.display.set_caption("LAURA")
        print(f"[DisplayManager] Window created successfully")
        
        self.base_path = Path('/home/user/RP500-Client/images/laura')
        self.image_cache = {}
        self.current_state = 'boot'
        self.current_mood = 'casual'
        self.last_state = None
        self.last_mood = None
        self.current_image = None
        self.last_image_change = None
        self.state_entry_time = None
        self.initialized = False
        
        self.moods = [
            "amused", "annoyed", "caring", "casual", "cheerful", "concerned", 
            "confused", "curious", "disappointed", "embarrassed", "excited", 
            "frustrated", "interested", "sassy", "scared", "surprised", 
            "suspicious", "thoughtful"
        ]
        
        self.states = {
            'listening': str(self.base_path / 'listening'),
            'idle': str(self.base_path / 'idle'),
            'sleep': str(self.base_path / 'sleep'),
            'speaking': str(self.base_path / 'speaking'),
            'thinking': str(self.base_path / 'thinking'),
            'wake': str(self.base_path / 'wake'),
            'boot': str(self.base_path / 'boot'),  # Changed from 'booting' to 'boot'
            'system': str(self.base_path / 'system'),  # Added
            'tool_use': str(self.base_path / 'tool_use'),  # Added
            'notification': str(self.base_path / 'speaking'),  # Maps to speaking images but separate state
            'code': str(self.base_path / 'code'),  # Code mode for Claude Code interaction
            'error': str(self.base_path / 'error'),  # Error state for connection/system errors
            'disconnected': str(self.base_path / 'disconnected'),  # Disconnected state
        }
        
        self.load_image_directories()
        
        # Load boot image if provided
        self.boot_img = None
        if boot_img_path:
            try:
                boot_img_loaded = pygame.image.load(boot_img_path).convert_alpha()
                self.boot_img = pygame.transform.scale(boot_img_loaded, (self.window_size, self.window_size))
            except Exception as e:
                print(f"[DisplayManager WARN] Could not load boot image: {e}")
        
        # Initial display setup
        if 'boot' in self.image_cache:
            self.current_image = random.choice(self.image_cache['boot'])
            self.screen.blit(self.current_image, (0, 0))
            pygame.display.flip()
            self.last_image_change = time.time()
            self.state_entry_time = time.time()
            self.initialized = True
        else:
            # Fallback to solid color if no images
            self.screen.fill((25, 25, 25))
            pygame.display.flip()
            self.last_image_change = time.time()  # Initialize this to prevent None errors
            self.initialized = True
        
        
    def load_image_directories(self):
        """Load images from directory structure"""
        print("\nLoading image directories...")
        for state, directory in self.states.items():
            print(f"Checking state: {state}")
            
            if state == 'speaking':
                self.image_cache[state] = {}
                for mood in self.moods:
                    mood_path = Path(directory) / mood
                    if mood_path.exists():
                        png_files = list(mood_path.glob('*.png'))
                        if png_files:
                            self.image_cache[state][mood] = [
                                pygame.transform.scale(pygame.image.load(str(img)), (self.window_size, self.window_size))
                                for img in png_files
                            ]
            else:
                state_path = Path(directory)
                if state_path.exists():
                    png_files = list(state_path.glob('*.png'))
                    if png_files:
                        self.image_cache[state] = [
                            pygame.transform.scale(pygame.image.load(str(img)), (self.window_size, self.window_size))
                            for img in png_files
                        ]

    async def update_display(self, state, mood=None, text=None):
        """Update display state immediately"""
        while not self.initialized:
            await asyncio.sleep(0.1)
            
        if mood is None:
            mood = self.current_mood

        # Map mood using client config
        mapped_mood_config = get_mood_color_config(mood)
        mapped_mood = mapped_mood_config.get('name', 'casual')
        
        try:
            self.last_state = self.current_state
            self.current_state = state
            self.current_mood = mapped_mood
            
            # Handle image selection
            if state == 'booting' and self.boot_img:
                self.current_image = self.boot_img
            elif state in ['speaking', 'notification']:
                # Both speaking and notification states use speaking images with mood
                image_state = 'speaking'  # Always use speaking images
                if mapped_mood not in self.image_cache[image_state]:
                    mapped_mood = 'casual'  # Default fallback
                if mapped_mood in self.image_cache[image_state]:
                    self.current_image = random.choice(self.image_cache[image_state][mapped_mood])
                else:
                    # Fallback to any available speaking image
                    available_moods = list(self.image_cache[image_state].keys())
                    if available_moods:
                        self.current_image = random.choice(self.image_cache[image_state][available_moods[0]])
            elif state in self.image_cache:
                self.current_image = random.choice(self.image_cache[state])
            else:
                print(f"Warning: No images for state '{state}', using fallback")
                # Use a fallback color based on state
                state_colors = {
                    'error': (150, 50, 50),
                    'disconnected': (50, 50, 50),
                    'booting': (100, 100, 150)
                }
                color = state_colors.get(state, (25, 25, 25))
                self.screen.fill(color)
                pygame.display.flip()
                return
                
            # Display the image
            if self.current_image:
                self.screen.blit(self.current_image, (0, 0))
                pygame.display.flip()
            
            # Update rotation timer for idle/sleep states
            if state in ['idle', 'sleep']:
                self.last_image_change = time.time()
                self.state_entry_time = time.time()
                
            print(f"Display updated - State: {self.current_state}, Mood: {self.current_mood}")
                
        except Exception as e:
            print(f"Error updating display: {e}")

    async def rotate_background(self):
        """Background image rotation for idle/sleep states"""
        while not self.initialized:
            await asyncio.sleep(0.1)
        
        print("Background rotation task started")
        
        while True:
            try:
                current_time = time.time()
                
                if self.current_state in ['idle', 'sleep'] and self.last_image_change is not None:
                    time_diff = current_time - self.last_image_change
                    
                    if time_diff >= 15:  # Rotate every 15 seconds
                        available_images = self.image_cache.get(self.current_state, [])
                        if len(available_images) > 1:
                            current_options = [img for img in available_images if img != self.current_image]
                            if current_options:
                                new_image = random.choice(current_options)
                                self.current_image = new_image
                                self.screen.blit(self.current_image, (0, 0))
                                pygame.display.flip()
                                self.last_image_change = current_time
                
            except Exception as e:
                print(f"Error in rotate_background: {e}")
        
            await asyncio.sleep(5)  # Check every 5 seconds
            
    def pygame_to_pil(self, surface):
        """Convert pygame surface to PIL Image"""
        try:
            # Convert pygame surface to string
            string_image = pygame.image.tostring(surface, 'RGB')
            # Create PIL image
            pil_image = Image.frombytes('RGB', surface.get_size(), string_image)
            return pil_image
        except Exception as e:
            print(f"Error converting pygame to PIL: {e}")
            # Return black image as fallback
            return Image.new('RGB', (self.window_size, self.window_size), (0, 0, 0))
    
    def get_current_web_image(self):
        """Get current display image for web interface"""
        if self.current_image:
            return self.pygame_to_pil(self.current_image)
        else:
            # Return black image as fallback
            return Image.new('RGB', (self.window_size, self.window_size), (0, 0, 0))
    
    def create_web_interface(self):
        """Create Gradio web interface"""
        with gr.Blocks(title="LAURA Display") as interface:
            gr.Markdown("# 🎧 LAURA Display")
            
            # Display image
            image_display = gr.Image(
                value=self.get_current_web_image(),
                height=400,
                width=400,
                interactive=False,
                show_label=False
            )
            
            # State info
            state_info = gr.Textbox(
                value=f"State: {self.current_state} | Mood: {self.current_mood}",
                label="Current State",
                interactive=False
            )
            
            # Auto-refresh display every 2 seconds
            interface.load(
                lambda: [self.get_current_web_image(), f"State: {self.current_state} | Mood: {self.current_mood}"],
                outputs=[image_display, state_info],
                every=2
            )
        
        return interface
    
    def start_web_interface(self):
        """Start web interface in separate thread"""
        def run_web():
            try:
                self.web_interface = self.create_web_interface()
                print("[DisplayManager] Starting web interface on http://localhost:7860")
                self.web_interface.launch(
                    server_name="0.0.0.0",
                    server_port=7860,
                    share=False,
                    quiet=True,
                    inbrowser=True  # Auto-open browser
                )
            except Exception as e:
                print(f"[DisplayManager] Web interface error: {e}")
        
        self.web_thread = threading.Thread(target=run_web, daemon=True)
        self.web_thread.start()
    
    def cleanup(self):
        """Clean up pygame resources"""
        pygame.quit()