from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Tuple
import json
from google.oauth2.credentials import Credentials

from app.services.gmail_service import GmailService
from app.utils.token_storage import TokenStorage
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

_gmail_service: Optional[GmailService] = None
_token_storage: Optional[TokenStorage] = None

def get_token_storage() -> TokenStorage:
    """Get or create TokenStorage instance"""
    global _token_storage
    if _token_storage is None:
        _token_storage = TokenStorage()
    return _token_storage

def get_gmail_service() -> GmailService:
    """Get or create GmailService instance"""
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service

def get_user_credentials(user_id: str) -> Tuple[Credentials, str]:
    """Shared helper to get credentials for a user
    
    Returns:
        Tuple of (Credentials, token_json)
    
    Raises:
        HTTPException: If user is not connected
    """
    token_storage = get_token_storage()
    
    if not token_storage.has_token(user_id):
        raise HTTPException(status_code=401, detail="Gmail not connected. Please authorize first.")
    
    gmail = get_gmail_service()
    token_json = token_storage.get_token(user_id)
    credentials = gmail.get_credentials_from_token(token_json)
    
    return credentials, token_json

class GmailSearchRequest(BaseModel):
    query: str
    user_id: str
    access_token: Optional[str] = None

class GmailAuthResponse(BaseModel):
    auth_url: str

class GmailCallbackRequest(BaseModel):
    code: str
    state: str
    user_id: str

@router.get("/auth-url")
async def get_auth_url(user_id: str = Query(..., description="User ID for token storage")):
    """Get Gmail OAuth authorization URL"""
    try:
        auth_url = get_gmail_service().get_authorization_url(user_id)
        logger.info(f"Gmail auth URL generated for user {user_id}")
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating Gmail auth URL for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

@router.post("/callback")
async def gmail_callback(request: GmailCallbackRequest):
    """Handle Gmail OAuth callback and store tokens with state validation"""
    try:
        token_storage = get_token_storage()

        # Check if already connected (prevent duplicate processing)
        if token_storage.has_token(request.user_id):
            return {
                "success": True,
                "message": "Gmail already connected"
            }

        gmail = get_gmail_service()
        # Pass state and user_id for CSRF protection
        token_json = await gmail.handle_oauth_callback(request.code, request.state, request.user_id)

        # Store token for this user (persists to file)
        token_storage.set_token(request.user_id, token_json)

        logger.info(f"Gmail OAuth callback successful for user {request.user_id}")
        return {
            "success": True,
            "message": "Gmail connected successfully"
        }
    except ValueError as e:
        # Handle state validation errors
        logger.error(f"Gmail OAuth callback validation error for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Gmail OAuth callback error for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="OAuth callback failed")

@router.get("/status")
async def gmail_status(user_id: str = Query(...)):
    """Check if Gmail is connected for this user and validate token"""
    token_storage = get_token_storage()

    # Check if token exists
    if not token_storage.has_token(user_id):
        return {
            "connected": False,
            "user_id": user_id,
            "message": "Not connected"
        }

    # Validate the token
    try:
        # Use shared helper which handles refresh automatically
        credentials, token_json = get_user_credentials(user_id)
        
        # Validate credentials (refresh already handled by get_user_credentials)
        gmail = get_gmail_service()
        is_valid = gmail.validate_credentials(credentials)

        if not is_valid:
            # Invalid token - remove it
            token_storage.remove_token(user_id)
            logger.warning(f"Removed invalid Gmail token for user {user_id}")
            return {
                "connected": False,
                "user_id": user_id,
                "message": "Token invalid or expired. Please reconnect."
            }

        # If credentials were refreshed, update stored token
        original_token_data = json.loads(token_json)
        if credentials.token != original_token_data.get("token"):
            updated_token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes
            }
            token_storage.set_token(user_id, json.dumps(updated_token_data))
            logger.info(f"Updated refreshed token for user {user_id}")

        return {
            "connected": True,
            "user_id": user_id,
            "message": "Connected and validated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating Gmail status for user {user_id}: {e}", exc_info=True)
        return {
            "connected": False,
            "user_id": user_id,
            "message": f"Validation error: {str(e)}"
        }

@router.post("/search")
async def search_gmail(request: GmailSearchRequest):
    """Search Gmail inbox"""
    try:
        # Use shared helper for credentials
        credentials, _ = get_user_credentials(request.user_id)
        
        gmail = get_gmail_service()
        query = await gmail.parse_search_query(request.query)
        emails = await gmail.search_emails(credentials, query, max_results=5)

        if not emails:
            return {
                "count": 0,
                "emails": [],
                "message": "No emails found matching your query."
            }

        summary = f"Found {len(emails)} email(s). "
        summary += f"Most recent from {emails[0]['from']} about '{emails[0]['subject']}'"

        logger.info(f"Gmail search successful for user {request.user_id}: found {len(emails)} emails")
        return {
            "count": len(emails),
            "emails": emails,
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail search error for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gmail search failed")

@router.get("/email/{email_id}")
async def get_email_content(email_id: str, user_id: str = Query(...)):
    """Get full email content"""
    try:
        # Use shared helper for credentials
        credentials, _ = get_user_credentials(user_id)
        
        gmail = get_gmail_service()
        content = await gmail.get_email_content(credentials, email_id)

        if not content:
            raise HTTPException(status_code=404, detail="Email content not found")

        logger.debug(f"Email content retrieved for user {user_id}, message {email_id}")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email content for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve email content")

@router.delete("/disconnect")
async def disconnect_gmail(user_id: str = Query(...)):
    """Disconnect Gmail by removing stored tokens"""
    try:
        token_storage = get_token_storage()
        
        if not token_storage.has_token(user_id):
            return {
                "success": True,
                "message": "Gmail was not connected"
            }
        
        # Remove the token
        token_storage.remove_token(user_id)
        
        logger.info(f"Gmail disconnected for user {user_id}")
        return {
            "success": True,
            "message": "Gmail disconnected successfully"
        }
    except Exception as e:
        logger.error(f"Error disconnecting Gmail for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to disconnect Gmail")

