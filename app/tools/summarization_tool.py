"""Summarization tool wrapper for voice agent integration."""
import logging
from typing import Dict, List, Optional
from app.services.summarization_service import SummarizationService

logger = logging.getLogger(__name__)


class SummarizationTool:
    """Tool wrapper for summarization service."""
    
    def __init__(self):
        """Initialize the summarization tool."""
        self.service = SummarizationService()
        logger.info("SummarizationTool initialized")
    
    async def summarize_text(
        self, 
        text: str, 
        max_sentences: int = 5,
        use_textrank: bool = True
    ) -> Dict:
        """Summarize general text.
        
        Args:
            text: Text to summarize
            max_sentences: Maximum sentences in summary
            use_textrank: Use TextRank algorithm for better quality
            
        Returns:
            Dict with success status and message
        """
        try:
            result = self.service.summarize_text(
                text=text,
                max_sentences=max_sentences,
                use_textrank=use_textrank
            )
            
            if result["success"]:
                message = f"Summary ({result['summary_length']} of {result['original_length']} sentences):\n\n"
                message += result["summary"]
                
                return {
                    "success": True,
                    "message": message,
                    "summary": result["summary"],
                    "metadata": {
                        "original_length": result["original_length"],
                        "summary_length": result["summary_length"],
                        "compression_ratio": result["compression_ratio"]
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Could not generate summary. The text may be too short or empty.",
                    "summary": ""
                }
                
        except Exception as e:
            logger.error(f"Error in summarize_text: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error generating summary: {str(e)}",
                "summary": ""
            }
    
    async def summarize_gmail_results(self, emails: List[Dict]) -> Dict:
        """Summarize Gmail search results.
        
        Args:
            emails: List of email dicts from Gmail search
            
        Returns:
            Dict with success status and message
        """
        try:
            result = self.service.summarize_emails(emails, max_emails=10)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": result["summary"],
                    "count": result["count"]
                }
            else:
                return {
                    "success": False,
                    "message": result["summary"],
                    "count": 0
                }
                
        except Exception as e:
            logger.error(f"Error in summarize_gmail_results: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error summarizing emails: {str(e)}",
                "count": 0
            }
    
    async def summarize_calendar_events(self, events: List[Dict]) -> Dict:
        """Summarize calendar events.
        
        Args:
            events: List of event dicts from Calendar
            
        Returns:
            Dict with success status and message
        """
        try:
            result = self.service.summarize_events(events, max_events=10)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": result["summary"],
                    "count": result["count"]
                }
            else:
                return {
                    "success": False,
                    "message": result["summary"],
                    "count": 0
                }
                
        except Exception as e:
            logger.error(f"Error in summarize_calendar_events: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error summarizing events: {str(e)}",
                "count": 0
            }
    
    async def summarize_web_search_results(
        self, 
        results: List[Dict],
        query: str = ""
    ) -> Dict:
        """Summarize web search results.
        
        Args:
            results: List of search result dicts
            query: Original search query
            
        Returns:
            Dict with success status and message
        """
        try:
            result = self.service.summarize_web_results(results, query=query)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": result["summary"],
                    "count": result["count"],
                    "key_points": result.get("key_points", [])
                }
            else:
                return {
                    "success": False,
                    "message": result["summary"],
                    "count": 0
                }
                
        except Exception as e:
            logger.error(f"Error in summarize_web_search_results: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error summarizing search results: {str(e)}",
                "count": 0
            }
    
    async def extract_key_points(self, text: str, num_points: int = 3) -> Dict:
        """Extract key bullet points from text.
        
        Args:
            text: Text to extract points from
            num_points: Number of key points to extract
            
        Returns:
            Dict with success status and message
        """
        try:
            key_points = self.service.extract_key_points(text, num_points=num_points)
            
            if key_points:
                message = f"Key points:\n"
                for i, point in enumerate(key_points, 1):
                    message += f"{i}. {point}\n"
                
                return {
                    "success": True,
                    "message": message,
                    "key_points": key_points
                }
            else:
                return {
                    "success": False,
                    "message": "Could not extract key points from the text.",
                    "key_points": []
                }
                
        except Exception as e:
            logger.error(f"Error in extract_key_points: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error extracting key points: {str(e)}",
                "key_points": []
            }
