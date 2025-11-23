import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from livekit.agents import cli, WorkerOptions
from app.agents.voice_agent import entrypoint

if __name__ == "__main__":
    # Default to 'dev' command if no arguments provided
    if len(sys.argv) == 1:
        print("ℹ️  No command provided, defaulting to 'dev' mode...")
        sys.argv.append("dev")

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
