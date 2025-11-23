#!/bin/bash

# Download required files
echo "📥 Downloading required files..."
python run_agent.py download-files

# Check if download was successful
if [ $? -eq 0 ]; then
    echo "✅ Files downloaded successfully"
else
    echo "❌ Failed to download files"
    exit 1
fi

# Start the agent
echo "🚀 Starting agent..."
python run_agent.py
