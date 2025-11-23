"""Lightweight OAuth server for Gmail and Calendar authentication"""
import uvicorn
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.services.gmail_service import GmailService
from app.services.calendar_service import CalendarService
from app.utils.token_storage import TokenStorage
from app.utils.logger import get_logger

logger = get_logger("auth_server")

app = FastAPI(title="Jarvis OAuth Server")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
gmail_service = GmailService()
calendar_service = CalendarService()
token_storage = TokenStorage()

FRONTEND_URL = "http://localhost:3000"

@app.get("/")
async def home():
    """Home page"""
    return {"status": "running", "message": "Jarvis OAuth Server"}

@app.get("/auth/status")
async def check_status(user_id: str = Query(...)):
    """Check connection status for all services"""
    return {
        "gmail": token_storage.has_token(user_id, "gmail"),
        "calendar": token_storage.has_token(user_id, "calendar")
    }

# ============================================================================
# Gmail Routes
# ============================================================================

@app.get("/gmail/auth")
async def start_gmail_auth(
    user_id: str = Query(...),
    redirect_uri: str = Query(default=None)
):
    """Start Gmail OAuth flow"""
    try:
        # Generate OAuth URL
        auth_url = gmail_service.get_authorization_url(user_id)
        logger.info(f"Generated Gmail OAuth URL for user: {user_id}")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error starting auth for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start authentication")

@app.get("/gmail/callback")
async def gmail_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    user_id: str = Query(None)
):
    """Handle Gmail OAuth callback"""
    try:
        # If user_id is missing (redirect from Google), try to find it from state
        if not user_id:
            user_id = gmail_service.get_user_id_by_state(state)
            if not user_id:
                logger.error(f"Could not find user_id for state: {state}")
                return RedirectResponse(url=f"{FRONTEND_URL}?status=error&service=gmail&error=session_expired")

        token_json = await gmail_service.handle_oauth_callback(code, state, user_id)
        token_storage.set_token(user_id, "gmail", token_json)
        logger.info(f"✅ Gmail connected successfully for user: {user_id}")
        
        # Redirect to frontend
        return RedirectResponse(url=f"{FRONTEND_URL}?status=connected&service=gmail")
    except Exception as e:
        logger.error(f"Gmail OAuth callback error: {e}", exc_info=True)
        return RedirectResponse(url=f"{FRONTEND_URL}?status=error&service=gmail&error={str(e)}")

@app.delete("/gmail/disconnect")
async def disconnect_gmail(user_id: str = Query(...)):
    """Disconnect Gmail"""
    token_storage.remove_token(user_id, "gmail")
    return {"success": True, "message": "Gmail disconnected"}

# ============================================================================
# Calendar Routes
# ============================================================================

@app.get("/calendar/auth")
async def start_calendar_auth(
    user_id: str = Query(...),
    redirect_uri: str = Query(default=None)
):
    """Start Calendar OAuth flow"""
    try:
        auth_url = calendar_service.get_authorization_url(user_id)
        logger.info(f"Generated Calendar OAuth URL for user: {user_id}")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error starting calendar auth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start authentication")

@app.get("/calendar/callback")
async def calendar_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    user_id: str = Query(None)
):
    """Handle Calendar OAuth callback"""
    try:
        # If user_id is missing, try to find it from state
        if not user_id:
            user_id = calendar_service.get_user_id_by_state(state)
            if not user_id:
                logger.error(f"Could not find user_id for state: {state}")
                return RedirectResponse(url=f"{FRONTEND_URL}?status=error&service=calendar&error=session_expired")

        token_json = await calendar_service.handle_oauth_callback(code, state, user_id)
        token_storage.set_token(user_id, "calendar", token_json)
        logger.info(f"✅ Calendar connected for user: {user_id}")
        
        return RedirectResponse(url=f"{FRONTEND_URL}?status=connected&service=calendar")
    except Exception as e:
        logger.error(f"Calendar OAuth callback error: {e}", exc_info=True)
        return RedirectResponse(url=f"{FRONTEND_URL}?status=error&service=calendar&error={str(e)}")

@app.delete("/calendar/disconnect")
async def disconnect_calendar(user_id: str = Query(...)):
    """Disconnect Calendar"""
    token_storage.remove_token(user_id, "calendar")
    return {"success": True, "message": "Calendar disconnected"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
