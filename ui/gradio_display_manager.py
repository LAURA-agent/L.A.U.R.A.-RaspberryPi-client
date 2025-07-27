#!/usr/bin/env python3

import asyncio
import time
import random
import io
import base64
from pathlib import Path
from typing import Optional, Callable
import pygame
from PIL import Image
import numpy as np
from communication.client_config import get_mood_color_config


class GradioDisplayManager:
    """
    Web-compatible version of DisplayManager that renders pygame surfaces 
    off-screen and converts them to PIL Images for Gradio display.
    
    Maintains all the functionality of the original DisplayManager while
    providing web-compatible output for the unified Gradio interface.
    """
    
    def __init__(self, svg_path=None, boot_img_path=None, window_size=512, update_callback=None):
        """
        Initialize the web-compatible display manager.
        
        Args:
            svg_path: Path to SVG file (legacy support)
            boot_img_path: Path to boot image
            window_size: Size of the display (default: 512x512)
            update_callback: Callback function to notify Gradio of updates
        """
        print(f"[GradioDisplayManager] Initializing headless pygame...")
        
        # Initialize pygame in headless mode
        import os
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.init()
        
        print(f"[GradioDisplayManager] Creating off-screen surface {window_size}x{window_size}")
        self.window_size = window_size
        self.surface = pygame.Surface((window_size, window_size))
        print(f"[GradioDisplayManager] Off-screen surface created successfully")
        
        # Display state management
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
        
        # Gradio integration
        self.update_callback = update_callback
        self.last_pil_image = None
        
        # Available moods for speaking state
        self.moods = [
            "amused", "annoyed", "caring", "casual", "cheerful", "concerned", 
            "confused", "curious", "disappointed", "embarrassed", "excited", 
            "frustrated", "interested", "sassy", "scared", "surprised", 
            "suspicious", "thoughtful"
        ]
        
        # State directory mapping
        self.states = {
            'listening': str(self.base_path / 'listening'),
            'idle': str(self.base_path / 'idle'),
            'sleep': str(self.base_path / 'sleep'),
            'speaking': str(self.base_path / 'speaking'),
            'thinking': str(self.base_path / 'thinking'),
            'wake': str(self.base_path / 'wake'),
            'boot': str(self.base_path / 'boot'),
            'system': str(self.base_path / 'system'),
            'tool_use': str(self.base_path / 'tool_use'),
            'notification': str(self.base_path / 'speaking'),  # Maps to speaking images
            'code': str(self.base_path / 'code'),
            'error': str(self.base_path / 'error'),
            'disconnected': str(self.base_path / 'disconnected'),
        }
        
        # Load all images into cache
        self.load_image_directories()
        
        # Initialize with boot image if available
        if boot_img_path and Path(boot_img_path).exists():
            try:
                boot_image = pygame.image.load(boot_img_path)
                self.current_image = pygame.transform.scale(boot_image, (window_size, window_size))
                self._render_current_frame()
            except Exception as e:
                print(f"[GradioDisplayManager] Warning: Could not load boot image: {e}")
        
        print(f"[GradioDisplayManager] Initialization complete")

    def load_image_directories(self):
        """Load all available images into cache for fast access"""
        print("Loading image directories...")
        
        for state_name, state_path in self.states.items():
            print(f"Checking state: {state_name}")
            state_dir = Path(state_path)
            
            if not state_dir.exists():
                print(f"Warning: Directory {state_dir} does not exist")
                continue
                
            self.image_cache[state_name] = {}
            
            # For speaking state, load mood-based subdirectories
            if state_name == 'speaking':
                for mood in self.moods:
                    mood_dir = state_dir / mood
                    if mood_dir.exists():
                        mood_images = []
                        for img_file in mood_dir.glob('*.png'):
                            try:
                                img = pygame.image.load(str(img_file))
                                img = pygame.transform.scale(img, (self.window_size, self.window_size))
                                mood_images.append(img)
                            except Exception as e:
                                print(f"Warning: Could not load {img_file}: {e}")
                        
                        if mood_images:
                            self.image_cache[state_name][mood] = mood_images
                            print(f"  Loaded {len(mood_images)} images for mood: {mood}")
            else:
                # For other states, load images directly
                state_images = []
                for img_file in state_dir.glob('*.png'):
                    try:
                        img = pygame.image.load(str(img_file))
                        img = pygame.transform.scale(img, (self.window_size, self.window_size))
                        state_images.append(img)
                    except Exception as e:
                        print(f"Warning: Could not load {img_file}: {e}")
                
                if state_images:
                    self.image_cache[state_name]['default'] = state_images
                    print(f"  Loaded {len(state_images)} images for state: {state_name}")

    def _surface_to_pil(self) -> Image.Image:
        """Convert current pygame surface to PIL Image"""
        # Convert pygame surface to numpy array
        surface_array = pygame.surfarray.array3d(self.surface)
        
        # Pygame uses (width, height, 3) format, PIL expects (height, width, 3)
        surface_array = np.transpose(surface_array, (1, 0, 2))
        
        # Convert to PIL Image
        pil_image = Image.fromarray(surface_array)
        
        return pil_image

    def _render_current_frame(self):
        """Render the current frame and update Gradio if callback is set"""
        if self.current_image:
            # Clear surface and blit current image
            self.surface.fill((0, 0, 0))  # Black background
            self.surface.blit(self.current_image, (0, 0))
        else:
            # Fallback to solid color based on mood
            color_config = get_mood_color_config(self.current_mood)
            if color_config and 'gradient_colors' in color_config:
                # Use first color from gradient as solid color
                color = color_config['gradient_colors'][0]
                self.surface.fill(color)
            else:
                # Default fallback color
                self.surface.fill((100, 100, 100))
        
        # Convert to PIL and cache
        self.last_pil_image = self._surface_to_pil()
        
        # Notify Gradio of update if callback is set
        if self.update_callback:
            try:
                self.update_callback(self.last_pil_image)
            except Exception as e:
                print(f"[GradioDisplayManager] Warning: Update callback failed: {e}")

    def get_current_image(self) -> Optional[Image.Image]:
        """Get the current display as a PIL Image for Gradio"""
        return self.last_pil_image

    def set_update_callback(self, callback: Callable):
        """Set the callback function for notifying Gradio of updates"""
        self.update_callback = callback

    async def update_display(self, state: str, mood: Optional[str] = None, text: Optional[str] = None):
        """
        Update the display state and render new frame.
        
        Args:
            state: The new display state (e.g., 'listening', 'thinking', 'speaking')
            mood: Optional mood for the state (mainly used for 'speaking' state)
            text: Optional text (for future text overlay support)
        """
        try:
            print(f"Display updated - State: {state}, Mood: {mood or 'casual'}")
            
            # Update state tracking
            self.last_state = self.current_state
            self.last_mood = self.current_mood
            self.current_state = state
            self.current_mood = mood or 'casual'
            self.state_entry_time = time.time()
            
            # Select appropriate image
            new_image = None
            
            if state in self.image_cache:
                state_images = self.image_cache[state]
                
                # For speaking state, try to get mood-specific image
                if state == 'speaking' and mood and mood in state_images:
                    mood_images = state_images[mood]
                    if mood_images:
                        # Avoid repeating the same image
                        available_images = [img for img in mood_images if img != self.current_image]
                        if not available_images:
                            available_images = mood_images
                        new_image = random.choice(available_images)
                
                # Fallback to default images for the state
                if not new_image and 'default' in state_images:
                    default_images = state_images['default']
                    if default_images:
                        # Avoid repeating the same image
                        available_images = [img for img in default_images if img != self.current_image]
                        if not available_images:
                            available_images = default_images
                        new_image = random.choice(available_images)
            
            # If we have a new image, update display
            if new_image:
                self.current_image = new_image
                self.last_image_change = time.time()
            else:
                print(f"Warning: No images for state '{state}', using fallback")
                # Keep current image or use None for color fallback
            
            # Render the new frame
            self._render_current_frame()
            
        except Exception as e:
            print(f"[GradioDisplayManager] Error updating display: {e}")

    async def rotate_background(self):
        """
        Background task to automatically rotate images in idle/sleep states.
        Compatible with the original DisplayManager's rotation logic.
        """
        print("[GradioDisplayManager] Background rotation task started")
        
        while True:
            try:
                await asyncio.sleep(15)  # Rotate every 15 seconds
                
                # Only rotate in idle and sleep states
                if self.current_state in ['idle', 'sleep']:
                    # Check if we have images for current state
                    if (self.current_state in self.image_cache and 
                        'default' in self.image_cache[self.current_state]):
                        
                        available_images = self.image_cache[self.current_state]['default']
                        if len(available_images) > 1:
                            # Get a different image
                            new_images = [img for img in available_images if img != self.current_image]
                            if new_images:
                                self.current_image = random.choice(new_images)
                                self.last_image_change = time.time()
                                self._render_current_frame()
                                print(f"[GradioDisplayManager] Rotated background image for {self.current_state}")
                
            except asyncio.CancelledError:
                print("[GradioDisplayManager] Background rotation cancelled")
                break
            except Exception as e:
                print(f"[GradioDisplayManager] Error in background rotation: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    def cleanup(self):
        """Clean up pygame resources"""
        try:
            pygame.quit()
            print("[GradioDisplayManager] Cleanup completed")
        except Exception as e:
            print(f"[GradioDisplayManager] Warning during cleanup: {e}")

    def get_base64_image(self) -> str:
        """Get current image as base64 string for web display"""
        if self.last_pil_image:
            buffer = io.BytesIO()
            self.last_pil_image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
        return ""