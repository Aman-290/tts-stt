"""Web search tool for voice agent integration."""
import logging
from typing import Dict, List, Optional
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)

class WebSearchTool:
    """Tool wrapper for web search functionality."""
    
    def __init__(self):
        """Initialize the web search tool."""
        self.service = WebSearchService()
        logger.info("WebSearchTool initialized")
    
    def is_configured(self) -> bool:
        """Check if web search is properly configured."""
        return self.service.is_configured()
    
    def get_configuration_instructions(self) -> str:
        """Get instructions for configuring web search."""
        return """To enable web search capabilities, you need to:

1. Sign up for a Tavily API key at https://tavily.com
   - Free tier: 1,000 searches per month (no credit card required)
   - Pay as you go: $0.008 per credit
   - Project plan: $30/month for 4,000 credits

2. Add your API key to the .env file:
   TAVILY_API_KEY=your_api_key_here

3. Restart the voice agent

Once configured, I'll be able to search the web, read webpages, and summarize content for you!"""
    
    async def search_web(self, query: str, num_results: int = 5) -> Dict:
        """
        Search the web for information.
        
        Args:
            query: Search query
            num_results: Number of results to return (default 5)
            
        Returns:
            Dict with success status and formatted message
        """
        if not self.is_configured():
            return {
                "success": False,
                "message": "Web search is not configured. " + self.get_configuration_instructions()
            }
        
        try:
            result = await self.service.search_web(query, num_results)
            return result
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Search failed: {str(e)}"
            }
    
    async def read_webpage(self, url: str) -> Dict:
        """
        Read and extract content from a webpage.
        
        Args:
            url: URL of the webpage to read
            
        Returns:
            Dict with success status and content
        """
        try:
            result = await self.service.read_webpage(url)
            return result
        except Exception as e:
            logger.error(f"Failed to read webpage: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to read webpage: {str(e)}"
            }
    
    async def read_multiple_pages(self, urls: List[str]) -> Dict:
        """
        Read content from multiple webpages.
        
        Args:
            urls: List of URLs to read
            
        Returns:
            Dict with success status and page contents
        """
        try:
            result = await self.service.read_multiple_pages(urls)
            return result
        except Exception as e:
            logger.error(f"Failed to read multiple pages: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to read pages: {str(e)}"
            }
    
    async def summarize_webpages(self, urls: List[str], focus: Optional[str] = None) -> Dict:
        """
        Extract and prepare content from multiple webpages for summarization.
        
        Args:
            urls: List of URLs to summarize
            focus: Optional focus area for summarization
            
        Returns:
            Dict with combined content and summary prompt
        """
        try:
            result = await self.service.summarize_pages(urls, focus)
            return result
        except Exception as e:
            logger.error(f"Failed to prepare summarization: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to prepare summarization: {str(e)}"
            }
    
    async def search_and_summarize(self, query: str, num_results: int = 5, focus: Optional[str] = None) -> Dict:
        """
        Search the web and summarize the top results.
        
        This is a convenience method that combines search and summarization.
        
        Args:
            query: Search query
            num_results: Number of results to summarize (default 5)
            focus: Optional focus area for summarization
            
        Returns:
            Dict with summary prompt ready for LLM
        """
        if not self.is_configured():
            return {
                "success": False,
                "message": "Web search is not configured. " + self.get_configuration_instructions()
            }
        
        try:
            # First, search the web
            search_result = await self.service.search_web(query, num_results)
            
            if not search_result["success"] or not search_result.get("results"):
                return {
                    "success": False,
                    "message": f"Could not find results for '{query}'"
                }
            
            # Extract URLs from search results
            urls = [result["url"] for result in search_result["results"]]
            
            # Summarize the pages
            summary_result = await self.service.summarize_pages(urls, focus)
            
            if not summary_result["success"]:
                return summary_result
            
            # Return the summary prompt for the LLM
            return {
                "success": True,
                "message": f"Found and extracted content from {summary_result['num_pages']} pages for '{query}'.",
                "summary_prompt": summary_result["summary_prompt"],
                "num_pages": summary_result["num_pages"]
            }
            
        except Exception as e:
            logger.error(f"Search and summarize failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to search and summarize: {str(e)}"
            }
