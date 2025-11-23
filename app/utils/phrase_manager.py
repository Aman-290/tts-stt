"""Phrase Manager - Provides intermediate phrases during tool execution to reduce perceived latency."""
import random
from typing import Optional


class PhraseManager:
    """Manages intermediate phrases for voice agent tools."""
    
    # Phrase collections for each tool and stage
    PHRASES = {
        "gmail": {
            "searching": [
                "Let me check your inbox",
                "Searching through your emails now",
                "Looking for those messages",
                "Checking your Gmail"
            ],
            "creating_draft": [
                "I'm drafting that email for you",
                "Creating the draft now",
                "Writing that email",
                "Composing the draft"
            ],
            "sending": [
                "Sending that email now",
                "I'm sending it for you",
                "Sending the message",
                "Delivering your email"
            ],
            "checking_label": [
                "Let me check that for you",
                "Looking through those emails",
                "Checking that category",
                "Searching for those"
            ],
            "analyzing": [
                "Let me analyze your inbox",
                "Checking your unread emails",
                "Looking at your messages",
                "Analyzing your inbox"
            ],
            "searching_files": [
                "Searching for those files",
                "Looking for attachments",
                "Checking for files",
                "Searching your attachments"
            ]
        },
        "calendar": {
            "checking": [
                "Let me check your calendar",
                "Looking at your schedule",
                "Checking your upcoming events",
                "Reviewing your calendar"
            ],
            "creating": [
                "Creating that event for you",
                "Adding it to your calendar",
                "Scheduling that now",
                "Setting up the event"
            ],
            "getting_link": [
                "Getting the invite link",
                "Fetching the event link",
                "Retrieving the shareable link"
            ],
            "updating": [
                "Let me update that event for you",
                "Updating the event now",
                "Making those changes to your calendar",
                "Modifying that event"
            ],
            "searching_range": [
                "Searching your calendar",
                "Looking through your events",
                "Checking your schedule for that period",
                "Searching for events in that range"
            ],
            "creating_recurring": [
                "Setting up that recurring event",
                "Creating the recurring schedule",
                "Adding that to your calendar",
                "Scheduling the recurring event"
            ],
            "checking_availability": [
                "Let me check your schedule",
                "Looking for free time slots",
                "Checking your availability",
                "Finding open times for you"
            ]
        },
        "web_search": {
            "searching": [
                "I'm searching for that",
                "Let me look that up for you",
                "Searching the web now",
                "Looking for information on that"
            ],
            "summarizing": [
                "Now I'm summarizing the results",
                "Let me put this together for you",
                "Processing the information",
                "Analyzing what I found"
            ],
            "reading": [
                "Let me read that page for you",
                "Extracting the content now",
                "Reading the webpage",
                "Getting the information from that page"
            ]
        },
        "summarization": {
            "summarizing": [
                "Let me summarize that for you",
                "I'm creating a summary",
                "Analyzing the key points",
                "Extracting the important details"
            ],
            "processing": [
                "Processing the information",
                "Analyzing the content",
                "Looking for key insights",
                "Identifying the main points"
            ],
            "finalizing": [
                "Putting it all together",
                "Finalizing the summary",
                "Almost done with the summary",
                "Wrapping up the key points"
            ]
        }
    }
    
    def __init__(self):
        """Initialize the phrase manager."""
        # Track last used phrases to avoid immediate repetition
        self._last_phrases = {}
    
    def get_phrase(self, tool: str, stage: str, context: Optional[str] = None) -> str:
        """
        Get a random phrase for the given tool and stage.
        
        Args:
            tool: Tool name (gmail, calendar, web_search)
            stage: Stage name (searching, creating, summarizing, etc.)
            context: Optional context to inject into the phrase (e.g., search query)
            
        Returns:
            A random phrase appropriate for the tool and stage
        """
        # Get phrases for this tool and stage
        phrases = self.PHRASES.get(tool, {}).get(stage, [])
        
        if not phrases:
            # Fallback to generic phrase
            return "Let me help you with that"
        
        # Get the last used phrase for this tool+stage combination
        key = f"{tool}_{stage}"
        last_phrase = self._last_phrases.get(key)
        
        # Filter out the last used phrase if we have multiple options
        available_phrases = phrases
        if len(phrases) > 1 and last_phrase in phrases:
            available_phrases = [p for p in phrases if p != last_phrase]
        
        # Select a random phrase
        selected_phrase = random.choice(available_phrases)
        
        # Store for next time
        self._last_phrases[key] = selected_phrase
        
        # Inject context if provided and phrase supports it
        if context and "{query}" in selected_phrase:
            selected_phrase = selected_phrase.replace("{query}", context)
        
        return selected_phrase
    
    def get_multi_stage_phrases(self, tool: str, stages: list) -> list:
        """
        Get phrases for multiple stages.
        
        Args:
            tool: Tool name
            stages: List of stage names
            
        Returns:
            List of phrases, one for each stage
        """
        return [self.get_phrase(tool, stage) for stage in stages]


# Global instance
phrase_manager = PhraseManager()
