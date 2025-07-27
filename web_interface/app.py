#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import json
import os
import time
from pathlib import Path
import threading
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'laura-control-center-2025'
socketio = SocketIO(app, cors_allowed_origins="*")

# Paths
BASE_DIR = Path("/home/user/RP500-Client")
CONFIG_PATH = BASE_DIR / "client_config.json"
CLAUDE_MD_PATH = BASE_DIR / "CLAUDE.md"
CURRENT_IMAGE_PATH = BASE_DIR / "current_display.png"

# Load initial config
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    config = load_config()
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({"status": "success"})

@app.route('/api/claude_md', methods=['GET'])
def get_claude_md():
    try:
        with open(CLAUDE_MD_PATH, 'r') as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/claude_md', methods=['POST'])
def update_claude_md():
    try:
        data = request.json
        content = data.get('content', '')
        with open(CLAUDE_MD_PATH, 'w') as f:
            f.write(content)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/personas', methods=['GET'])
def get_personas():
    try:
        config = load_config()
        personas = config.get('persona_voice_configs', {})
        return jsonify({"personas": personas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/personas', methods=['POST'])
def add_persona():
    try:
        data = request.json
        persona_name = data.get('name', '').lower().strip()
        voice_id = data.get('voice_id', '').strip()
        voice_name = data.get('voice_name', '').strip()
        
        # Validate inputs
        if not persona_name or not voice_id:
            return jsonify({"error": "Persona name and voice ID are required"}), 400
        
        # Validate voice ID format (ElevenLabs voice IDs are typically 20 characters)
        if len(voice_id) < 15 or not voice_id.replace('-', '').isalnum():
            return jsonify({"error": "Invalid voice ID format"}), 400
        
        # Load current config
        config = load_config()
        personas = config.get('persona_voice_configs', {})
        
        # Check for duplicates
        if persona_name in personas:
            return jsonify({"error": f"Persona '{persona_name}' already exists"}), 400
        
        # Create new persona config
        new_persona = {
            "elevenlabs": {
                "voice_name_or_id": voice_id,
                "model": "eleven_flash_v2_5"
            },
            "cartesia": {
                "voice_id": "78f71eb3-187f-48b4-a763-952f2f4f838a",  # Default
                "model": "sonic-en"
            },
            "piper": {
                "model_path": "/home/user/RP500-Client/piper_models/en_US-ljspeech-low.onnx",
                "voice_name": "ljspeech"
            }
        }
        
        # Add display name if provided
        if voice_name:
            new_persona["display_name"] = voice_name
        
        # Add to config
        personas[persona_name] = new_persona
        config['persona_voice_configs'] = personas
        
        # Save updated config
        save_config(config)
        
        return jsonify({"status": "success", "persona": persona_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/personas/<persona_name>', methods=['DELETE'])
def delete_persona(persona_name):
    try:
        # Prevent deleting essential personas
        if persona_name.lower() in ['laura', 'client_default']:
            return jsonify({"error": "Cannot delete essential personas"}), 400
        
        config = load_config()
        personas = config.get('persona_voice_configs', {})
        
        if persona_name not in personas:
            return jsonify({"error": f"Persona '{persona_name}' not found"}), 404
        
        # Remove persona
        del personas[persona_name]
        config['persona_voice_configs'] = personas
        
        # Save updated config
        save_config(config)
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/current_image')
def get_current_image():
    import random
    
    # Pick a random image from idle folder
    idle_folder = BASE_DIR / "images" / "laura" / "idle"
    if idle_folder.exists():
        images = list(idle_folder.glob("*.png"))
        if images:
            random_image = random.choice(images)
            return send_file(random_image, mimetype='image/png')
    
    # Generate a simple placeholder if no images found
    import io
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.new('RGB', (200, 200), color='#1a1a1a')
    draw = ImageDraw.Draw(img)
    # Simple text placeholder
    draw.text((50, 90), "LAURA", fill='#666666')
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'data': 'Connected to LAURA Control Center'})

@socketio.on('update_status')
def handle_status_update(data):
    # Broadcast status updates to all connected clients
    emit('status_changed', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=7860, debug=True)