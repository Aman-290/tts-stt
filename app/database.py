"""Database manager for Jarvis backend"""
import sqlite3
import json
import os
from typing import Optional, Dict, Any
from app.utils.logger import get_logger

logger = get_logger("database")

class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = "data/jarvis.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()
        
    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def _init_db(self):
        """Initialize database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create user_tokens table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_tokens (
                        user_id TEXT PRIMARY KEY,
                        gmail_token TEXT,
                        calendar_token TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def get_token(self, user_id: str, service: str) -> Optional[Dict[str, Any]]:
        """Get token for a user and service
        
        Args:
            user_id: User identifier
            service: 'gmail' or 'calendar'
            
        Returns:
            Token dictionary or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                column = f"{service}_token"
                cursor.execute(f"SELECT {column} FROM user_tokens WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row and row[0]:
                    return json.loads(row[0])
                return None
        except Exception as e:
            logger.error(f"Error getting token for {user_id}/{service}: {e}")
            return None

    def set_token(self, user_id: str, service: str, token: Dict[str, Any]):
        """Set token for a user and service
        
        Args:
            user_id: User identifier
            service: 'gmail' or 'calendar'
            token: Token dictionary
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                token_json = json.dumps(token)
                column = f"{service}_token"
                
                # Check if user exists
                cursor.execute("SELECT 1 FROM user_tokens WHERE user_id = ?", (user_id,))
                exists = cursor.fetchone()
                
                if exists:
                    cursor.execute(f"""
                        UPDATE user_tokens 
                        SET {column} = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    """, (token_json, user_id))
                else:
                    cursor.execute(f"""
                        INSERT INTO user_tokens (user_id, {column}) 
                        VALUES (?, ?)
                    """, (user_id, token_json))
                    
                conn.commit()
                logger.info(f"Saved {service} token for user {user_id}")
        except Exception as e:
            logger.error(f"Error setting token for {user_id}/{service}: {e}")
            raise

    def remove_token(self, user_id: str, service: str):
        """Remove token for a user and service"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                column = f"{service}_token"
                
                cursor.execute(f"""
                    UPDATE user_tokens 
                    SET {column} = NULL, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                logger.info(f"Removed {service} token for user {user_id}")
        except Exception as e:
            logger.error(f"Error removing token for {user_id}/{service}: {e}")

    def has_token(self, user_id: str, service: str) -> bool:
        """Check if user has a token for a service"""
        token = self.get_token(user_id, service)
        return token is not None
