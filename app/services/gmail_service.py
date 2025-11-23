import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict
import json
from app.utils.logger import get_logger
from app.config import get_settings

# Relax OAuth scope validation to allow shared OAuth clients
# This allows the same OAuth client to be used for both Gmail and Calendar
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

logger = get_logger()

class GmailService:
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.compose'
    ]

    def __init__(self):
        settings = get_settings()
        self.client_id = settings.gmail_client_id
        self.client_secret = settings.gmail_client_secret
        self.redirect_uri = settings.gmail_redirect_uri
        self._oauth_states: Dict[str, str] = {}  # Store state per user for CSRF protection

    def get_user_id_by_state(self, state: str) -> Optional[str]:
        """Find user_id by OAuth state"""
        for user_id, stored_state in self._oauth_states.items():
            if stored_state == state:
                return user_id
        return None

    def get_authorization_url(self, user_id: str) -> str:
        """Get OAuth authorization URL with state for CSRF protection"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Required for refresh_token
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to get refresh_token
        )
        
        # Store state for CSRF protection
        self._oauth_states[user_id] = state
        
        logger.info(f"Generated Gmail auth URL for user {user_id} with state for CSRF protection")
        return authorization_url

    async def handle_oauth_callback(self, code: str, state: str, user_id: str) -> str:
        """Handle OAuth callback and return token JSON with state validation"""
        # Validate state for CSRF protection
        if user_id not in self._oauth_states:
            raise ValueError("OAuth state not found. Please restart the authorization flow.")
        
        if self._oauth_states[user_id] != state:
            # Remove invalid state
            del self._oauth_states[user_id]
            raise ValueError("Invalid OAuth state. Possible CSRF attack. Please restart the authorization flow.")
        
        # Remove used state
        del self._oauth_states[user_id]
        
        # Create a new flow for token exchange
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri

        # Exchange authorization code for tokens
        flow.fetch_token(code=code)

        # Get credentials and convert to JSON
        credentials = flow.credentials

        # Log refresh_token status
        if credentials.refresh_token:
            logger.info(f"Successfully obtained refresh_token for user {user_id}")
        else:
            logger.warning(f"No refresh_token received for user {user_id} - user may have already authorized before")

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }

        return json.dumps(token_data)
    
    def get_credentials_from_token(self, token: str) -> Credentials:
        """Get credentials from stored token and refresh if needed (centralized refresh logic)"""
        token_data = json.loads(token)
        credentials = Credentials.from_authorized_user_info(token_data)

        # Centralized credential refresh logic
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logger.info("Successfully refreshed expired Gmail credentials")
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}", exc_info=True)
                raise ValueError("Gmail credentials expired and could not be refreshed. Please reconnect your account.")

        return credentials

    def validate_credentials(self, credentials: Credentials) -> bool:
        """Validate credentials by checking token and scopes (no refresh - use get_credentials_from_token for that)

        Args:
            credentials: Google OAuth credentials

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if token exists
            if not credentials.token:
                logger.warning("Credentials missing token")
                return False

            # Check if required scopes are present
            if not credentials.scopes or 'https://www.googleapis.com/auth/gmail.readonly' not in credentials.scopes:
                logger.warning("Credentials missing required Gmail scopes")
                return False

            # Check if expired (but don't refresh here - that's handled by get_credentials_from_token)
            if credentials.expired:
                if credentials.refresh_token:
                    logger.warning("Credentials expired but have refresh token - should be refreshed via get_credentials_from_token")
                    return False
                else:
                    logger.warning("Credentials expired with no refresh token")
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating credentials: {e}", exc_info=True)
            return False
    
    def build_service(self, credentials: Credentials):
        """Build Gmail service from credentials"""
        return build('gmail', 'v1', credentials=credentials)
    
    async def search_emails(
        self, 
        credentials: Credentials,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """Search emails in Gmail"""
        try:
            service = self.build_service(credentials)
            
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            email_list = []
            
            for msg in messages:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = message['payload'].get('headers', [])
                from_header = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                subject_header = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                date_header = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                
                email_list.append({
                    "id": msg['id'],
                    "from": from_header,
                    "subject": subject_header,
                    "date": date_header
                })
            
            return email_list
        except HttpError as e:
            logger.error(f"Error searching Gmail: {e}", exc_info=True)
            return []
    
    async def fetch_daily_briefing(self, credentials: Credentials, max_results: int = 10) -> List[Dict]:
        """Fetch unread emails for a daily briefing"""
        try:
            # Search for unread emails in inbox
            return await self.search_emails(credentials, "is:unread in:inbox", max_results=max_results)
        except Exception as e:
            logger.error(f"Error fetching daily briefing: {e}", exc_info=True)
            return []

    async def search_attachments(self, credentials: Credentials, query: str) -> List[Dict]:
        """Search for emails with attachments"""
        try:
            # Add has:attachment to the query
            full_query = f"{query} has:attachment"
            return await self.search_emails(credentials, full_query, max_results=5)
        except Exception as e:
            logger.error(f"Error searching attachments: {e}", exc_info=True)
            return []

    async def create_draft(self, credentials: Credentials, to: str, subject: str, body: str) -> Optional[Dict]:
        """Create a draft email"""
        try:
            service = self.build_service(credentials)
            message = self.create_message(to, subject, body)
            
            draft = service.users().drafts().create(
                userId='me',
                body={'message': message}
            ).execute()
            
            logger.info(f"Draft created with ID: {draft['id']}")
            return draft
        except HttpError as e:
            logger.error(f"Error creating draft: {e}", exc_info=True)
            return None

    async def send_email(self, credentials: Credentials, to: str, subject: str, body: str) -> Optional[Dict]:
        """Send an email"""
        try:
            service = self.build_service(credentials)
            message = self.create_message(to, subject, body)
            
            sent_message = service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Email sent with ID: {sent_message['id']}")
            return sent_message
        except HttpError as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return None

    def create_message(self, to: str, subject: str, body: str) -> Dict:
        """Create a MIME message for sending/drafting"""
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}

    async def get_email_content(self, credentials: Credentials, message_id: str) -> Optional[str]:
        """Get full email content, handling text/plain, text/html, and multipart emails"""
        try:
            service = self.build_service(credentials)
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            payload = message.get('payload', {})
            
            # Helper function to decode body data
            def decode_body_data(data: str) -> str:
                return base64.urlsafe_b64decode(data).decode('utf-8')
            
            # Handle multipart emails
            if 'parts' in payload:
                # Look for text/plain first, then text/html
                text_content = None
                html_content = None
                
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    body_data = part.get('body', {}).get('data')
                    
                    if mime_type == 'text/plain' and body_data and not text_content:
                        text_content = decode_body_data(body_data)
                    elif mime_type == 'text/html' and body_data and not html_content:
                        html_content = decode_body_data(body_data)
                    
                    # Handle nested multipart (e.g., multipart/alternative)
                    if mime_type.startswith('multipart/') and 'parts' in part:
                        for subpart in part['parts']:
                            sub_mime_type = subpart.get('mimeType', '')
                            sub_body_data = subpart.get('body', {}).get('data')
                            
                            if sub_mime_type == 'text/plain' and sub_body_data and not text_content:
                                text_content = decode_body_data(sub_body_data)
                            elif sub_mime_type == 'text/html' and sub_body_data and not html_content:
                                html_content = decode_body_data(sub_body_data)
                
                # Prefer plain text, fallback to HTML
                return text_content or html_content
            
            # Handle simple email (single part)
            if payload.get('body', {}).get('data'):
                return decode_body_data(payload['body']['data'])
            
            return None
        except HttpError as e:
            logger.error(f"Error getting email content for message {message_id}: {e}", exc_info=True)
            return None
    
    async def parse_search_query(self, user_query: str) -> str:
        """Parse user query into Gmail search query, using fallback parser first, then OpenAI if needed"""
        # Check if query already uses Gmail operators (before any processing)
        gmail_operators = ['from:', 'to:', 'subject:', 'has:', 'is:', 'in:', 'after:', 'before:', 'older:', 'newer:']
        if any(op in user_query.lower() for op in gmail_operators):
            return user_query

        # Try fallback parser first (no API call needed)
        fallback_result = self._fallback_parse(user_query)
        if fallback_result != user_query:
            logger.info(f"Fallback parser converted '{user_query}' → '{fallback_result}'")
            return fallback_result

        # Only use OpenAI if fallback parser didn't help
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Gmail search query translator. Convert natural language queries "
                            "into Gmail search operators.\n\n"
                            "Gmail operators:\n"
                            "- from:email@domain.com (emails from sender)\n"
                            "- to:email@domain.com (emails to recipient)\n"
                            "- subject:keyword (in subject line)\n"
                            "- has:attachment (has files attached)\n"
                            "- is:unread (unread emails)\n"
                            "- is:starred (starred emails)\n"
                            "- after:YYYY/MM/DD (emails after date)\n"
                            "- before:YYYY/MM/DD (emails before date)\n"
                            "- OR (combine conditions)\n\n"
                            "Examples:\n"
                            "- 'emails from Sarah' → from:sarah\n"
                            "- 'unread emails from John' → from:john is:unread\n"
                            "- 'emails about meeting' → subject:meeting OR meeting\n"
                            "- 'emails with attachments from boss' → from:boss has:attachment\n\n"
                            "Return ONLY the Gmail query, no explanations."
                        )
                    },
                    {
                        "role": "user",
                        "content": user_query
                    }
                ],
                max_tokens=50,
                temperature=0.1  # Very low for consistent parsing
            )

            gmail_query = response.choices[0].message.content.strip()
            logger.info(f"OpenAI parsed '{user_query}' → '{gmail_query}'")
            return gmail_query

        except Exception as e:
            logger.error(f"Error parsing search query with OpenAI: {e}")
            # Return fallback result if OpenAI fails
            return fallback_result

    def _fallback_parse(self, user_query: str) -> str:
        """Fallback simple parser if OpenAI fails"""
        query_lower = user_query.lower()

        if "from:" in user_query or "sender:" in user_query:
            return user_query

        if "did" in query_lower and "email" in query_lower:
            parts = query_lower.split()
            for i, word in enumerate(parts):
                if word in ["did", "has"]:
                    if i + 1 < len(parts):
                        name = parts[i + 1]
                        if name not in ["email", "me", "send", "mail"]:
                            return f"from:{name}"

        if "about" in query_lower:
            parts = query_lower.split("about")
            if len(parts) > 1:
                topic = parts[1].strip()
                return f'subject:"{topic}" OR "{topic}"'

        return user_query

