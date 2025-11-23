import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from livekit.agents import cli, WorkerOptions
from app.agents.voice_agent import entrypoint

if __name__ == "__main__":
    # Auto-detect production environment (Railway, Cloud Run, etc.)
    is_production = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("LIVEKIT_URL")
    
    # Default to appropriate mode if no arguments provided
    if len(sys.argv) == 1:
        if is_production:
            print("🚀 Production environment detected, using 'start' mode...")
            sys.argv.append("start")
        else:
            print("ℹ️  No command provided, defaulting to 'dev' mode...")
            sys.argv.append("dev")

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
