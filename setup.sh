#!/bin/bash

echo "Setting up PropEngine KB Backend..."

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "Setup complete! To run the backend:"
echo "1. source venv/bin/activate"
echo "2. python main.py"
