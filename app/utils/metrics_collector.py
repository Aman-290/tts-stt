"""
Comprehensive Metrics Collection System for Voice AI Assistant

This module provides a centralized system for collecting and analyzing
performance metrics including latency, accuracy, tool success rates,
and personalization effectiveness.

Usage:
    from app.utils.metrics_collector import MetricsCollector
    
    # Initialize for a user session
    metrics = MetricsCollector(user_id="user_123")
    
    # Log interactions
    metrics.log_interaction("check my emails", "I found 5 emails...", 2.3)
    
    # Log tool calls
    metrics.log_tool_call("search_gmail", {"query": "unread"}, True, 1.2)
    
    # Save session data
    metrics.save_session()
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Centralized metrics collection for voice AI assistant"""
    
    def __init__(self, user_id: str, metrics_dir: str = "data/metrics"):
        """
        Initialize metrics collector
        
        Args:
            user_id: Unique user identifier
            metrics_dir: Directory to store metrics files
        """
        self.user_id = user_id
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logs subdirectory for text logs
        self.logs_dir = self.metrics_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_start = time.time()
        self.session_id = f"{user_id}_{int(time.time())}"
        self.session_metrics = {
            'user_id': user_id,
            'session_id': self.session_id,
            'session_start': datetime.now().isoformat(),
            'interactions': [],
            'tool_calls': [],
            'latencies': [],
            'errors': [],
            'memory_retrievals': [],
            'personalization_events': []
        }
        
        # Initialize text log file
        self.log_file = self.logs_dir / f"session_{self.session_id}.txt"
        self._write_log_header()
    
    def _write_log_header(self):
        """Write header to text log file"""
        with open(self.log_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"VOICE AI ASSISTANT - SESSION LOG\n")
            f.write("="*80 + "\n")
            f.write(f"User ID: {self.user_id}\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Session Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
    
    def _append_to_log(self, message: str):
        """Append message to text log file"""
        with open(self.log_file, 'a') as f:
            timestamp = datetime.now().strftime('%H:%M:%S')
            f.write(f"[{timestamp}] {message}\n")
    
    def log_interaction(
        self, 
        user_input: str, 
        ai_response: str, 
        duration: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a single user-AI interaction
        
        Args:
            user_input: User's input text
            ai_response: AI's response text
            duration: Response time in seconds
            metadata: Additional metadata (e.g., sentiment, satisfaction signals)
        """
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'ai_response': ai_response,
            'duration_seconds': duration,
            'metadata': metadata or {}
        }
        
        # Detect satisfaction signals
        interaction['satisfaction_signal'] = self._detect_satisfaction_signal(user_input)
        
        self.session_metrics['interactions'].append(interaction)
        logger.info(f"Logged interaction: {len(user_input)} chars input, {duration:.2f}s")
        
        # Write to text log
        self._append_to_log(f"\n{'='*70}")
        self._append_to_log(f"INTERACTION #{len(self.session_metrics['interactions'])}")
        self._append_to_log(f"{'='*70}")
        self._append_to_log(f"User Input: {user_input}")
        self._append_to_log(f"AI Response: {ai_response[:200]}{'...' if len(ai_response) > 200 else ''}")
        self._append_to_log(f"Duration: {duration:.2f}s")
        self._append_to_log(f"Satisfaction Signal: {interaction['satisfaction_signal']}")
        if metadata:
            self._append_to_log(f"Metadata: {metadata}")
    
    def log_tool_call(
        self,
        tool_name: str,
        params: dict,
        success: bool,
        duration: float,
        error: Optional[str] = None,
        result: Optional[Any] = None
    ):
        """
        Log tool execution
        
        Args:
            tool_name: Name of the tool called
            params: Parameters passed to the tool
            success: Whether the tool call succeeded
            duration: Execution time in seconds
            error: Error message if failed
            result: Tool result (will be truncated if too large)
        """
        tool_call = {
            'timestamp': datetime.now().isoformat(),
            'tool': tool_name,
            'params': params,
            'success': success,
            'duration_seconds': duration,
            'error': error
        }
        
        # Truncate result if too large
        if result:
            result_str = str(result)
            if len(result_str) > 500:
                tool_call['result'] = result_str[:500] + "... (truncated)"
            else:
                tool_call['result'] = result_str
        
        self.session_metrics['tool_calls'].append(tool_call)
        
        status = "✅" if success else "❌"
        logger.info(f"{status} Tool call: {tool_name} ({duration:.2f}s)")
        
        # Write to text log
        self._append_to_log(f"\n--- TOOL CALL: {tool_name} ---")
        self._append_to_log(f"Status: {status} {'SUCCESS' if success else 'FAILED'}")
        self._append_to_log(f"Parameters: {params}")
        self._append_to_log(f"Duration: {duration:.2f}s")
        if error:
            self._append_to_log(f"Error: {error}")
        if result:
            result_str = str(result)
            self._append_to_log(f"Result: {result_str[:150]}{'...' if len(result_str) > 150 else ''}")
    
    def log_latency(self, component: str, latency_ms: float, metadata: Optional[dict] = None):
        """
        Log component latency (STT, LLM, TTS)
        
        Args:
            component: Component name (stt, llm, tts, e2e)
            latency_ms: Latency in milliseconds
            metadata: Additional metadata
        """
        latency_record = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'latency_ms': latency_ms,
            'metadata': metadata or {}
        }
        
        self.session_metrics['latencies'].append(latency_record)
        
        # Warn if latency is high
        thresholds = {
            'stt': 500,
            'llm': 2000,
            'tts': 800,
            'e2e': 3000
        }
        
        if component in thresholds and latency_ms > thresholds[component]:
            logger.warning(f"⚠️ High {component.upper()} latency: {latency_ms:.0f}ms (threshold: {thresholds[component]}ms)")
            self._append_to_log(f"⚠️ HIGH LATENCY - {component.upper()}: {latency_ms:.0f}ms (threshold: {thresholds[component]}ms)")
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict] = None,
        severity: str = "error"
    ):
        """
        Log errors
        
        Args:
            error_type: Type of error (e.g., 'tool_failure', 'api_error')
            error_message: Error message
            context: Additional context
            severity: Error severity (info, warning, error, critical)
        """
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message,
            'severity': severity,
            'context': context or {}
        }
        
        self.session_metrics['errors'].append(error_record)
        logger.error(f"Error logged: {error_type} - {error_message}")
    
    def log_memory_retrieval(
        self,
        query: str,
        results_count: int,
        avg_relevance_score: float,
        duration: float
    ):
        """
        Log Mem0 memory retrieval
        
        Args:
            query: Search query
            results_count: Number of results returned
            avg_relevance_score: Average relevance score
            duration: Retrieval time in seconds
        """
        retrieval = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'results_count': results_count,
            'avg_relevance_score': avg_relevance_score,
            'duration_seconds': duration,
            'hit': results_count > 0
        }
        
        self.session_metrics['memory_retrievals'].append(retrieval)
        logger.info(f"Memory retrieval: {results_count} results, avg score: {avg_relevance_score:.2f}")
        
        # Write to text log
        self._append_to_log(f"🧠 MEMORY RETRIEVAL - Query: '{query}'")
        self._append_to_log(f"   Results: {results_count}, Avg Score: {avg_relevance_score:.2f}, Duration: {duration:.2f}s")
    
    def log_personalization_event(
        self,
        event_type: str,
        details: dict,
        effectiveness_score: Optional[float] = None
    ):
        """
        Log personalization events
        
        Args:
            event_type: Type of personalization (e.g., 'greeting', 'email_prioritization')
            details: Event details
            effectiveness_score: Optional score (0-100) indicating effectiveness
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'details': details,
            'effectiveness_score': effectiveness_score
        }
        
        self.session_metrics['personalization_events'].append(event)
        logger.info(f"Personalization event: {event_type}")
    
    def _detect_satisfaction_signal(self, user_input: str) -> str:
        """
        Detect implicit satisfaction signals from user input
        
        Args:
            user_input: User's message
            
        Returns:
            'positive', 'negative', or 'neutral'
        """
        message_lower = user_input.lower()
        
        # Positive signals
        positive_words = ['thanks', 'thank you', 'perfect', 'great', 'awesome', 
                         'excellent', 'exactly', 'yes', 'correct', 'right']
        if any(word in message_lower for word in positive_words):
            return 'positive'
        
        # Negative signals
        negative_words = ['no', 'wrong', 'incorrect', 'not what', 'mistake',
                         'error', 'bad', 'stop', 'cancel']
        if any(word in message_lower for word in negative_words):
            return 'negative'
        
        # Clarification requests (mild negative)
        clarification_words = ['what', 'repeat', 'again', 'huh', 'pardon']
        if any(word in message_lower for word in clarification_words):
            return 'clarification_needed'
        
        return 'neutral'
    
    def save_session(self) -> Path:
        """
        Save session metrics to file
        
        Returns:
            Path to saved metrics file
        """
        session_file = self.metrics_dir / f"session_{self.session_metrics['session_id']}.json"
        
        self.session_metrics['session_end'] = datetime.now().isoformat()
        self.session_metrics['total_duration'] = time.time() - self.session_start
        
        # Add summary statistics
        summary = self.get_summary()
        self.session_metrics['summary'] = summary
        
        # Write summary to text log
        self._write_summary_to_log(summary)
        
        with open(session_file, 'w') as f:
            json.dump(self.session_metrics, f, indent=2)
        
        logger.info(f"Session metrics saved to {session_file}")
        logger.info(f"Text log saved to {self.log_file}")
        return session_file
    
    def _write_summary_to_log(self, summary: dict):
        """Write session summary to text log"""
        with open(self.log_file, 'a') as f:
            f.write("\n\n" + "="*80 + "\n")
            f.write("SESSION SUMMARY\n")
            f.write("="*80 + "\n")
            f.write(f"Session Duration: {summary['session_duration_seconds']:.1f}s\n")
            f.write(f"Total Interactions: {summary['total_interactions']}\n")
            f.write(f"Total Tool Calls: {summary['total_tool_calls']}\n")
            f.write(f"Tool Success Rate: {summary['tool_success_rate']:.1f}%\n")
            f.write(f"Errors: {summary['error_count']}\n\n")
            
            f.write("Average Latencies:\n")
            for component, latency in summary['avg_latencies_ms'].items():
                if latency > 0:
                    f.write(f"  - {component.upper()}: {latency:.0f}ms\n")
            
            f.write(f"\nUser Satisfaction:\n")
            sat = summary['satisfaction_distribution']
            f.write(f"  - Positive: {sat['positive']}\n")
            f.write(f"  - Negative: {sat['negative']}\n")
            f.write(f"  - Neutral: {sat['neutral']}\n")
            f.write(f"  - Satisfaction Score: {summary['satisfaction_score']:.1f}%\n")
            
            f.write(f"\nMemory Performance:\n")
            f.write(f"  - Hit Rate: {summary['memory_hit_rate']:.1f}%\n")
            f.write(f"  - Avg Relevance: {summary['avg_memory_relevance']:.2f}\n")
            
            f.write(f"\nPersonalization Events: {summary['personalization_events']}\n")
            f.write("="*80 + "\n")
    
    def get_summary(self) -> dict:
        """
        Get session summary statistics
        
        Returns:
            Dictionary with summary metrics
        """
        total_interactions = len(self.session_metrics['interactions'])
        total_tool_calls = len(self.session_metrics['tool_calls'])
        successful_tools = sum(1 for t in self.session_metrics['tool_calls'] if t['success'])
        
        # Calculate average latencies
        avg_latency = {}
        for component in ['stt', 'llm', 'tts', 'e2e']:
            latencies = [
                l['latency_ms'] 
                for l in self.session_metrics['latencies'] 
                if l['component'] == component
            ]
            avg_latency[component] = sum(latencies) / len(latencies) if latencies else 0
        
        # Calculate satisfaction metrics
        satisfaction_counts = {
            'positive': 0,
            'negative': 0,
            'neutral': 0,
            'clarification_needed': 0
        }
        
        for interaction in self.session_metrics['interactions']:
            signal = interaction.get('satisfaction_signal', 'neutral')
            satisfaction_counts[signal] = satisfaction_counts.get(signal, 0) + 1
        
        # Memory retrieval stats
        memory_retrievals = self.session_metrics['memory_retrievals']
        memory_hit_rate = (
            sum(1 for m in memory_retrievals if m['hit']) / len(memory_retrievals) * 100
            if memory_retrievals else 0
        )
        
        avg_memory_score = (
            sum(m['avg_relevance_score'] for m in memory_retrievals) / len(memory_retrievals)
            if memory_retrievals else 0
        )
        
        return {
            'total_interactions': total_interactions,
            'total_tool_calls': total_tool_calls,
            'tool_success_rate': (successful_tools / total_tool_calls * 100) if total_tool_calls > 0 else 0,
            'avg_latencies_ms': avg_latency,
            'error_count': len(self.session_metrics['errors']),
            'session_duration_seconds': time.time() - self.session_start,
            'satisfaction_distribution': satisfaction_counts,
            'satisfaction_score': (
                (satisfaction_counts['positive'] - satisfaction_counts['negative']) / 
                total_interactions * 100
                if total_interactions > 0 else 0
            ),
            'memory_hit_rate': memory_hit_rate,
            'avg_memory_relevance': avg_memory_score,
            'personalization_events': len(self.session_metrics['personalization_events'])
        }
    
    def print_summary(self):
        """Print a formatted summary of the session"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print(f"📊 SESSION SUMMARY - User: {self.user_id}")
        print("="*60)
        
        print(f"\n📈 Overall Metrics:")
        print(f"  • Duration: {summary['session_duration_seconds']:.1f}s")
        print(f"  • Interactions: {summary['total_interactions']}")
        print(f"  • Tool Calls: {summary['total_tool_calls']}")
        print(f"  • Tool Success Rate: {summary['tool_success_rate']:.1f}%")
        print(f"  • Errors: {summary['error_count']}")
        
        print(f"\n⏱️  Average Latencies:")
        for component, latency in summary['avg_latencies_ms'].items():
            if latency > 0:
                print(f"  • {component.upper()}: {latency:.0f}ms")
        
        print(f"\n😊 User Satisfaction:")
        sat = summary['satisfaction_distribution']
        print(f"  • Positive: {sat['positive']}")
        print(f"  • Negative: {sat['negative']}")
        print(f"  • Neutral: {sat['neutral']}")
        print(f"  • Satisfaction Score: {summary['satisfaction_score']:.1f}%")
        
        print(f"\n🧠 Memory Performance:")
        print(f"  • Hit Rate: {summary['memory_hit_rate']:.1f}%")
        print(f"  • Avg Relevance: {summary['avg_memory_relevance']:.2f}")
        
        print(f"\n✨ Personalization:")
        print(f"  • Events: {summary['personalization_events']}")
        
        print("\n" + "="*60 + "\n")


# Example usage
if __name__ == "__main__":
    # Create a sample session
    metrics = MetricsCollector("test_user_123")
    
    # Simulate some interactions
    metrics.log_interaction(
        "check my emails",
        "I found 5 emails from today...",
        2.3,
        metadata={'intent': 'gmail_search'}
    )
    
    metrics.log_tool_call(
        "search_gmail",
        {"query": "is:unread"},
        success=True,
        duration=1.2
    )
    
    metrics.log_latency("stt", 250)
    metrics.log_latency("llm", 1800)
    metrics.log_latency("tts", 400)
    
    metrics.log_memory_retrieval(
        "emails from sarah",
        results_count=3,
        avg_relevance_score=0.85,
        duration=0.15
    )
    
    metrics.log_personalization_event(
        "greeting",
        {"used_memories": True, "referenced_project": "ML project"},
        effectiveness_score=85
    )
    
    # Print summary
    metrics.print_summary()
    
    # Save to file
    metrics.save_session()
