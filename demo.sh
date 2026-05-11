#!/bin/bash

# Exit on error
set -e

echo "Setting up UnitedMasters Demo Environment..."

# Create demo data directory if it doesn't exist
mkdir -p demo_data
echo "Created ./demo_data directory for testing input."

# Build and start the container
echo "Building and starting Docker containers..."
docker compose up --build -d

echo ""
echo "Demo is now running!"
echo "Access the Web UI at: http://127.0.0.1:5000"
echo "You can place audio files in the './demo_data' folder on your host machine."
echo "In the Web UI, use '/app/demo_data' as the input directory path."
echo ""
echo "To stop the demo, run: docker compose down"
