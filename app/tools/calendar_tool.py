"""Calendar Manager - Simple wrapper for voice agent integration"""
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.services.calendar_service import CalendarService
from app.utils.token_storage import TokenStorage
from app.utils.logger import get_logger

logger = get_logger("calendar_tool")

class CalendarTool:
    """Manages Google Calendar operations for voice assistant"""

    def __init__(self):
        """Initialize Calendar tool"""
        self.service = CalendarService()
        # Use centralized token storage
        self.token_storage = TokenStorage()

    def is_connected(self, user_id: str) -> bool:
        """Check if user has Calendar connected"""
        return self.token_storage.has_token(user_id, "calendar")

    async def list_upcoming_events(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """List upcoming calendar events

        Args:
            user_id: User identifier
            days: Number of days to look ahead (default 7)

        Returns:
            Dictionary with success status and formatted message
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first by visiting localhost:8000/calendar/auth",
                    "events": []
                }

            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)

            time_max = datetime.utcnow() + timedelta(days=days)
            events = await self.service.list_events(
                credentials,
                time_min=datetime.utcnow(),
                time_max=time_max,
                max_results=10
            )

            if not events:
                return {
                    "success": True,
                    "message": f"You have no upcoming events in the next {days} days.",
                    "events": []
                }

            # Format voice-friendly response
            message = f"You have {len(events)} upcoming event"
            if len(events) > 1:
                message += "s"
            message += ". "

            for i, event in enumerate(events[:3], 1):
                summary = event['summary']
                start = event['start']
                # Parse and format datetime
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    time_str = start_dt.strftime("%A at %I:%M %p")
                except:
                    time_str = start

                message += f"Event {i}: {summary}, {time_str}. "

            if len(events) > 3:
                message += f"And {len(events) - 3} more."

            return {
                "success": True,
                "message": message,
                "events": events
            }

        except Exception as e:
            logger.error(f"Error listing events: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I encountered an error while checking your calendar: {str(e)}",
                "events": []
            }

    async def create_event(
        self,
        user_id: str,
        summary: str,
        start_time: datetime,
        duration_minutes: int = 60,
        description: str = "",
        timezone: str = "America/Los_Angeles"
    ) -> Dict[str, Any]:
        """Create a calendar event

        Args:
            user_id: User identifier
            summary: Event title
            start_time: Event start time
            duration_minutes: Event duration in minutes
            description: Event description
            timezone: Timezone for the event (default: America/Los_Angeles)

        Returns:
            Dictionary with success status and message
        """
        try:
            logger.info(f"📅 Creating event for user {user_id}: '{summary}' at {start_time}")

            if not self.is_connected(user_id):
                logger.warning(f"User {user_id} is not connected to Calendar")
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first.",
                }

            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)

            end_time = start_time + timedelta(minutes=duration_minutes)

            logger.info(f"Creating event: {summary}, Start: {start_time}, End: {end_time}, TZ: {timezone}")

            event = await self.service.create_event(
                credentials,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                description=description,
                timezone=timezone
            )

            if not event:
                logger.error("Calendar API returned None - event creation failed!")
                return {
                    "success": False,
                    "message": "Failed to create the event. Please check the logs for details."
                }

            logger.info(f"✅ Event created successfully: {event.get('id')} - {event.get('link')}")

            time_str = start_time.strftime("%A, %B %d at %I:%M %p")
            event_link = event.get('link', '')

            message = f"I've created an event called '{summary}' for {time_str}."
            if event_link:
                message += f" You can view and share it using this link: {event_link}"

            return {
                "success": True,
                "message": message,
                "event": event,
                "invite_link": event_link
            }

        except Exception as e:
            logger.error(f"❌ Error creating event: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I couldn't create the event: {str(e)}"
            }

    def get_connection_instructions(self) -> str:
        """Get instructions for connecting Calendar"""
        return (
            "To connect your Google Calendar, please use the 'Connect Calendar' button in the Jarvis dashboard."
        )

    async def get_event_invite_link(self, user_id: str, event_id: str) -> Dict[str, Any]:
        """Get shareable invite link for a specific event
        
        Args:
            user_id: User identifier
            event_id: ID of the calendar event
            
        Returns:
            Dictionary with success status and invite link
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first.",
                    "invite_link": ""
                }
            
            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)
            
            invite_link = await self.service.get_event_link(credentials, event_id)
            
            if not invite_link:
                return {
                    "success": False,
                    "message": f"Could not find event with ID {event_id}",
                    "invite_link": ""
                }
            
            return {
                "success": True,
                "message": f"Here's the shareable invite link for your event: {invite_link}",
                "invite_link": invite_link
            }
            
        except Exception as e:
            logger.error(f"Error getting event invite link: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I encountered an error: {str(e)}",
                "invite_link": ""
            }

    async def update_event(
        self,
        user_id: str,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = "America/Los_Angeles"
    ) -> Dict[str, Any]:
        """Update an existing calendar event
        
        Args:
            user_id: User identifier
            event_id: ID of the event to update
            summary: New event title (optional)
            start_time: New start time (optional)
            duration_minutes: New duration in minutes (optional)
            description: New description (optional)
            location: New location (optional)
            timezone: Timezone for the event (default: America/Los_Angeles)
            
        Returns:
            Dictionary with success status and message
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first."
                }
            
            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)
            
            # Calculate end time if start time and duration are provided
            end_time = None
            if start_time and duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            
            event = await self.service.update_event(
                credentials,
                event_id=event_id,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                timezone=timezone
            )
            
            if not event:
                return {
                    "success": False,
                    "message": "Failed to update the event. Please check the event ID."
                }
            
            message = f"I've updated the event '{event.get('summary', 'your event')}'"
            if start_time:
                time_str = start_time.strftime("%A, %B %d at %I:%M %p")
                message += f" to {time_str}"
            message += "."
            
            event_link = event.get('link', '')
            if event_link:
                message += f" View it here: {event_link}"
            
            return {
                "success": True,
                "message": message,
                "event": event
            }
            
        except Exception as e:
            logger.error(f"Error updating event: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I couldn't update the event: {str(e)}"
            }

    async def search_events_by_date_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Search for events within a specific date range
        
        Args:
            user_id: User identifier
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            Dictionary with success status and formatted message
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first.",
                    "events": []
                }
            
            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)
            
            events = await self.service.search_events_by_date_range(
                credentials,
                start_date=start_date,
                end_date=end_date
            )
            
            if not events:
                start_str = start_date.strftime("%B %d")
                end_str = end_date.strftime("%B %d")
                return {
                    "success": True,
                    "message": f"You have no events between {start_str} and {end_str}.",
                    "events": []
                }
            
            # Format voice-friendly response
            start_str = start_date.strftime("%B %d")
            end_str = end_date.strftime("%B %d")
            message = f"I found {len(events)} event"
            if len(events) > 1:
                message += "s"
            message += f" between {start_str} and {end_str}. "
            
            for i, event in enumerate(events[:5], 1):
                summary = event['summary']
                start = event['start']
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    time_str = start_dt.strftime("%B %d at %I:%M %p")
                except:
                    time_str = start
                
                message += f"Event {i}: {summary}, {time_str}. "
            
            if len(events) > 5:
                message += f"And {len(events) - 5} more."
            
            return {
                "success": True,
                "message": message,
                "events": events
            }
            
        except Exception as e:
            logger.error(f"Error searching events by date range: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I encountered an error: {str(e)}",
                "events": []
            }

    async def create_recurring_event(
        self,
        user_id: str,
        summary: str,
        start_time: datetime,
        duration_minutes: int,
        recurrence_pattern: str,
        count: Optional[int] = None,
        until_date: Optional[datetime] = None,
        description: str = "",
        timezone: str = "America/Los_Angeles"
    ) -> Dict[str, Any]:
        """Create a recurring calendar event
        
        Args:
            user_id: User identifier
            summary: Event title
            start_time: First occurrence start time
            duration_minutes: Event duration in minutes
            recurrence_pattern: Pattern like 'daily', 'weekly', 'monthly', or custom RRULE
            count: Number of occurrences (optional)
            until_date: End date for recurrence (optional)
            description: Event description
            timezone: Timezone for the event (default: America/Los_Angeles)
            
        Returns:
            Dictionary with success status and message
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first."
                }
            
            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)
            
            # Build RRULE from pattern
            rrule = self._build_rrule(recurrence_pattern, count, until_date, start_time)
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            event = await self.service.create_recurring_event(
                credentials,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                recurrence_rule=rrule,
                description=description,
                timezone=timezone
            )
            
            if not event:
                return {
                    "success": False,
                    "message": "Failed to create the recurring event."
                }
            
            time_str = start_time.strftime("%I:%M %p")
            pattern_desc = self._get_pattern_description(recurrence_pattern, count, until_date)
            
            message = f"I've created a recurring event called '{summary}' {pattern_desc} at {time_str}."
            event_link = event.get('link', '')
            if event_link:
                message += f" View it here: {event_link}"
            
            return {
                "success": True,
                "message": message,
                "event": event
            }
            
        except Exception as e:
            logger.error(f"Error creating recurring event: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I couldn't create the recurring event: {str(e)}"
            }
    
    def _build_rrule(self, pattern: str, count: Optional[int], until_date: Optional[datetime], start_time: datetime) -> str:
        """Build RRULE string from pattern and parameters"""
        pattern_lower = pattern.lower()
        
        # If it's already an RRULE, return it
        if pattern.upper().startswith('RRULE:'):
            return pattern.upper()
        
        # Build RRULE based on pattern
        if pattern_lower == 'daily':
            rrule = 'RRULE:FREQ=DAILY'
        elif pattern_lower == 'weekly':
            # Get day of week from start_time
            days = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
            day = days[start_time.weekday()]
            rrule = f'RRULE:FREQ=WEEKLY;BYDAY={day}'
        elif pattern_lower == 'monthly':
            rrule = 'RRULE:FREQ=MONTHLY'
        elif pattern_lower == 'weekdays':
            rrule = 'RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'
        elif pattern_lower == 'weekends':
            rrule = 'RRULE:FREQ=WEEKLY;BYDAY=SA,SU'
        else:
            # Default to weekly
            days = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
            day = days[start_time.weekday()]
            rrule = f'RRULE:FREQ=WEEKLY;BYDAY={day}'
        
        # Add count or until
        if count:
            rrule += f';COUNT={count}'
        elif until_date:
            # Format as YYYYMMDDTHHMMSSZ
            until_str = until_date.strftime('%Y%m%dT%H%M%SZ')
            rrule += f';UNTIL={until_str}'
        
        return rrule
    
    def _get_pattern_description(self, pattern: str, count: Optional[int], until_date: Optional[datetime]) -> str:
        """Get human-readable description of recurrence pattern"""
        pattern_lower = pattern.lower()
        
        if pattern_lower == 'daily':
            desc = 'every day'
        elif pattern_lower == 'weekly':
            desc = 'every week'
        elif pattern_lower == 'monthly':
            desc = 'every month'
        elif pattern_lower == 'weekdays':
            desc = 'every weekday'
        elif pattern_lower == 'weekends':
            desc = 'every weekend'
        else:
            desc = pattern_lower
        
        if count:
            desc += f' for {count} occurrences'
        elif until_date:
            until_str = until_date.strftime('%B %d')
            desc += f' until {until_str}'
        
        return desc

    async def check_availability(
        self,
        user_id: str,
        date: datetime,
        duration_minutes: int,
        working_hours_start: int = 9,
        working_hours_end: int = 18
    ) -> Dict[str, Any]:
        """Check availability and find free time slots
        
        Args:
            user_id: User identifier
            date: Date to check for availability
            duration_minutes: Required duration in minutes
            working_hours_start: Start of working hours (default 9 AM)
            working_hours_end: End of working hours (default 6 PM)
            
        Returns:
            Dictionary with success status and available slots
        """
        try:
            if not self.is_connected(user_id):
                return {
                    "success": False,
                    "message": "Calendar is not connected. Please connect your Google Calendar first.",
                    "slots": []
                }
            
            token_json = self.token_storage.get_token(user_id, "calendar")
            credentials = self.service.get_credentials_from_token(token_json)
            
            slots = await self.service.find_available_slots(
                credentials,
                date=date,
                duration_minutes=duration_minutes,
                working_hours_start=working_hours_start,
                working_hours_end=working_hours_end
            )
            
            if not slots:
                date_str = date.strftime("%A, %B %d")
                return {
                    "success": True,
                    "message": f"Sorry, I couldn't find any {duration_minutes}-minute slots available on {date_str}.",
                    "slots": []
                }
            
            # Format voice-friendly response
            date_str = date.strftime("%A, %B %d")
            message = f"I found {len(slots)} available time slot"
            if len(slots) > 1:
                message += "s"
            message += f" on {date_str} for a {duration_minutes}-minute meeting. "
            
            for i, slot in enumerate(slots[:3], 1):
                start_time = slot['start_time']
                time_str = start_time.strftime("%I:%M %p")
                message += f"Slot {i}: {time_str}. "
            
            if len(slots) > 3:
                message += f"And {len(slots) - 3} more options."
            
            return {
                "success": True,
                "message": message,
                "slots": slots
            }
            
        except Exception as e:
            logger.error(f"Error checking availability: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Sorry, I encountered an error: {str(e)}",
                "slots": []
            }

