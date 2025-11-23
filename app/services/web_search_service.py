"""Web search service using Tavily Search API and Jina AI Reader for content extraction."""
import os
import logging
from typing import Dict, List, Optional
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

class WebSearchService:
    """Service for web search and content extraction."""
    
    def __init__(self):
        """Initialize the web search service."""
        self.settings = get_settings()
        self.tavily_api_key = self.settings.tavily_api_key
        self.tavily_api_url = "https://api.tavily.com/search"
        self.jina_reader_base = "https://r.jina.ai/"
        
        # HTTP client configuration
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        
        logger.info("WebSearchService initialized with Tavily")
    
    def is_configured(self) -> bool:
        """Check if Tavily Search API key is configured."""
        return bool(self.tavily_api_key)
    
    async def search_web(self, query: str, num_results: int = 5) -> Dict:
        """
        Search the web using Tavily Search API.
        
        Args:
            query: Search query string
            num_results: Number of results to return (default 5, max 10)
            
        Returns:
            Dict with success status, results list, and message
        """
        if not self.is_configured():
            return {
                "success": False,
                "message": "Web search is not configured. Please add TAVILY_API_KEY to your environment variables.",
                "results": []
            }
        
        try:
            logger.info(f"Searching web with Tavily for: {query} (limit: {num_results})")
            
            # Tavily Search API payload
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "max_results": min(num_results, 3),  # Max 10 results
                "search_depth": "basic",  # or "advanced" for deeper search
                "include_answer": True,  # Get AI-generated answer
                "include_raw_content": False,  # We'll use Jina for content
                "include_images": False
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.tavily_api_url,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            # Parse results
            results = []
            tavily_results = data.get("results", [])
            
            for item in tavily_results[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("content", ""),  # Tavily provides clean content
                    "score": item.get("score", 0),  # Relevance score
                })
            
            if not results:
                return {
                    "success": True,
                    "message": f"No results found for '{query}'.",
                    "results": [],
                    "answer": data.get("answer", "")
                }
            
            # Format message for voice response
            message = ""
            
            # Include Tavily's AI-generated answer if available
            if data.get("answer"):
                message += f"Quick answer: {data['answer']}\n\n"
            
            message += f"Found {len(results)} results for '{query}':\n\n"
            for i, result in enumerate(results, 1):
                message += f"{i}. {result['title']}\n"
                message += f"   {result['description'][:200]}...\n"
                message += f"   URL: {result['url']}\n\n"
            
            logger.info(f"Successfully retrieved {len(results)} search results from Tavily")
            
            return {
                "success": True,
                "message": message,
                "results": results,
                "query": query,
                "answer": data.get("answer", "")  # AI-generated answer
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Tavily Search API error: {e.response.status_code} - {e.response.text}")
            error_msg = f"Search failed: API returned error {e.response.status_code}"
            
            # Handle specific error codes
            if e.response.status_code == 429:
                error_msg = "Rate limit exceeded. You've used your monthly search quota. Please upgrade your plan or wait until next month."
            elif e.response.status_code == 400:
                error_msg = "Search query is too long or invalid. Please try a shorter, simpler query."
            
            return {
                "success": False,
                "message": error_msg,
                "results": []
            }
        except httpx.TimeoutException:
            logger.error("Tavily Search API timeout")
            return {
                "success": False,
                "message": "Search request timed out. Please try again.",
                "results": []
            }
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Search failed: {str(e)}",
                "results": []
            }
    
    async def read_webpage(self, url: str) -> Dict:
        """
        Extract and read content from a webpage using Jina AI Reader.
        
        Args:
            url: URL of the webpage to read
            
        Returns:
            Dict with success status, content, and message
        """
        try:
            logger.info(f"Reading webpage: {url}")
            
            # Jina AI Reader - prepend r.jina.ai to the URL
            jina_url = f"{self.jina_reader_base}{url}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(jina_url)
                response.raise_for_status()
                content = response.text
            
            if not content or len(content) < 50:
                return {
                    "success": False,
                    "message": f"Could not extract meaningful content from {url}",
                    "content": ""
                }
            
            # Limit content length to prevent API errors (max 15k chars per page)
            max_content_length = 15000
            if len(content) > max_content_length:
                content = content[:max_content_length]
                logger.info(f"Truncated content from {len(content)} to {max_content_length} characters")
            
            # Truncate very long content for voice response
            max_display_length = 500
            truncated = len(content) > max_display_length
            display_content = content[:max_display_length] + "..." if truncated else content
            
            message = f"Successfully read content from {url}.\n\n"
            message += f"Content preview:\n{display_content}\n"
            if truncated:
                message += f"\n(Content truncated for voice - full length: {len(content)} characters)"
            
            logger.info(f"Successfully extracted {len(content)} characters from {url}")
            
            return {
                "success": True,
                "message": message,
                "content": content,
                "url": url,
                "length": len(content)
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to read webpage {url}: {e.response.status_code}")
            error_msg = f"Could not read webpage: HTTP {e.response.status_code}"
            if e.response.status_code == 429:
                error_msg = "Rate limit exceeded. Please try again in a moment."
            return {
                "success": False,
                "message": error_msg,
                "content": ""
            }
        except Exception as e:
            logger.error(f"Failed to read webpage {url}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Could not read webpage: {str(e)}",
                "content": ""
            }
    
    async def read_multiple_pages(self, urls: List[str], max_pages: int = 10) -> Dict:
        """
        Extract content from multiple webpages.
        
        Args:
            urls: List of URLs to read
            max_pages: Maximum number of pages to process (default 10)
            
        Returns:
            Dict with success status, list of page contents, and message
        """
        try:
            urls = urls[:max_pages]  # Limit to max_pages
            logger.info(f"Reading {len(urls)} webpages")
            
            pages = []
            successful = 0
            failed = 0
            
            for url in urls:
                result = await self.read_webpage(url)
                if result["success"]:
                    pages.append({
                        "url": url,
                        "content": result["content"],
                        "length": result["length"]
                    })
                    successful += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to read {url}")
            
            if not pages:
                return {
                    "success": False,
                    "message": "Could not read any of the provided webpages.",
                    "pages": []
                }
            
            message = f"Successfully read {successful} out of {len(urls)} pages"
            if failed > 0:
                message += f" ({failed} failed)"
            message += "."
            
            return {
                "success": True,
                "message": message,
                "pages": pages,
                "successful": successful,
                "failed": failed
            }
            
        except Exception as e:
            logger.error(f"Failed to read multiple pages: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to read pages: {str(e)}",
                "pages": []
            }
    
    async def summarize_pages(self, urls: List[str], focus: Optional[str] = None) -> Dict:
        """
        Extract content from multiple pages and prepare for summarization.
        
        Args:
            urls: List of URLs to summarize
            focus: Optional focus area for summarization (e.g., "pricing", "features")
            
        Returns:
            Dict with combined content ready for LLM summarization
        """
        try:
            logger.info(f"Preparing to summarize {len(urls)} pages")
            
            # Read all pages
            result = await self.read_multiple_pages(urls, max_pages=10)
            
            if not result["success"] or not result["pages"]:
                return {
                    "success": False,
                    "message": "Could not extract content for summarization.",
                    "combined_content": ""
                }
            
            # Combine content from all pages with length limits
            combined_content = ""
            max_total_length = 30000  # Limit total content to prevent Claude API errors
            current_length = 0
            
            for i, page in enumerate(result["pages"], 1):
                page_content = page["content"]
                # Limit each page to 10k characters
                if len(page_content) > 10000:
                    page_content = page_content[:10000] + "...[truncated]"
                
                # Check if adding this page would exceed total limit
                if current_length + len(page_content) > max_total_length:
                    logger.warning(f"Reached content limit, stopping at page {i-1}")
                    break
                
                combined_content += f"\n\n--- Page {i}: {page['url']} ---\n\n"
                combined_content += page_content
                current_length += len(page_content)
            
            # Create summarization prompt
            focus_instruction = f" Focus on: {focus}." if focus else ""
            summary_prompt = f"""Please summarize the following content from {len(result['pages'])} web pages.{focus_instruction}

{combined_content}

Provide a concise summary that captures the key information from all sources."""
            
            message = f"Extracted content from {len(result['pages'])} pages. Ready for summarization."
            
            return {
                "success": True,
                "message": message,
                "combined_content": combined_content,
                "summary_prompt": summary_prompt,
                "num_pages": len(result["pages"]),
                "total_length": current_length
            }
            
        except Exception as e:
            logger.error(f"Failed to prepare summarization: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to prepare summarization: {str(e)}",
                "combined_content": ""
            }
