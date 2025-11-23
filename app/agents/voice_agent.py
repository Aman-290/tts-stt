import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from mem0 import AsyncMemoryClient

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    ChatContext,
    ChatMessage,
    RoomInputOptions,
    MetricsCollectedEvent,
    metrics,
)
from livekit.plugins import noise_cancellation, silero, anthropic
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Gmail, Calendar, Web Search, and Summarization integration
from app.tools.gmail_tool import GmailTool
from app.tools.calendar_tool import CalendarTool
from app.tools.web_search_tool import WebSearchTool
from app.tools.summarization_tool import SummarizationTool
from app.config import get_settings

# Metrics collection
from app.utils.metrics_collector import MetricsCollector

# Phrase manager for intermediate phrases
from app.utils.phrase_manager import phrase_manager

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
settings = get_settings()

# Initialize Mem0 client
mem0_client = AsyncMemoryClient(api_key=settings.mem0_api_key)

# Initialize Gmail, Calendar, Web Search, and Summarization tools
gmail_tool = GmailTool()
calendar_tool = CalendarTool()
web_search_tool = WebSearchTool()
summarization_tool = SummarizationTool()


class VoiceAssistant(Agent):
    """Voice assistant with Mem0 memory integration."""
    
    def __init__(self, user_id: str, user_timezone: str = None, user_current_time: str = None) -> None:
        instructions = """You are Brokai, a helpful and friendly voice AI assistant with memory capabilities, Gmail integration, Google Calendar integration, web search capabilities, and intelligent summarization.

            Your personality:
            - Professional yet approachable and conversational
            - Concise and clear in your responses
            - Eager to help and genuinely interested in the user

            Important guidelines:
            - Keep responses natural and conversational for voice
            - Avoid complex formatting, asterisks, or emojis
            - Use the context from past conversations when relevant
            - Be proactive in offering assistance based on what you remember

            Gmail capabilities:
            - Search the user's Gmail inbox using search_gmail function
            - Examples: "check my emails", "emails from Sarah", "unread emails"
            - If not connected, use connect_gmail to provide connection instructions
            - Create drafts using create_draft_gmail function
            - Send emails using send_email_gmail function
            - Examples: "draft an email to john@example.com", "send an email to sarah about the meeting"
            - Filter emails by category using get_emails_by_label function
            - Examples: "check my starred emails", "show me sent emails", "any snoozed emails?"
            - Get a smart briefing using fetch_smart_digest
            - Search for files using search_files
            - Unsubscribe from newsletters using find_unsubscribe_link
            - When drafting, you can adapt your style (professional, casual, firm, etc.) based on user request.

            Calendar capabilities:
            - View upcoming events using check_calendar function
            - Create new events using create_calendar_event function
            - Update or move existing events using update_calendar_event function (searches by event name, no need for event ID)
            - Search events by date range using search_calendar_events function
            - Create recurring events (daily, weekly, monthly, weekdays, weekends) using create_recurring_calendar_event function
            - Check availability and find free time slots using check_calendar_availability function
            - When creating events, you will automatically receive a shareable invite link that you can provide to the user
            - The invite link allows users to view the event in Google Calendar and share it with others
            - To update an event, just use the event name (e.g., "move my team meeting to 4 PM" - you'll search for "team meeting")
            - Examples: "what's on my calendar?", "schedule a meeting tomorrow at 2 PM", "move my team meeting to 4 PM", "reschedule my dentist appointment to next Monday", "show me events from Nov 20 to Nov 25", "create a daily standup at 10 AM", "when am I free on Friday for a 30-minute meeting?"
            - If not connected, use connect_calendar to provide connection instructions
            - Always mention the invite link when you create an event so users know they can share it

            Web search capabilities:
            - Search the web using search_web function for current information, news, weather, prices, etc.
            - Examples: "search for latest AI news", "what's the weather in New York?", "find iPhone 15 prices"
            - Read specific web pages using read_webpage function to extract and summarize content
            - Examples: "read this article for me", "what does this page say?", "summarize this URL"
            - Summarize multiple web pages using summarize_webpages function
            - Examples: "summarize the top 5 results for machine learning", "compare prices from Amazon and Flipkart"
            - You can provide real-time information from the web including weather updates, product prices, news, and any publicly accessible information
            - When users ask about current events, prices, or information that changes frequently, always use web search

            Summarization capabilities:
            - When users ask for a summary of emails, calendar events, or web search results, you can provide fast, intelligent summaries
            - Use summarize_content function to create concise summaries of any text content
            - Examples: "summarize my emails", "give me a summary of this week's calendar", "summarize the search results"
            - Summaries are generated instantly without API calls, extracting the most important information
            - You can also extract key bullet points from any content for quick scanning

            You have access to conversation history through your memory system and can help with email, calendar management, web information retrieval, and intelligent summarization."""

        if user_timezone and user_current_time:
            instructions += f"\n\nUser's Local Context:\n- Timezone: {user_timezone}\n- Current Local Time: {user_current_time}"

        super().__init__(
            instructions=instructions,
        )
        # Store the unique user ID from LiveKit participant identity
        self.user_id = user_id
        
        # Initialize metrics collector
        self.metrics = MetricsCollector(user_id)
        
        # Track current interaction for logging
        self.current_user_input = None
        self.interaction_start_time = None
        
        logger.info(f"Initialized VoiceAssistant for user: {self.user_id}")
        logger.info(f"Metrics logging to: {self.metrics.log_file}")

    async def on_enter(self):
        """Generate a personalized greeting based on user's raw memory data"""
        try:
            # Fetch existing memories to create a personalized greeting
            search_results = await mem0_client.search(
                query="user information name activities projects conversations",
                filters={"user_id": self.user_id},
                top_k=15,  # Get more memories for richer context
                threshold=0.05  # Very low threshold to get diverse memories
            )

            # Collect raw memory data
            raw_memories = []
            if search_results and search_results.get('results'):
                for result in search_results.get('results', []):
                    memory_text = result.get("memory", "").strip()
                    if memory_text and len(memory_text) > 10:  # Filter out very short memories
                        raw_memories.append(memory_text)

            if raw_memories:
                # Create a comprehensive memory context
                memory_context = "\n".join([f"• {memory}" for memory in raw_memories[:10]])  # Limit to 10 most relevant

                # Detailed prompt for LLM to create personalized greeting
                greeting_prompt = f"""You are Brokai, a warm and personable AI assistant with excellent memory.

Here is the user's memory data from our previous interactions:
{memory_context}

Based on this memory data, create a SHORT, WARM, and HIGHLY PERSONALIZED greeting (2-3 sentences max) that:
- References specific details from their memory to show you remember them
- Feels natural and conversational, like catching up with an old friend
- Acknowledges their recent activities, interests, or projects
- Makes them feel genuinely remembered and valued
- Ends with an invitation to help or continue the conversation
- Uses their name if known, otherwise be warmly welcoming

Be creative but authentic - don't force references that don't fit naturally. Focus on making them feel good about reconnecting with you.

Example style: "Hey Bro! Great to see you back - I remember you were deep into that machine learning project last time. How's it going? Ready to tackle something new today?"
DONT CALL THE USER ALWAYS BY THERE "NAME", MOSTLY CALL THEM "Bro".
DONT ALWAYS REWIND THE MEMORY IN THE START, IT SHOULD ONLY BE SOMETIMES NOT ALWAYS.
Keep it concise and warm!"""

                logger.info(f"Using {len(raw_memories)} raw memories for personalized greeting")

                await self.session.generate_reply(
                    instructions=greeting_prompt
                )

            else:
                # Fallback to a warm, engaging greeting when no memories exist
                await self.session.generate_reply(
                    instructions="""You are Brokai, a warm and personable AI assistant. Create a SHORT, genuinely welcoming greeting (2 sentences max) that makes new users feel comfortable and excited to interact with you. Show enthusiasm and approachability. Example: "Hello! I'm Brokai, your AI assistant. It's wonderful to meet you - I'm here to help with anything you need today!" Keep it concise and warm!"""
                )

        except Exception as e:
            logger.warning(f"Failed to generate personalized greeting from memory: {e}")
            # Fallback to a nice generic greeting
            await self.session.generate_reply(
                instructions="Greet the user warmly as Bro and offer your assistance with genuine enthusiasm and personality."
            )
    
    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        """
        Runs BEFORE the LLM generates a response.
        Automatically retrieves relevant memories and injects them into context.
        """
        # RAG: Retrieve relevant context from Mem0 and inject as system message
        try:
            user_text = new_message.text_content
            if not user_text:
                logger.warning("User message has no text content, skipping RAG.")
                return
            
            # Store for interaction logging
            self.current_user_input = user_text
            self.interaction_start_time = time.time()

            logger.info(f"About to await mem0_client.search for RAG context with query: {user_text}")
            
            # Track memory retrieval
            mem_start = time.time()
            search_results = await mem0_client.search(
                query=user_text,
                filters={
                    "user_id": self.user_id
                },
                top_k=5,  # Limit to top 5 most relevant memories
                threshold=0.3,  # Only include memories with similarity > 0.3
            )
            mem_duration = time.time() - mem_start
            
            # Log memory retrieval
            results_count = len(search_results.get('results', []))
            avg_score = sum(r.get('score', 0) for r in search_results.get('results', [])) / results_count if results_count > 0 else 0
            self.metrics.log_memory_retrieval(
                query=user_text,
                results_count=results_count,
                avg_relevance_score=avg_score,
                duration=mem_duration
            )
            
            logger.info(f"mem0_client.search returned: {search_results}")
            
            if search_results and search_results.get('results', []):
                # Build concise context (just the memory content, no verbose formatting)
                context_parts = []
                for result in search_results.get('results', [])[:5]:  # Limit to top 5
                    paragraph = result.get("memory") or result.get("text")
                    if paragraph:
                        # Clean up the memory text
                        if "from [" in paragraph:
                            paragraph = paragraph.split("]")[1].strip() if "]" in paragraph else paragraph
                        context_parts.append(f"- {paragraph}")
                
                if context_parts:
                    # More concise format
                    full_context = "\n".join(context_parts)
                    logger.info(f"Injecting RAG context ({len(context_parts)} memories): {full_context[:200]}...")
                    
                    # Add single RAG context system message
                    turn_ctx.add_message(
                        role="system", 
                        content=f"Previous conversation context:\n{full_context}"
                    )
                    await self.update_chat_ctx(turn_ctx)
        except Exception as e:
            logger.warning(f"Failed to inject RAG context from Mem0: {e}")

        # Persist the user message in Mem0
        try:
            logger.info(f"Adding user message to Mem0: {new_message.text_content}")
            add_result = await mem0_client.add(
                [{"role": "user", "content": new_message.text_content}],
                user_id=self.user_id
            )
            logger.info(f"Mem0 add result (user): {add_result}")
        except Exception as e:
            logger.warning(f"Failed to store user message in Mem0: {e}")

        await super().on_user_turn_completed(turn_ctx, new_message)
    
    async def on_agent_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        """
        Runs AFTER the LLM generates a response.
        Log the complete interaction with user input and AI response.
        Store AI response in Mem0 for future recall.
        """
        try:
            if self.current_user_input and new_message.text_content:
                # Calculate interaction duration
                duration = time.time() - self.interaction_start_time if self.interaction_start_time else 0
                
                # Log the complete interaction
                self.metrics.log_interaction(
                    user_input=self.current_user_input,
                    ai_response=new_message.text_content,
                    duration=duration,
                    metadata={
                        'timestamp': datetime.now().isoformat(),
                        'role': new_message.role
                    }
                )
                
                logger.info(f"Logged interaction: User: '{self.current_user_input[:50]}...' -> AI: '{new_message.text_content[:50]}...' ({duration:.2f}s)")
                
                # Reset for next interaction
                self.current_user_input = None
                self.interaction_start_time = None
        except Exception as e:
            logger.warning(f"Failed to log interaction: {e}")
        
        # Store AI response in Mem0 (including web search results)
        try:
            if new_message.text_content:
                logger.info(f"Adding AI response to Mem0: {new_message.text_content[:100]}...")
                add_result = await mem0_client.add(
                    [{"role": "assistant", "content": new_message.text_content}],
                    user_id=self.user_id
                )
                logger.info(f"Mem0 add result (assistant): {add_result}")
        except Exception as e:
            logger.warning(f"Failed to store AI response in Mem0: {e}")
        
        await super().on_agent_turn_completed(turn_ctx, new_message)
        
        


