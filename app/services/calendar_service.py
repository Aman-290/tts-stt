"""Google Calendar Service - OAuth and Calendar Operations"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional, List, Dict
import json
from datetime import datetime, timedelta
from app.utils.logger import get_logger
from app.config import get_settings

# Relax OAuth scope validation to allow shared OAuth clients
# This allows the same OAuth client to be used for both Gmail and Calendar
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

logger = get_logger()

class CalendarService:
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]

    def __init__(self):
        settings = get_settings()
        self.client_id = settings.calendar_client_id
        self.client_secret = settings.calendar_client_secret
        self.redirect_uri = settings.calendar_redirect_uri
        self._oauth_states: Dict[str, str] = {}

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
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        self._oauth_states[user_id] = state
        logger.info(f"Generated Calendar auth URL for user {user_id}")
        return authorization_url

    async def handle_oauth_callback(self, code: str, state: str, user_id: str) -> str:
        """Handle OAuth callback and return token JSON with state validation"""
        if user_id not in self._oauth_states:
            raise ValueError("OAuth state not found. Please restart the authorization flow.")

        if self._oauth_states[user_id] != state:
            del self._oauth_states[user_id]
            raise ValueError("Invalid OAuth state. Possible CSRF attack.")

        del self._oauth_states[user_id]

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

        flow.fetch_token(code=code)

        credentials = flow.credentials

        if credentials.refresh_token:
            logger.info(f"Successfully obtained refresh_token for user {user_id}")
        else:
            logger.warning(f"No refresh_token received for user {user_id}")

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
        """Get credentials from stored token and refresh if needed"""
        token_data = json.loads(token)
        credentials = Credentials.from_authorized_user_info(token_data)

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logger.info("Successfully refreshed expired Calendar credentials")
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}", exc_info=True)
                raise ValueError("Calendar credentials expired and could not be refreshed.")

        return credentials

    def validate_credentials(self, credentials: Credentials) -> bool:
        """Validate credentials"""
        try:
            if not credentials.token:
                return False
            if credentials.expired and not credentials.refresh_token:
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating credentials: {e}")
            return False

    def build_service(self, credentials: Credentials):
        """Build Calendar service from credentials"""
        return build('calendar', 'v3', credentials=credentials)

    async def list_events(
        self,
        credentials: Credentials,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """List calendar events"""
        try:
            service = self.build_service(credentials)

            if not time_min:
                time_min = datetime.utcnow()
            if not time_max:
                time_max = time_min + timedelta(days=7)

            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            event_list = []

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({
                    "id": event['id'],
                    "summary": event.get('summary', 'No title'),
                    "start": start,
                    "end": event['end'].get('dateTime', event['end'].get('date')),
                    "description": event.get('description', ''),
                    "location": event.get('location', ''),
                    "link": event.get('htmlLink', ''),
                    "invite_link": event.get('htmlLink', '')
                })

            return event_list
        except HttpError as e:
            logger.error(f"Error listing events: {e}", exc_info=True)
            return []

    async def create_event(
        self,
        credentials: Credentials,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        location: str = "",
        timezone: str = "America/Los_Angeles"
    ) -> Optional[Dict]:
        """Create a calendar event

        Args:
            credentials: Google Calendar credentials
            summary: Event title
            start_time: Event start time (naive or timezone-aware datetime)
            end_time: Event end time (naive or timezone-aware datetime)
            description: Event description
            location: Event location
            timezone: Timezone for the event (default: America/Los_Angeles)
        """
        try:
            service = self.build_service(credentials)

            # If datetime is naive (no timezone), treat it as local time in specified timezone
            # If datetime is timezone-aware, convert to ISO with timezone
            if start_time.tzinfo is None:
                # Naive datetime - use specified timezone
                start_dt_str = start_time.isoformat()
                end_dt_str = end_time.isoformat()
                logger.info(f"Creating event with naive datetime. Using timezone: {timezone}")
            else:
                # Timezone-aware datetime - use its timezone
                start_dt_str = start_time.isoformat()
                end_dt_str = end_time.isoformat()
                timezone = str(start_time.tzinfo)
                logger.info(f"Creating event with timezone-aware datetime: {timezone}")

            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_dt_str,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_dt_str,
                    'timeZone': timezone,
                },
            }

            logger.info(f"Creating event with payload: {event}")

            created_event = service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            logger.info(f"✅ Successfully created event: {created_event.get('id')} - {created_event.get('htmlLink')}")
            return {
                "id": created_event['id'],
                "summary": created_event.get('summary'),
                "start": created_event['start'].get('dateTime'),
                "link": created_event.get('htmlLink')
            }
        except HttpError as e:
            logger.error(f"❌ HTTP Error creating event: {e}", exc_info=True)
            logger.error(f"Error details: {e.resp.status} - {e.content}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error creating event: {e}", exc_info=True)
            return None

    async def update_event(
        self,
        credentials: Credentials,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone: str = "America/Los_Angeles"
    ) -> Optional[Dict]:
        """Update a calendar event
        
        Args:
            credentials: Google Calendar credentials
            event_id: ID of the event to update
            summary: New event title (optional)
            start_time: New start time (optional)
            end_time: New end time (optional)
            description: New description (optional)
            location: New location (optional)
            timezone: Timezone for the event (default: America/Los_Angeles)
        """
        try:
            service = self.build_service(credentials)

            # Get existing event
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()

            # Update fields only if provided
            if summary:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            if start_time:
                # Handle timezone-aware and naive datetimes
                if start_time.tzinfo is None:
                    start_dt_str = start_time.isoformat()
                else:
                    start_dt_str = start_time.isoformat()
                    timezone = str(start_time.tzinfo)
                event['start'] = {'dateTime': start_dt_str, 'timeZone': timezone}
            if end_time:
                if end_time.tzinfo is None:
                    end_dt_str = end_time.isoformat()
                else:
                    end_dt_str = end_time.isoformat()
                    timezone = str(end_time.tzinfo)
                event['end'] = {'dateTime': end_dt_str, 'timeZone': timezone}

            updated_event = service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event
            ).execute()

            logger.info(f"✅ Updated event: {event_id}")
            return {
                "id": updated_event['id'],
                "summary": updated_event.get('summary'),
                "start": updated_event['start'].get('dateTime'),
                "link": updated_event.get('htmlLink')
            }
        except HttpError as e:
            logger.error(f"❌ Error updating event: {e}", exc_info=True)
            return None

    async def delete_event(self, credentials: Credentials, event_id: str) -> bool:
        """Delete a calendar event"""
        try:
            service = self.build_service(credentials)
            service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            logger.info(f"Deleted event: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Error deleting event: {e}", exc_info=True)
            return False

    async def get_event_link(self, credentials: Credentials, event_id: str) -> Optional[str]:
        """Get shareable invite link for a specific event
        
        Args:
            credentials: Google Calendar credentials
            event_id: ID of the event
            
        Returns:
            Shareable htmlLink for the event, or None if not found
        """
        try:
            service = self.build_service(credentials)
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            link = event.get('htmlLink', '')
            logger.info(f"Retrieved invite link for event {event_id}: {link}")
            return link
        except HttpError as e:
            logger.error(f"Error getting event link: {e}", exc_info=True)
            return None

    async def search_events_by_date_range(
        self,
        credentials: Credentials,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 50
    ) -> List[Dict]:
        """Search for events within a specific date range
        
        Args:
            credentials: Google Calendar credentials
            start_date: Start of the date range
            end_date: End of the date range
            max_results: Maximum number of events to return (default 50)
            
        Returns:
            List of events in the date range
        """
        try:
            service = self.build_service(credentials)

            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z' if start_date.tzinfo is None else start_date.isoformat(),
                timeMax=end_date.isoformat() + 'Z' if end_date.tzinfo is None else end_date.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            event_list = []

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({
                    "id": event['id'],
                    "summary": event.get('summary', 'No title'),
                    "start": start,
                    "end": event['end'].get('dateTime', event['end'].get('date')),
                    "description": event.get('description', ''),
                    "location": event.get('location', ''),
                    "link": event.get('htmlLink', '')
                })

            logger.info(f"Found {len(event_list)} events between {start_date} and {end_date}")
            return event_list
        except HttpError as e:
            logger.error(f"Error searching events by date range: {e}", exc_info=True)
            return []

    async def create_recurring_event(
        self,
        credentials: Credentials,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        recurrence_rule: str,
        description: str = "",
        location: str = "",
        timezone: str = "America/Los_Angeles"
    ) -> Optional[Dict]:
        """Create a recurring calendar event
        
        Args:
            credentials: Google Calendar credentials
            summary: Event title
            start_time: First occurrence start time
            end_time: First occurrence end time
            recurrence_rule: RRULE string (e.g., 'RRULE:FREQ=DAILY;COUNT=10' or 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR')
            description: Event description
            location: Event location
            timezone: Timezone for the event (default: America/Los_Angeles)
            
        Returns:
            Created event details or None if failed
        """
        try:
            service = self.build_service(credentials)

            # Handle timezone-aware and naive datetimes
            if start_time.tzinfo is None:
                start_dt_str = start_time.isoformat()
                end_dt_str = end_time.isoformat()
            else:
                start_dt_str = start_time.isoformat()
                end_dt_str = end_time.isoformat()
                timezone = str(start_time.tzinfo)

            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_dt_str,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_dt_str,
                    'timeZone': timezone,
                },
                'recurrence': [
                    recurrence_rule
                ]
            }

            logger.info(f"Creating recurring event with payload: {event}")

            created_event = service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            logger.info(f"✅ Successfully created recurring event: {created_event.get('id')}")
            return {
                "id": created_event['id'],
                "summary": created_event.get('summary'),
                "start": created_event['start'].get('dateTime'),
                "recurrence": created_event.get('recurrence', []),
                "link": created_event.get('htmlLink')
            }
        except HttpError as e:
            logger.error(f"❌ HTTP Error creating recurring event: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error creating recurring event: {e}", exc_info=True)
            return None

    async def find_available_slots(
        self,
        credentials: Credentials,
        date: datetime,
        duration_minutes: int,
        working_hours_start: int = 9,
        working_hours_end: int = 18,
        max_slots: int = 5
    ) -> List[Dict]:
        """Find available time slots on a specific date
        
        Args:
            credentials: Google Calendar credentials
            date: Date to check for availability
            duration_minutes: Required duration in minutes
            working_hours_start: Start of working hours (default 9 AM)
            working_hours_end: End of working hours (default 6 PM)
            max_slots: Maximum number of slots to return (default 5)
            
        Returns:
            List of available time slots with start and end times
        """
        try:
            service = self.build_service(credentials)

            # Set time range for the specific date
            day_start = date.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
            day_end = date.replace(hour=working_hours_end, minute=0, second=0, microsecond=0)

            # Get all events for the day
            events_result = service.events().list(
                calendarId='primary',
                timeMin=day_start.isoformat() + 'Z' if day_start.tzinfo is None else day_start.isoformat(),
                timeMax=day_end.isoformat() + 'Z' if day_end.tzinfo is None else day_end.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Build list of busy periods
            busy_periods = []
            for event in events:
                start_str = event['start'].get('dateTime', event['start'].get('date'))
                end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                try:
                    start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    busy_periods.append((start, end))
                except:
                    continue

            # Find free slots
            free_slots = []
            current_time = day_start
            duration_delta = timedelta(minutes=duration_minutes)

            while current_time + duration_delta <= day_end and len(free_slots) < max_slots:
                slot_end = current_time + duration_delta
                
                # Check if this slot overlaps with any busy period
                is_free = True
                for busy_start, busy_end in busy_periods:
                    # Check for overlap
                    if not (slot_end <= busy_start or current_time >= busy_end):
                        is_free = False
                        # Jump to end of this busy period
                        current_time = busy_end
                        break
                
                if is_free:
                    free_slots.append({
                        "start": current_time.isoformat(),
                        "end": slot_end.isoformat(),
                        "start_time": current_time,
                        "end_time": slot_end
                    })
                    # Move to next potential slot (15-minute increments)
                    current_time += timedelta(minutes=15)
                
            logger.info(f"Found {len(free_slots)} available slots on {date.date()}")
            return free_slots
        except HttpError as e:
            logger.error(f"Error finding available slots: {e}", exc_info=True)
            return []
