"""Configuration management for Jarvis"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # Gmail OAuth credentials
        self.gmail_client_id: str = os.getenv("GMAIL_CLIENT_ID", "")
        self.gmail_client_secret: str = os.getenv("GMAIL_CLIENT_SECRET", "")
        self.gmail_redirect_uri: str = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/gmail/callback")

        # Calendar OAuth credentials (uses same Gmail credentials)
        self.calendar_client_id: str = os.getenv("CALENDAR_CLIENT_ID", os.getenv("GMAIL_CLIENT_ID", ""))
        self.calendar_client_secret: str = os.getenv("CALENDAR_CLIENT_SECRET", os.getenv("GMAIL_CLIENT_SECRET", ""))
        self.calendar_redirect_uri: str = os.getenv("CALENDAR_REDIRECT_URI", "http://localhost:8000/calendar/callback")

        # OpenAI
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

        # Mem0
        self.mem0_api_key: str = os.getenv("MEM0_API_KEY", "")

        # Tavily Search
        self.tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

        # LiveKit
        self.livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "")
        self.livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")
        self.livekit_url: str = os.getenv("LIVEKIT_URL", "")

        # User Preferences
        self.user_timezone: str = os.getenv("USER_TIMEZONE", "America/Los_Angeles")

        # Server & Paths
        self.auth_server_url: str = os.getenv("AUTH_SERVER_URL", "http://localhost:8000")
        self.data_dir: str = os.getenv("DATA_DIR", "data")

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get singleton settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
