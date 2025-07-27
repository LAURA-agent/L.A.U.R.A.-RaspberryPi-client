#!/usr/bin/env python3
"""
List available ElevenLabs voices and find the names for configured voice IDs
"""

import httpx
import json
from pathlib import Path

# Import the API key
try:
    from communication.client_secret import ELEVENLABS_API_KEY
except ImportError:
    import os
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

def list_voices():
    """Fetch all available voices from ElevenLabs API"""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    response = httpx.get(
        "https://api.elevenlabs.io/v1/voices",
        headers=headers
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching voices: {response.status_code}")
        return None

def main():
    # Known voice IDs from config
    known_ids = {
        "laura": "qEwI395unGwWV1dn3Y65",
        "max": "uY96J30mUhYUIymmD5cu"
    }
    
    print("Fetching ElevenLabs voices...")
    voices_data = list_voices()
    
    if not voices_data:
        return
    
    voices = voices_data.get("voices", [])
    
    print(f"\nFound {len(voices)} voices\n")
    
    # Find names for our configured voices
    print("=== Configured Voice IDs ===")
    for persona, voice_id in known_ids.items():
        found = False
        for voice in voices:
            if voice["voice_id"] == voice_id:
                print(f"{persona}: {voice['name']} (ID: {voice_id})")
                found = True
                break
        if not found:
            print(f"{persona}: Voice ID {voice_id} not found!")
    
    print("\n=== All Available Voices ===")
    for voice in sorted(voices, key=lambda x: x['name']):
        labels = voice.get('labels', {})
        category = voice.get('category', 'unknown')
        print(f"- {voice['name']} (ID: {voice['voice_id']}) - {category}")
        if labels:
            print(f"  Labels: {', '.join(f'{k}={v}' for k, v in labels.items())}")

if __name__ == "__main__":
    main()