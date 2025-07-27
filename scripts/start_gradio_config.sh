#!/bin/bash

# RP500-Client Gradio Configuration Interface Startup Script
# This script starts the web-based configuration interface

echo "$(date): Starting RP500-Client Configuration Interface..."

# Navigate to the RP500-Client directory
cd /home/user/RP500-Client

# Activate the virtual environment
source venv/bin/activate

# Start the Gradio configuration interface
echo "$(date): Launching Gradio configuration interface on port 7860..."
python3 gradio_config_interface.py

echo "$(date): Gradio configuration interface has exited."