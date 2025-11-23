"""Gmail Manager - Simple wrapper for voice agent integration"""
import os
from typing import Optional, Dict, Any
from app.services.gmail_service import GmailService
from app.utils.token_storage import TokenStorage
from app.utils.logger import get_logger

logger = get_logger("gmail_tool")

class GmailTool:
    """Manages Gmail operations for voice assistant"""

    def __init__(self):
        """Initialize Gmail tool"""
        self.service = GmailService()
        # Use centralized token storage
        self.token_storage = TokenStorage()

    def is_connected(self, user_id: str) -> bool:
        """Check if user has Gmail connected"""
        return self.token_storage.has_token(user_id, "gmail")

    async def search_emails(self, user_id: str, query: str) -> Dict[str, Any]:
        """Search emails and return voice-friendly response

        Args:
            user_id: User identifier
            query: Natural language search query

        Returns:
            Dictionary with success status and formatted message
        """
        try:
            # Check connection
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Gmail is not connected. Please connect your Gmail first by visiting localhost:8000/auth",
                    "emails": []
                }

            # Get credentials
            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            # Parse query and search
            gmail_query = await self.service.parse_search_query(query)
            logger.info(f"Searching Gmail with query: {gmail_query}")

            emails = await self.service.search_emails(credentials, gmail_query, max_results=5)

            if not emails:
                return {
                    "success": True,
                    "message": f"I didn't find any emails matching '{query}'.",
                    "emails": []
                }

            # Format voice-friendly response
            message = f"I found {len(emails)} email"
            if len(emails) > 1:
                message += "s"
            message += ". "

            # Describe the first 2-3 emails
            for i, email in enumerate(emails[:3], 1):
                sender = email['from'].split('<')[0].strip()  # Extract name from "Name <email>"
                subject = email['subject']
                message += f"Email {i}: From {sender}, subject: {subject}. "

            if len(emails) > 3:
                message += f"And {len(emails) - 3} more."

            return {
                "success": True,
                "message": message,
                "emails": emails
            }

        except Exception as e:
            logger.error(f"Error searching emails: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I encountered an error while searching your emails: {str(e)}",
                "emails": []
            }

    async def get_email_content(self, user_id: str, email_id: str) -> Dict[str, Any]:
        """Get full email content

        Args:
            user_id: User identifier
            email_id: Gmail message ID

        Returns:
            Dictionary with email content
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Gmail is not connected.",
                    "content": None
                }

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            content = await self.service.get_email_content(credentials, email_id)

            if not content:
                return {
                    "success": False,
                    "message": "I couldn't retrieve that email.",
                    "content": None
                }

            # Truncate for voice if too long
            max_length = 500
            if len(content) > max_length:
                content = content[:max_length] + "... (content truncated)"

            return {
                "success": True,
                "message": f"Here's the email content: {content}",
                "content": content
            }

        except Exception as e:
            logger.error(f"Error getting email content: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Sorry, I couldn't retrieve that email.",
                "content": None
            }

    async def create_draft(self, user_id: str, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Create a draft email"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            draft = await self.service.create_draft(credentials, to, subject, body)
            
            if draft:
                return {
                    "success": True,
                    "message": f"I've created a draft email to {to} with subject '{subject}'.",
                    "draft_id": draft['id']
                }
            else:
                return {"success": False, "message": "Failed to create draft."}
        except Exception as e:
            logger.error(f"Error creating draft: {e}", exc_info=True)
            return {"success": False, "message": f"Error creating draft: {str(e)}"}

    async def send_email(self, user_id: str, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an email"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            sent = await self.service.send_email(credentials, to, subject, body)
            
            if sent:
                return {
                    "success": True,
                    "message": f"I've sent the email to {to}.",
                    "message_id": sent['id']
                }
            else:
                return {"success": False, "message": "Failed to send email."}
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return {"success": False, "message": f"Error sending email: {str(e)}"}

    async def get_emails_by_label(self, user_id: str, label: str) -> Dict[str, Any]:
        """Get emails by specific label (starred, snoozed, sent, drafts)"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            # Map user-friendly labels to Gmail search queries
            label_map = {
                "starred": "is:starred",
                "snoozed": "in:snoozed",
                "sent": "in:sent",
                "drafts": "in:drafts",
                "unread": "is:unread",
                "important": "is:important"
            }
            
            query = label_map.get(label.lower(), f"label:{label}")
            logger.info(f"Searching emails with label query: {query}")

            emails = await self.service.search_emails(credentials, query, max_results=5)

            if not emails:
                return {
                    "success": True,
                    "message": f"I didn't find any {label} emails.",
                    "emails": []
                }

            # Format voice-friendly response
            message = f"I found {len(emails)} {label} email"
            if len(emails) > 1:
                message += "s"
            message += ". "

            for i, email in enumerate(emails[:3], 1):
                sender = email['from'].split('<')[0].strip()
                subject = email['subject']
                message += f"{i}: From {sender}, subject: {subject}. "

            if len(emails) > 3:
                message += f"And {len(emails) - 3} more."

            return {
                "success": True,
                "message": message,
                "emails": emails
            }

        except Exception as e:
            logger.error(f"Error getting emails by label: {e}", exc_info=True)
            return {"success": False, "message": f"Error checking {label} emails: {str(e)}"}

    async def fetch_smart_digest(self, user_id: str) -> Dict[str, Any]:
        """Fetch unread emails and prepare a smart briefing"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            emails = await self.service.fetch_daily_briefing(credentials, max_results=10)

            if not emails:
                return {
                    "success": True,
                    "message": "You have no unread emails. You're all caught up!",
                    "emails": []
                }

            # Format for LLM summarization
            email_data = []
            for email in emails:
                email_data.append(f"From: {email['from']}, Subject: {email['subject']}")
            
            # The agent will use this raw data to generate the "Smart Digest"
            return {
                "success": True,
                "message": f"I found {len(emails)} unread emails. Here's the list for your briefing.",
                "email_data": "\n".join(email_data),
                "count": len(emails)
            }
        except Exception as e:
            logger.error(f"Error fetching smart digest: {e}", exc_info=True)
            return {"success": False, "message": f"Error fetching digest: {str(e)}"}

    async def search_files(self, user_id: str, query: str) -> Dict[str, Any]:
        """Search for files/attachments"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            emails = await self.service.search_attachments(credentials, query)

            if not emails:
                return {
                    "success": True,
                    "message": f"I didn't find any emails with attachments matching '{query}'.",
                    "emails": []
                }

            message = f"I found {len(emails)} email(s) with attachments matching '{query}'. "
            for i, email in enumerate(emails[:3], 1):
                sender = email['from'].split('<')[0].strip()
                subject = email['subject']
                message += f"{i}: From {sender}, subject: {subject}. "

            return {
                "success": True,
                "message": message,
                "emails": emails
            }
        except Exception as e:
            logger.error(f"Error searching files: {e}", exc_info=True)
            return {"success": False, "message": f"Error searching files: {str(e)}"}

    async def find_unsubscribe_link(self, user_id: str, sender: str) -> Dict[str, Any]:
        """Find unsubscribe link for a sender"""
        try:
            if not self.is_connected(user_id):
                return {"success": False, "message": "Gmail is not connected."}

            token_json = self.token_storage.get_token(user_id, "gmail")
            credentials = self.service.get_credentials_from_token(token_json)

            # Search for emails from this sender
            query = f"from:{sender}"
            emails = await self.service.search_emails(credentials, query, max_results=3)

            if not emails:
                return {"success": False, "message": f"I couldn't find any emails from {sender}."}

            # Check the latest email for unsubscribe link
            latest_email_id = emails[0]['id']
            content = await self.service.get_email_content(credentials, latest_email_id)
            
            if not content:
                return {"success": False, "message": "I couldn't read the email content."}

            # Simple heuristic for unsubscribe links
            import re
            # Look for "unsubscribe" in text and try to find a nearby URL
            # This is a basic implementation - a real one would parse HTML
            if "unsubscribe" in content.lower():
                return {
                    "success": True,
                    "message": f"I found an unsubscribe option in an email from {sender}. You might want to check the email with subject '{emails[0]['subject']}' to unsubscribe."
                }
            else:
                return {
                    "success": False, 
                    "message": f"I checked the latest email from {sender} but couldn't automatically find an unsubscribe link."
                }

        except Exception as e:
            logger.error(f"Error finding unsubscribe link: {e}", exc_info=True)
            return {"success": False, "message": f"Error: {str(e)}"}

    def get_connection_instructions(self) -> str:
        """Get instructions for connecting Gmail"""
        return (
            "To connect your Gmail account, please use the 'Connect Gmail' button in the Jarvis dashboard."
        )

    def get_function_definitions(self) -> list:
        """Get function definitions for Claude function calling

        Returns:
            List of function definitions for LiveKit/Claude
        """
        return [
            {
                "name": "search_gmail",
                "description": "Search the user's Gmail inbox for emails. Use this when the user asks about emails, messages, or wants to check if someone emailed them.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query (e.g., 'emails from Sarah', 'unread emails', 'emails about the project')"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "connect_gmail",
                "description": "Provide instructions for connecting Gmail to the voice assistant. Use this when user wants to connect their Gmail account.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "create_draft_gmail",
                "description": "Create a draft email in Gmail. Use this when the user wants to draft or compose an email but not send it yet.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body content"}
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "send_email_gmail",
                "description": "Send an email using Gmail. Use this when the user explicitly wants to send an email immediately.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string", "description": "Email subject"},
                        "body": {"type": "string", "description": "Email body content"}
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "get_emails_by_label",
                "description": "Get emails filtered by a specific category/label like starred, snoozed, sent, or drafts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string", 
                            "description": "The category to filter by. Valid values: 'starred', 'snoozed', 'sent', 'drafts', 'unread', 'important'",
                            "enum": ["starred", "snoozed", "sent", "drafts", "unread", "important"]
                        }
                    },
                    "required": ["label"]
                }
            },
            {
                "name": "fetch_smart_digest",
                "description": "Get a briefing of unread emails to identify important action items and deadlines.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "search_files",
                "description": "Search for emails specifically containing attachments or files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query for the file (e.g., 'invoice', 'contract', 'PDF from Amazon')"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "find_unsubscribe_link",
                "description": "Help the user unsubscribe from newsletters or spam.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sender": {"type": "string", "description": "The name or email of the sender to unsubscribe from"}
                    },
                    "required": ["sender"]
                }
            }
        ]
