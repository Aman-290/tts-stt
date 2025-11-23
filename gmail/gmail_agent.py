"""Gmail Agent for email operations - delegates to GmailService"""
from typing import List

from app.agents.base import BaseAgent, AgentContext, AgentResponse, Tool, ToolParameter, AgentType
from app.services.gmail_service import GmailService
from app.utils.token_storage import TokenStorage


class GmailAgent(BaseAgent):
    """Agent responsible for Gmail operations"""

    def __init__(self):
        super().__init__(AgentType.GMAIL, "Gmail Agent")
        self.service: GmailService = None
        self.token_storage: TokenStorage = None

    async def initialize(self) -> None:
        """Initialize Gmail service and token storage"""
        try:
            self.service = GmailService()
            self.token_storage = TokenStorage()
            self.logger.info("Gmail Agent initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Gmail Agent: {e}")
            raise

    async def execute(self, context: AgentContext) -> AgentResponse:
        """Execute Gmail operations"""
        await self.ensure_initialized()

        try:
            user_id = context.user_id
            operation = context.tool_arguments.get("operation", "gmail_search")

            # Check if user has connected Gmail
            if not self.token_storage.has_token(user_id):
                return AgentResponse.error_response(
                    "Gmail is not connected. Please connect your Gmail account in settings first."
                )

            # Get credentials from token storage
            token_json = self.token_storage.get_token(user_id)
            credentials = self.service.get_credentials_from_token(token_json)

            if operation == "gmail_search":
                query = context.tool_arguments.get("query")
                gmail_query = await self.service.parse_search_query(query)

                emails = await self.service.search_emails(credentials, gmail_query, max_results=5)

                if not emails:
                    result_text = f"No emails found matching '{query}'."
                else:
                    # Format results for voice response
                    result_text = f"I found {len(emails)} email(s). "
                    for i, email in enumerate(emails[:3], 1):  # Only mention first 3
                        result_text += f"{i}. From {email['from']}, subject: {email['subject']}. "
                    if len(emails) > 3:
                        result_text += f"And {len(emails) - 3} more."

                return AgentResponse.success_response({"result": result_text, "emails": emails})

            elif operation == "get_email":
                email_id = context.tool_arguments.get("email_id")
                content = await self.service.get_email_content(credentials, email_id)
                return AgentResponse.success_response({"content": content})

            elif operation == "check_status":
                # Validate credentials
                is_valid = self.service.validate_credentials(credentials)
                return AgentResponse.success_response({"connected": is_valid})

            elif operation == "create_draft":
                to = context.tool_arguments.get("to")
                subject = context.tool_arguments.get("subject")
                body = context.tool_arguments.get("body")
                
                draft = await self.service.create_draft(credentials, to, subject, body)
                if draft:
                    return AgentResponse.success_response({
                        "result": f"Draft created successfully to {to}.",
                        "draft": draft
                    })
                else:
                    return AgentResponse.error_response("Failed to create draft.")

            elif operation == "send_email":
                to = context.tool_arguments.get("to")
                subject = context.tool_arguments.get("subject")
                body = context.tool_arguments.get("body")
                
                sent = await self.service.send_email(credentials, to, subject, body)
                if sent:
                    return AgentResponse.success_response({
                        "result": f"Email sent successfully to {to}.",
                        "message": sent
                    })
                else:
                    return AgentResponse.error_response("Failed to send email.")

            elif operation == "get_emails_by_label":
                label = context.tool_arguments.get("label")
                result = await self.service.search_emails(credentials, f"label:{label}" if label not in ["starred", "snoozed", "sent", "drafts", "unread"] else {"starred": "is:starred", "snoozed": "in:snoozed", "sent": "in:sent", "drafts": "in:drafts", "unread": "is:unread"}.get(label), max_results=5)
                
                if not result:
                    return AgentResponse.success_response({"result": f"No {label} emails found."})
                
                # Format results
                result_text = f"I found {len(result)} {label} email(s). "
                for i, email in enumerate(result[:3], 1):
                    result_text += f"{i}. From {email['from']}, subject: {email['subject']}. "
                
                return AgentResponse.success_response({"result": result_text, "emails": result})
            
            else:
                return AgentResponse.error_response(f"Unknown operation: {operation}")

        except Exception as e:
            self.logger.error(f"Error executing Gmail Agent: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))

    def get_tools(self) -> List[Tool]:
        """Get Gmail tools"""
        return [
            Tool(
                name="gmail_search",
                description="Search the user's Gmail inbox for emails. Use this when the user asks about emails, messages, or wants to check if someone emailed them.",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Natural language search query (e.g., 'emails from Sarah', 'emails about the project')",
                        required=True
                    )
                ]
            ),
            Tool(
                name="get_email",
                description="Get the full content of a specific email by its ID. Use this when the user wants to read a specific email that was found in a search.",
                parameters=[
                    ToolParameter(
                        name="email_id",
                        type="string",
                        description="The Gmail message ID of the email to retrieve",
                        required=True
                    )
                ]
            ),
            Tool(
                name="create_draft",
                description="Create a draft email. Use this when the user wants to draft an email.",
                parameters=[
                    ToolParameter(name="to", type="string", description="Recipient email", required=True),
                    ToolParameter(name="subject", type="string", description="Email subject", required=True),
                    ToolParameter(name="body", type="string", description="Email body", required=True)
                ]
            ),
            Tool(
                name="send_email",
                description="Send an email immediately. Use this when the user wants to send an email.",
                parameters=[
                    ToolParameter(name="to", type="string", description="Recipient email", required=True),
                    ToolParameter(name="subject", type="string", description="Email subject", required=True),
                    ToolParameter(name="body", type="string", description="Email body", required=True)
                ]
            ),
            Tool(
                name="get_emails_by_label",
                description="Get emails filtered by label (starred, snoozed, sent, drafts).",
                parameters=[
                    ToolParameter(
                        name="label", 
                        type="string", 
                        description="Label to filter by (starred, snoozed, sent, drafts, unread)", 
                        required=True
                    )
                ]
            )
        ]
