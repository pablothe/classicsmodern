#!/bin/bash
# Start Audiobook Server
# This script activates the virtual environment and starts the server

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set PYTHONPATH to project root so lib.* imports work
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Start server using venv Python explicitly
# This ensures subprocess.run() commands use the venv Python with kokoro-onnx installed
cd server
../venv/bin/python3 audiobook_server.py --host 0.0.0.0 --port 8000
