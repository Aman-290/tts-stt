"""Fast extractive text summarization service without LLM dependencies.

Uses a hybrid approach combining:
1. Frequency-based scoring (TF-IDF style) for keyword importance
2. TextRank (graph-based) for sentence importance
3. Position weighting (first/last sentences often more important)
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from collections import Counter, defaultdict
import math

logger = logging.getLogger(__name__)


class SummarizationService:
    """Fast extractive summarization service."""
    
    def __init__(self):
        """Initialize the summarization service."""
        # Common stop words to filter out
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have',
            'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how'
        }
        
        logger.info("SummarizationService initialized")
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:\-]', '', text)
        return text.strip()
    
    def _tokenize_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence tokenization
        sentences = re.split(r'[.!?]+', text)
        # Clean and filter empty sentences
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        return sentences
    
    def _tokenize_words(self, text: str) -> List[str]:
        """Split text into words and filter stop words."""
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter stop words and very short words
        words = [w for w in words if w not in self.stop_words and len(w) > 2]
        return words
    
    def _calculate_word_frequencies(self, sentences: List[str]) -> Dict[str, float]:
        """Calculate word frequencies across all sentences (TF-IDF style)."""
        word_freq = Counter()
        
        for sentence in sentences:
            words = self._tokenize_words(sentence)
            word_freq.update(words)
        
        # Normalize frequencies
        max_freq = max(word_freq.values()) if word_freq else 1
        word_freq = {word: freq / max_freq for word, freq in word_freq.items()}
        
        return word_freq
    
    def _score_sentences(
        self, 
        sentences: List[str], 
        word_freq: Dict[str, float]
    ) -> List[Tuple[int, float, str]]:
        """Score sentences based on word frequencies and position.
        
        Returns:
            List of tuples (index, score, sentence)
        """
        scored_sentences = []
        
        for idx, sentence in enumerate(sentences):
            words = self._tokenize_words(sentence)
            
            # Base score: sum of word frequencies
            word_score = sum(word_freq.get(word, 0) for word in words)
            
            # Normalize by sentence length to avoid bias toward long sentences
            sentence_score = word_score / len(words) if words else 0
            
            # Position weighting: first and last sentences are often important
            position_weight = 1.0
            if idx == 0:  # First sentence
                position_weight = 1.3
            elif idx == len(sentences) - 1:  # Last sentence
                position_weight = 1.2
            elif idx < 3:  # Early sentences
                position_weight = 1.1
            
            final_score = sentence_score * position_weight
            
            scored_sentences.append((idx, final_score, sentence))
        
        return scored_sentences
    
    def _calculate_sentence_similarity(self, sent1: str, sent2: str, word_freq: Dict[str, float]) -> float:
        """Calculate similarity between two sentences (for TextRank)."""
        words1 = set(self._tokenize_words(sent1))
        words2 = set(self._tokenize_words(sent2))
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity with word frequency weighting
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        # Weight by word importance
        weighted_intersection = sum(word_freq.get(w, 0) for w in intersection)
        weighted_union = sum(word_freq.get(w, 0) for w in union)
        
        return weighted_intersection / weighted_union if weighted_union > 0 else 0.0
    
    def _textrank_scores(self, sentences: List[str], word_freq: Dict[str, float], iterations: int = 10) -> List[float]:
        """Calculate TextRank scores for sentences."""
        n = len(sentences)
        if n == 0:
            return []
        
        # Build similarity matrix
        similarity_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._calculate_sentence_similarity(sentences[i], sentences[j], word_freq)
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim
        
        # Initialize scores
        scores = [1.0] * n
        damping = 0.85
        
        # Iterate to converge
        for _ in range(iterations):
            new_scores = [0.0] * n
            for i in range(n):
                rank_sum = 0.0
                for j in range(n):
                    if i != j and similarity_matrix[i][j] > 0:
                        # Sum of similarities from j to all other nodes
                        total_sim = sum(similarity_matrix[j][k] for k in range(n) if k != j)
                        if total_sim > 0:
                            rank_sum += (similarity_matrix[i][j] / total_sim) * scores[j]
                
                new_scores[i] = (1 - damping) + damping * rank_sum
            
            scores = new_scores
        
        return scores
    
    def summarize_text(
        self, 
        text: str, 
        max_sentences: int = 5,
        compression_ratio: float = 0.3,
        use_textrank: bool = True
    ) -> Dict:
        """Summarize text using extractive summarization.
        
        Args:
            text: Input text to summarize
            max_sentences: Maximum number of sentences in summary
            compression_ratio: Target compression ratio (0.0-1.0)
            use_textrank: Whether to use TextRank algorithm (slower but better)
            
        Returns:
            Dict with summary, key_sentences, and metadata
        """
        try:
            # Clean and tokenize
            text = self._clean_text(text)
            sentences = self._tokenize_sentences(text)
            
            if not sentences:
                return {
                    "success": False,
                    "summary": "",
                    "key_sentences": [],
                    "original_length": 0,
                    "summary_length": 0
                }
            
            # If text is already short, return as-is
            if len(sentences) <= max_sentences:
                summary = '. '.join(sentences) + '.'
                return {
                    "success": True,
                    "summary": summary,
                    "key_sentences": sentences,
                    "original_length": len(sentences),
                    "summary_length": len(sentences),
                    "compression_ratio": 1.0
                }
            
            # Calculate word frequencies
            word_freq = self._calculate_word_frequencies(sentences)
            
            # Determine number of sentences to extract
            target_sentences = max(
                1,
                min(
                    max_sentences,
                    int(len(sentences) * compression_ratio)
                )
            )
            
            if use_textrank:
                # Use TextRank for better quality
                textrank_scores = self._textrank_scores(sentences, word_freq)
                
                # Combine TextRank with frequency-based scoring
                freq_scores = self._score_sentences(sentences, word_freq)
                
                # Combine scores (60% TextRank, 40% frequency)
                combined_scores = []
                for idx, (_, freq_score, sentence) in enumerate(freq_scores):
                    combined_score = 0.6 * textrank_scores[idx] + 0.4 * freq_score
                    combined_scores.append((idx, combined_score, sentence))
            else:
                # Use frequency-based scoring only (faster)
                combined_scores = self._score_sentences(sentences, word_freq)
            
            # Sort by score and take top N
            top_sentences = sorted(combined_scores, key=lambda x: x[1], reverse=True)[:target_sentences]
            
            # Sort by original position to maintain coherence
            top_sentences = sorted(top_sentences, key=lambda x: x[0])
            
            # Extract sentences
            key_sentences = [sent for _, _, sent in top_sentences]
            summary = '. '.join(key_sentences) + '.'
            
            return {
                "success": True,
                "summary": summary,
                "key_sentences": key_sentences,
                "original_length": len(sentences),
                "summary_length": len(key_sentences),
                "compression_ratio": len(key_sentences) / len(sentences)
            }
            
        except Exception as e:
            logger.error(f"Error in summarize_text: {e}", exc_info=True)
            return {
                "success": False,
                "summary": "",
                "key_sentences": [],
                "error": str(e)
            }
    
    def extract_key_points(self, text: str, num_points: int = 3) -> List[str]:
        """Extract key bullet points from text.
        
        Args:
            text: Input text
            num_points: Number of key points to extract
            
        Returns:
            List of key point strings
        """
        result = self.summarize_text(text, max_sentences=num_points, use_textrank=False)
        if result["success"]:
            return result["key_sentences"]
        return []
    
    def summarize_emails(self, emails: List[Dict], max_emails: int = 5) -> Dict:
        """Summarize a list of emails.
        
        Args:
            emails: List of email dicts with 'from', 'subject', 'date' keys
            max_emails: Maximum number of emails to include in summary
            
        Returns:
            Dict with summary and metadata
        """
        try:
            if not emails:
                return {
                    "success": False,
                    "summary": "No emails to summarize.",
                    "count": 0
                }
            
            # Limit to max_emails
            emails = emails[:max_emails]
            
            # Extract key information
            summary_parts = []
            summary_parts.append(f"You have {len(emails)} email(s):")
            
            for i, email in enumerate(emails, 1):
                sender = email.get('from', 'Unknown sender')
                # Extract just the name or email (before <)
                if '<' in sender:
                    sender = sender.split('<')[0].strip()
                
                subject = email.get('subject', 'No subject')
                date = email.get('date', '')
                
                summary_parts.append(f"{i}. From {sender}: {subject}")
            
            summary = '\n'.join(summary_parts)
            
            return {
                "success": True,
                "summary": summary,
                "count": len(emails),
                "emails": emails
            }
            
        except Exception as e:
            logger.error(f"Error in summarize_emails: {e}", exc_info=True)
            return {
                "success": False,
                "summary": f"Error summarizing emails: {str(e)}",
                "count": 0
            }
    
    def summarize_events(self, events: List[Dict], max_events: int = 10) -> Dict:
        """Summarize calendar events.
        
        Args:
            events: List of event dicts with 'summary', 'start', 'end' keys
            max_events: Maximum number of events to include
            
        Returns:
            Dict with summary and metadata
        """
        try:
            if not events:
                return {
                    "success": False,
                    "summary": "No events to summarize.",
                    "count": 0
                }
            
            # Limit to max_events
            events = events[:max_events]
            
            summary_parts = []
            summary_parts.append(f"You have {len(events)} upcoming event(s):")
            
            for i, event in enumerate(events, 1):
                title = event.get('summary', 'Untitled event')
                start = event.get('start', '')
                location = event.get('location', '')
                
                event_line = f"{i}. {title}"
                if start:
                    event_line += f" at {start}"
                if location:
                    event_line += f" ({location})"
                
                summary_parts.append(event_line)
            
            summary = '\n'.join(summary_parts)
            
            return {
                "success": True,
                "summary": summary,
                "count": len(events),
                "events": events
            }
            
        except Exception as e:
            logger.error(f"Error in summarize_events: {e}", exc_info=True)
            return {
                "success": False,
                "summary": f"Error summarizing events: {str(e)}",
                "count": 0
            }
    
    def summarize_web_results(self, results: List[Dict], query: str = "") -> Dict:
        """Summarize web search results.
        
        Args:
            results: List of search result dicts with 'title', 'description', 'url' keys
            query: Original search query
            
        Returns:
            Dict with summary and metadata
        """
        try:
            if not results:
                return {
                    "success": False,
                    "summary": "No search results to summarize.",
                    "count": 0
                }
            
            # Combine all descriptions for summarization
            combined_text = ""
            for result in results:
                title = result.get('title', '')
                description = result.get('description', '')
                combined_text += f"{title}. {description}. "
            
            # Summarize the combined text
            summary_result = self.summarize_text(
                combined_text,
                max_sentences=5,
                compression_ratio=0.4,
                use_textrank=True
            )
            
            if not summary_result["success"]:
                # Fallback: just list titles
                summary_parts = []
                if query:
                    summary_parts.append(f"Search results for '{query}':")
                else:
                    summary_parts.append("Search results:")
                
                for i, result in enumerate(results[:5], 1):
                    title = result.get('title', 'Untitled')
                    summary_parts.append(f"{i}. {title}")
                
                return {
                    "success": True,
                    "summary": '\n'.join(summary_parts),
                    "count": len(results)
                }
            
            # Format with query context
            summary_parts = []
            if query:
                summary_parts.append(f"Summary of search results for '{query}':")
            else:
                summary_parts.append("Summary of search results:")
            
            summary_parts.append(summary_result["summary"])
            summary_parts.append(f"\nBased on {len(results)} source(s).")
            
            return {
                "success": True,
                "summary": '\n'.join(summary_parts),
                "count": len(results),
                "key_points": summary_result["key_sentences"]
            }
            
        except Exception as e:
            logger.error(f"Error in summarize_web_results: {e}", exc_info=True)
            return {
                "success": False,
                "summary": f"Error summarizing search results: {str(e)}",
                "count": 0
            }