async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the LiveKit voice agent."""

    # Wait for a participant to connect
    await ctx.connect()

    # Wait for the first participant to join
    participant = await ctx.wait_for_participant()
    
    # Get user_id from participant identity (which is set to Clerk ID in token.ts)
    user_id = participant.identity
    logger.info(f"User joined: {user_id} (Identity: {participant.identity})")
    
    # Fallback to metadata if needed (though identity should be sufficient)
    if not user_id or user_id.startswith("identity-"):
        try:
            if participant.metadata:
                import json
                metadata = json.loads(participant.metadata)
                if "user_id" in metadata:
                    user_id = metadata["user_id"]
                    logger.info(f"Found user_id in metadata: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to parse participant metadata: {e}")

    # Default fallback if everything fails
    if not user_id:
        user_id = "livekit-mem0"
        logger.warning("Could not determine user_id, falling back to default")

    # Get user attributes
    user_timezone = participant.attributes.get("user_timezone")
    user_current_time = participant.attributes.get("user_current_time")
    
    logger.info(f"User connected with timezone: {user_timezone} and local time: {user_current_time}")

    ctx.log_context_fields = {
        "room": ctx.room.name,
        "user_id": user_id
    }
    
    # Create voice assistant instance BEFORE tool definitions (tools need to reference it)
    voice_assistant = VoiceAssistant(user_id=user_id, user_timezone=user_timezone, user_current_time=user_current_time)

    # Gmail function handlers (decorated with @agents.function_tool)
    @agents.function_tool
    async def search_gmail(query: str):
        """Search the user's Gmail inbox for emails.

        Args:
            query: Natural language search query (e.g., 'emails from Sarah', 'unread emails')
        """
        start_time = time.time()
        logger.info(f"🔍 Gmail search requested: {query}")
        
        # Speak intermediate phrase while searching
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'searching')}'"
        )
        
        try:
            result = await gmail_tool.search_emails(user_id, query)
            
            # Contextual Sender Info: Check Mem0 for sender context
            if result.get("emails"):
                for email in result["emails"][:3]:
                    sender_name = email['from'].split('<')[0].strip()
                    # Quick Mem0 check for this sender
                    try:
                        mem_result = await mem0_client.search(query=f"who is {sender_name}", filters={"user_id": user_id}, top_k=1)
                        if mem_result and mem_result.get('results'):
                            context = mem_result['results'][0].get('memory')
                            # Inject context into the message for the LLM
                            result["message"] += f" (Context on {sender_name}: {context})"
                    except Exception:
                        pass # Fail silently to keep it fast
            
            # Log metrics
            voice_assistant.metrics.log_tool_call(
                tool_name="search_gmail",
                params={"query": query},
                success=result.get("success", False),
                duration=time.time() - start_time,
                result=result.get("message")
            )
            
            return result["message"]
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="search_gmail",
                params={"query": query},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    @agents.function_tool
    async def connect_gmail():
        """Provide instructions for connecting Gmail to the voice assistant."""
        import webbrowser
        from app.config import get_settings
        settings = get_settings()
        
        logger.info("🔗 Gmail connection requested")
        if gmail_tool.is_connected(user_id):
            return "Your Gmail is already connected! You can ask me to check your emails anytime."

        # Auto-open browser for development
        auth_url = f"{settings.auth_server_url}/gmail/auth?user_id={user_id}"
        try:
            webbrowser.open(auth_url)
            logger.info(f"✅ Opened browser to {auth_url}")
            return "I've opened your browser to connect Gmail. Please complete the authorization and I'll be ready to help with your emails!"
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")
            return gmail_tool.get_connection_instructions()

    @agents.function_tool
    async def create_draft_gmail(to: str, subject: str, body: str):
        """Create a draft email in Gmail.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
        """
        start_time = time.time()
        logger.info(f"📝 Creating draft email to {to}")
        
        # Speak intermediate phrase while creating draft
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'creating_draft')}'"
        )
        
        try:
            result = await gmail_tool.create_draft(user_id, to, subject, body)
            voice_assistant.metrics.log_tool_call(
                tool_name="create_draft_gmail",
                params={"to": to, "subject": subject},
                success=result.get("success", False),
                duration=time.time() - start_time
            )
            return result["message"]
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="create_draft_gmail",
                params={"to": to, "subject": subject},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    @agents.function_tool
    async def send_email_gmail(to: str, subject: str, body: str):
        """Send an email using Gmail.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
        """
        start_time = time.time()
        logger.info(f"📧 Sending email to {to}")
        
        # Speak intermediate phrase while sending
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'sending')}'"
        )
        
        try:
            result = await gmail_tool.send_email(user_id, to, subject, body)
            voice_assistant.metrics.log_tool_call(
                tool_name="send_email_gmail",
                params={"to": to, "subject": subject},
                success=result.get("success", False),
                duration=time.time() - start_time
            )
            return result["message"]
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="send_email_gmail",
                params={"to": to, "subject": subject},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    @agents.function_tool
    async def get_emails_by_label(label: str):
        """Get emails filtered by a specific category/label.
        
        Args:
            label: The category to filter by (starred, snoozed, sent, drafts, unread)
        """
        logger.info(f"🔍 Checking emails with label: {label}")
        
        # Speak intermediate phrase while checking
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'checking_label')}'"
        )
        
        result = await gmail_tool.get_emails_by_label(user_id, label)
        return result["message"]

    @agents.function_tool
    async def fetch_smart_digest():
        """Get a smart briefing of unread emails with action items."""
        logger.info("📰 Fetching smart digest")
        
        # Speak intermediate phrase while analyzing
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'analyzing')}'"
        )
        
        result = await gmail_tool.fetch_smart_digest(user_id)
        return result["message"] + "\nRaw Data for Summary:\n" + result.get("email_data", "")

    @agents.function_tool
    async def search_files(query: str):
        """Search for emails with specific attachments/files.
        
        Args:
            query: Search query (e.g., 'invoice', 'PDF from Amazon')
        """
        logger.info(f"📎 Searching files: {query}")
        
        # Speak intermediate phrase while searching
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('gmail', 'searching_files')}'"
        )
        
        result = await gmail_tool.search_files(user_id, query)
        return result["message"]

    @agents.function_tool
    async def find_unsubscribe_link(sender: str):
        """Find unsubscribe link for a sender.
        
        Args:
            sender: Sender name or email
        """
        logger.info(f"🚫 Looking for unsubscribe link from: {sender}")
        result = await gmail_tool.find_unsubscribe_link(user_id, sender)
        return result["message"]

    # Calendar function handlers (decorated with @agents.function_tool)
    @agents.function_tool
    async def check_calendar(days: int = 7):
        """View upcoming calendar events.

        Args:
            days: Number of days to look ahead (default 7)
        """
        logger.info(f"📅 Calendar check requested for next {days} days")
        
        # Speak intermediate phrase while checking
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'checking')}'"
        )
        
        result = await calendar_tool.list_upcoming_events(user_id, days)
        return result["message"]

    @agents.function_tool
    async def create_calendar_event(summary: str, start_time_str: str, duration_minutes: int = 60):
        """Create a new calendar event.

        Args:
            summary: Event title/description
            start_time_str: Start time in ISO format (e.g., '2025-11-20T14:00:00')
            duration_minutes: Event duration in minutes (default 60)
        """
        logger.info(f"📅 Creating calendar event: {summary} at {start_time_str}")
        
        # Speak intermediate phrase while creating
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'creating')}'"
        )
        
        try:
            from datetime import datetime
            from app.config import get_settings

            # Parse the datetime string
            start_time = datetime.fromisoformat(start_time_str)
            logger.info(f"Parsed start time: {start_time} (tzinfo: {start_time.tzinfo})")

            # Get user's timezone from attributes or config
            settings = get_settings()
            # Use dynamic user timezone if available, otherwise fallback to settings
            timezone_to_use = user_timezone if user_timezone else settings.user_timezone
            
            logger.info(f"Using timezone: {timezone_to_use}")

            result = await calendar_tool.create_event(
                user_id,
                summary=summary,
                start_time=start_time,
                duration_minutes=duration_minutes,
                timezone=timezone_to_use
            )

            logger.info(f"Calendar tool result: {result}")
            return result["message"]
        except ValueError as e:
            logger.error(f"DateTime parsing error: {e}", exc_info=True)
            return f"Sorry, I couldn't parse the time format. Please provide a valid datetime: {str(e)}"
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}", exc_info=True)
            return f"Sorry, I encountered an error creating the event: {str(e)}"

    @agents.function_tool
    async def connect_calendar():
        """Provide instructions for connecting Google Calendar to the voice assistant."""
        import webbrowser
        from app.config import get_settings
        settings = get_settings()
        
        logger.info("🔗 Calendar connection requested")
        if calendar_tool.is_connected(user_id):
            return "Your Google Calendar is already connected! You can ask me about your schedule anytime."

        # Auto-open browser for development
        auth_url = f"{settings.auth_server_url}/calendar/auth?user_id={user_id}"
        try:
            webbrowser.open(auth_url)
            logger.info(f"✅ Opened browser to {auth_url}")
            return "I've opened your browser to connect Google Calendar. Please complete the authorization and I'll be able to manage your calendar!"
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")
            return calendar_tool.get_connection_instructions()

    @agents.function_tool
    async def get_calendar_invite_link(event_id: str):
        """Get the shareable invite link for a specific calendar event.
        
        Args:
            event_id: The ID of the calendar event
        """
        logger.info(f"🔗 Getting invite link for event: {event_id}")
        
        # Speak intermediate phrase while getting link
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'getting_link')}'"
        )
        
        result = await calendar_tool.get_event_invite_link(user_id, event_id)
        return result["message"]

    @agents.function_tool
    async def update_calendar_event(
        event_summary: str,
        new_summary: str = None,
        start_time_str: str = None,
        duration_minutes: int = None,
        description: str = None,
        location: str = None
    ):
        """Update or move an existing calendar event by searching for it by name.
        
        Args:
            event_summary: Current title/name of the event to update (e.g., "team meeting", "dentist appointment")
            new_summary: New event title (optional)
            start_time_str: New start time in ISO format (optional, e.g., '2025-11-20T14:00:00')
            duration_minutes: New duration in minutes (optional)
            description: New description (optional)
            location: New location (optional)
        """
        logger.info(f"📅 Updating calendar event: {event_summary}")
        
        # Speak intermediate phrase while updating
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'updating')}'"
        )
        
        try:
            from datetime import datetime, timedelta
            from app.config import get_settings
            
            # First, search for the event by summary in the next 30 days
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=30)
            
            # Use the calendar_tool method to search events
            search_result = await calendar_tool.search_events_by_date_range(
                user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not search_result.get("success") or not search_result.get("events"):
                return f"I couldn't find any upcoming events in your calendar to update."
            
            events = search_result["events"]
            
            # Find event matching the summary (case-insensitive partial match)
            matching_event = None
            event_summary_lower = event_summary.lower()
            for event in events:
                if event_summary_lower in event['summary'].lower():
                    matching_event = event
                    break
            
            if not matching_event:
                return f"I couldn't find an event called '{event_summary}' in your calendar. Please check the event name and try again."
            
            event_id = matching_event['id']
            logger.info(f"Found event: {matching_event['summary']} (ID: {event_id})")
            
            # Parse start time if provided
            start_time = None
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
            
            # Get user's timezone
            settings = get_settings()
            timezone_to_use = user_timezone if user_timezone else settings.user_timezone
            
            result = await calendar_tool.update_event(
                user_id,
                event_id=event_id,
                summary=new_summary,
                start_time=start_time,
                duration_minutes=duration_minutes,
                description=description,
                location=location,
                timezone=timezone_to_use
            )
            
            return result["message"]
        except Exception as e:
            logger.error(f"Error updating calendar event: {e}", exc_info=True)
            return f"Sorry, I encountered an error updating the event: {str(e)}"



    @agents.function_tool
    async def search_calendar_events(start_date_str: str, end_date_str: str):
        """Search for calendar events within a specific date range.
        
        IMPORTANT: You must provide dates in ISO format (YYYY-MM-DDTHH:MM:SS).
        When user says "November 20", convert it to "2025-11-20T00:00:00".
        When user says "November 25", convert it to "2025-11-25T23:59:59".
        
        Args:
            start_date_str: Start date in ISO format (e.g., '2025-11-20T00:00:00')
            end_date_str: End date in ISO format (e.g., '2025-11-25T23:59:59')
        """
        logger.info(f"📅 Searching calendar events from {start_date_str} to {end_date_str}")
        
        # Speak intermediate phrase while searching
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'searching_range')}'"
        )
        
        try:
            from datetime import datetime
            
            # Try to parse the dates - be flexible with formats
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except:
                # Try parsing without time component
                start_date = datetime.strptime(start_date_str.split('T')[0], '%Y-%m-%d')
            
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except:
                # Try parsing without time component and set to end of day
                end_date = datetime.strptime(end_date_str.split('T')[0], '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            
            logger.info(f"Parsed dates: {start_date} to {end_date}")
            
            result = await calendar_tool.search_events_by_date_range(
                user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return result["message"]
        except Exception as e:
            logger.error(f"Error searching calendar events: {e}", exc_info=True)
            return f"Sorry, I encountered an error searching events: {str(e)}"


    @agents.function_tool
    async def create_recurring_calendar_event(
        summary: str,
        start_time_str: str,
        duration_minutes: int,
        recurrence_pattern: str,
        count: int = None,
        until_date_str: str = None,
        description: str = ""
    ):
        """Create a recurring calendar event.
        
        Args:
            summary: Event title
            start_time_str: First occurrence start time in ISO format (e.g., '2025-11-20T10:00:00')
            duration_minutes: Event duration in minutes
            recurrence_pattern: Pattern like 'daily', 'weekly', 'monthly', 'weekdays', or 'weekends'
            count: Number of occurrences (optional, e.g., 10 for 10 occurrences)
            until_date_str: End date for recurrence in ISO format (optional)
            description: Event description (optional)
        """
        logger.info(f"📅 Creating recurring event: {summary} - {recurrence_pattern}")
        
        # Speak intermediate phrase while creating
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'creating_recurring')}'"
        )
        
        try:
            from datetime import datetime
            from app.config import get_settings
            
            start_time = datetime.fromisoformat(start_time_str)
            until_date = datetime.fromisoformat(until_date_str) if until_date_str else None
            
            # Get user's timezone
            settings = get_settings()
            timezone_to_use = user_timezone if user_timezone else settings.user_timezone
            
            result = await calendar_tool.create_recurring_event(
                user_id,
                summary=summary,
                start_time=start_time,
                duration_minutes=duration_minutes,
                recurrence_pattern=recurrence_pattern,
                count=count,
                until_date=until_date,
                description=description,
                timezone=timezone_to_use
            )
            
            return result["message"]
        except Exception as e:
            logger.error(f"Error creating recurring event: {e}", exc_info=True)
            return f"Sorry, I encountered an error creating the recurring event: {str(e)}"

    @agents.function_tool
    async def check_calendar_availability(
        date_str: str,
        duration_minutes: int,
        working_hours_start: int = 9,
        working_hours_end: int = 18
    ):
        """Check availability and find free time slots on a specific date.
        
        Args:
            date_str: Date to check in ISO format (e.g., '2025-11-22T00:00:00')
            duration_minutes: Required meeting duration in minutes
            working_hours_start: Start of working hours in 24h format (default 9 for 9 AM)
            working_hours_end: End of working hours in 24h format (default 18 for 6 PM)
        """
        logger.info(f"📅 Checking availability on {date_str} for {duration_minutes} minutes")
        
        # Speak intermediate phrase while checking
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('calendar', 'checking_availability')}'"
        )
        
        try:
            from datetime import datetime
            
            date = datetime.fromisoformat(date_str)
            
            result = await calendar_tool.check_availability(
                user_id,
                date=date,
                duration_minutes=duration_minutes,
                working_hours_start=working_hours_start,
                working_hours_end=working_hours_end
            )
            
            return result["message"]
        except Exception as e:
            logger.error(f"Error checking availability: {e}", exc_info=True)
            return f"Sorry, I encountered an error checking availability: {str(e)}"

    # Web search function handlers (decorated with @agents.function_tool)
    @agents.function_tool
    async def search_web(query: str, num_results: int = 5):
        """Search the web for information.
        
        Args:
            query: Search query (e.g., 'latest AI news', 'weather in New York', 'iPhone 15 price')
            num_results: Number of results to return (default 5, max 20)
        """
        start_time = time.time()
        logger.info(f"🔍 Web search requested: {query}")
        
        # Speak intermediate phrase while searching
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('web_search', 'searching')}'"
        )
        
        try:
            result = await web_search_tool.search_web(query, num_results)
            
            # Log metrics
            voice_assistant.metrics.log_tool_call(
                tool_name="search_web",
                params={"query": query, "num_results": num_results},
                success=result.get("success", False),
                duration=time.time() - start_time,
                result=result.get("message")
            )
            
            return result["message"]
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="search_web",
                params={"query": query, "num_results": num_results},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    @agents.function_tool
    async def read_webpage(url: str):
        """Read and extract content from a specific webpage.
        
        Args:
            url: URL of the webpage to read and extract content from
        """
        start_time = time.time()
        logger.info(f"📄 Reading webpage: {url}")
        
        # Speak intermediate phrase while reading
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('web_search', 'reading')}'"
        )
        
        try:
            result = await web_search_tool.read_webpage(url)
            
            # Log metrics
            voice_assistant.metrics.log_tool_call(
                tool_name="read_webpage",
                params={"url": url},
                success=result.get("success", False),
                duration=time.time() - start_time,
                result=f"Extracted {result.get('length', 0)} characters"
            )
            
            return result["message"]
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="read_webpage",
                params={"url": url},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    @agents.function_tool
    async def summarize_webpages(query: str, num_results: int = 5, focus: str = None):
        """Search the web and summarize content from multiple pages.
        
        Args:
            query: Search query to find relevant pages
            num_results: Number of pages to summarize (default 5, max 10)
            focus: Optional focus area for summarization (e.g., 'pricing', 'features', 'reviews')
        """
        start_time = time.time()
        logger.info(f"📝 Summarizing web results for: {query}")
        
        # Speak intermediate phrase while searching
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('web_search', 'searching')}'"
        )
        
        try:
            result = await web_search_tool.search_and_summarize(query, num_results, focus)
            
            if result.get("success") and result.get("summary_prompt"):
                # Speak intermediate phrase while summarizing
                await session.generate_reply(
                    instructions=f"Say this exactly: '{phrase_manager.get_phrase('web_search', 'summarizing')}'"
                )
                
                # Use the LLM to generate the summary
                # The summary_prompt contains the combined content from all pages
                summary_response = result["summary_prompt"]
                
                # Log metrics
                voice_assistant.metrics.log_tool_call(
                    tool_name="summarize_webpages",
                    params={"query": query, "num_results": num_results, "focus": focus},
                    success=True,
                    duration=time.time() - start_time,
                    result=f"Summarized {result.get('num_pages', 0)} pages"
                )
                
                return summary_response
            else:
                # Log metrics for failure
                voice_assistant.metrics.log_tool_call(
                    tool_name="summarize_webpages",
                    params={"query": query, "num_results": num_results, "focus": focus},
                    success=False,
                    duration=time.time() - start_time,
                    error=result.get("message")
                )
                
                return result.get("message", "Failed to summarize web pages.")
                
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="summarize_webpages",
                params={"query": query, "num_results": num_results, "focus": focus},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise

    # Summarization function handler (decorated with @agents.function_tool)
    @agents.function_tool
    async def summarize_content(content_type: str, content_data: str = None):
        """Summarize content from Gmail, Calendar, Web Search, or general text.
        
        Args:
            content_type: Type of content to summarize ('text', 'gmail', 'calendar', 'web_search')
            content_data: JSON string or text content to summarize (optional for some types)
        """
        start_time = time.time()
        logger.info(f"📝 Summarization requested for: {content_type}")
        
        # Speak intermediate phrase while summarizing
        await session.generate_reply(
            instructions=f"Say this exactly: '{phrase_manager.get_phrase('summarization', 'summarizing')}'"
        )
        
        try:
            import json
            
            if content_type == "text" and content_data:
                # Summarize general text
                result = await summarization_tool.summarize_text(content_data, max_sentences=5)
                
            elif content_type == "gmail":
                # Parse email data from JSON string
                if content_data:
                    emails = json.loads(content_data)
                    result = await summarization_tool.summarize_gmail_results(emails)
                else:
                    result = {
                        "success": False,
                        "message": "No email data provided for summarization."
                    }
                    
            elif content_type == "calendar":
                # Parse event data from JSON string
                if content_data:
                    events = json.loads(content_data)
                    result = await summarization_tool.summarize_calendar_events(events)
                else:
                    result = {
                        "success": False,
                        "message": "No calendar data provided for summarization."
                    }
                    
            elif content_type == "web_search":
                # Parse search results from JSON string
                if content_data:
                    data = json.loads(content_data)
                    results = data.get("results", [])
                    query = data.get("query", "")
                    result = await summarization_tool.summarize_web_search_results(results, query)
                else:
                    result = {
                        "success": False,
                        "message": "No search results provided for summarization."
                    }
            else:
                result = {
                    "success": False,
                    "message": f"Unknown content type: {content_type}. Supported types: text, gmail, calendar, web_search"
                }
            
            # Log metrics
            voice_assistant.metrics.log_tool_call(
                tool_name="summarize_content",
                params={"content_type": content_type},
                success=result.get("success", False),
                duration=time.time() - start_time,
                result=result.get("message", "")[:100]
            )
            
            return result["message"]
            
        except Exception as e:
            voice_assistant.metrics.log_tool_call(
                tool_name="summarize_content",
                params={"content_type": content_type},
                success=False,
                duration=time.time() - start_time,
                error=str(e)
            )
            raise


    # Create agent session with STT-LLM-TTS pipeline
    session = AgentSession(
        # Speech-to-Text: AssemblyAI via LiveKit Inference
        stt="assemblyai/universal-streaming:en",

        # Large Language Model: Claude 3.5 Sonnet (Latest valid model)
        llm=anthropic.LLM(
            model="claude-sonnet-4-20250514",
            temperature=0.8,
        ),

        # Text-to-Speech: Cartesia Sonic-3 (natural voice)
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        # Voice Activity Detection: Silero
        vad=silero.VAD.load(),

        # Turn Detection: Multilingual model for natural conversation flow
        turn_detection=MultilingualModel(),

        # Gmail, Calendar, Web Search, and Summarization function tools (pass decorated functions directly)
        tools=[
            search_gmail, connect_gmail, create_draft_gmail, send_email_gmail, 
            get_emails_by_label, fetch_smart_digest, search_files, find_unsubscribe_link, 
            check_calendar, create_calendar_event, connect_calendar, get_calendar_invite_link,
            search_web, read_webpage, summarize_webpages,
            summarize_content
        ],
    )
    
    # Initialize usage collector for metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        # Log metrics to console (latency, tokens, etc.)
        metrics.log_metrics(ev.metrics)
        # Collect usage stats for summary
        usage_collector.collect(ev.metrics)
        
        # Extract and log latencies to our metrics collector
        try:
            # Get latency metrics from LiveKit
            if hasattr(ev.metrics, 'stt_ttfb'):
                voice_assistant.metrics.log_latency('stt', ev.metrics.stt_ttfb * 1000)  # Convert to ms
            
            if hasattr(ev.metrics, 'llm_ttfb'):
                voice_assistant.metrics.log_latency('llm', ev.metrics.llm_ttfb * 1000)
            
            if hasattr(ev.metrics, 'tts_ttfb'):
                voice_assistant.metrics.log_latency('tts', ev.metrics.tts_ttfb * 1000)
            
            # Calculate end-to-end latency
            if hasattr(ev.metrics, 'e2e_latency'):
                voice_assistant.metrics.log_latency('e2e', ev.metrics.e2e_latency * 1000)
            elif all(hasattr(ev.metrics, attr) for attr in ['stt_ttfb', 'llm_ttfb', 'tts_ttfb']):
                e2e = (ev.metrics.stt_ttfb + ev.metrics.llm_ttfb + ev.metrics.tts_ttfb) * 1000
                voice_assistant.metrics.log_latency('e2e', e2e)
        except Exception as e:
            logger.warning(f"Failed to log LiveKit latencies: {e}")

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage Summary: {summary}")
    
    async def save_metrics():
        """Save session metrics and print summary"""
        try:
            # Save metrics to file
            session_file = voice_assistant.metrics.save_session()
            
            # Print summary to console
            voice_assistant.metrics.print_summary()
            
            logger.info(f"✅ Metrics saved to: {session_file}")
            logger.info(f"✅ Text log saved to: {voice_assistant.metrics.log_file}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(save_metrics)
    
    # Start the session with the user-specific voice assistant
    await session.start(
        room=ctx.room,
        agent=voice_assistant,  # ✅ Pass user ID and time context
        room_input_options=RoomInputOptions(
            # Enhanced noise cancellation for clear audio
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    logger.info(f"Jarvis voice agent is ready for user: {user_id}")


if __name__ == "__main__":
    # Run the agent with LiveKit CLI
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))