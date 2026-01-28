#!/bin/bash
# Start Audiobook Server
# This script activates the virtual environment and starts the server

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start server
cd server
python3 audiobook_server.py --host 0.0.0.0 --port 8000
