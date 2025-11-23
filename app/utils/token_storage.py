"""Token storage utility for OAuth tokens"""
from typing import Optional, Dict, Any
import os
from app.database import Database
from app.config import get_settings

class TokenStorage:
    """Database-backed token storage for user credentials"""

    def __init__(self):
        """Initialize token storage"""
        settings = get_settings()
        db_path = os.path.join(settings.data_dir, "jarvis.db")
        self.db = Database(db_path)

    def has_token(self, user_id: str, service: str) -> bool:
        """Check if user has a stored token for a service"""
        return self.db.has_token(user_id, service)

    def get_token(self, user_id: str, service: str) -> Optional[Dict[str, Any]]:
        """Get token for a user and service"""
        return self.db.get_token(user_id, service)

    def set_token(self, user_id: str, service: str, token: Dict[str, Any]):
        """Set token for a user and service"""
        self.db.set_token(user_id, service, token)

    def remove_token(self, user_id: str, service: str):
        """Remove token for a user and service"""
        self.db.remove_token(user_id, service)
