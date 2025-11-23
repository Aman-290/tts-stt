"""Base agent classes and types"""
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
from app.utils.logger import get_logger

class AgentType(Enum):
    """Types of agents"""
    GMAIL = "gmail"
    CALENDAR = "calendar"
    GENERAL = "general"

@dataclass
class ToolParameter:
    """Parameter definition for a tool"""
    name: str
    type: str
    description: str
    required: bool = True

@dataclass
class Tool:
    """Tool definition for agent"""
    name: str
    description: str
    parameters: List[ToolParameter]

@dataclass
class AgentContext:
    """Context passed to agent for execution"""
    user_id: str
    tool_arguments: Dict[str, Any]
    session_data: Optional[Dict[str, Any]] = None

@dataclass
class AgentResponse:
    """Response from agent execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def success_response(cls, data: Dict[str, Any]) -> 'AgentResponse':
        """Create a success response"""
        return cls(success=True, data=data)

    @classmethod
    def error_response(cls, error: str) -> 'AgentResponse':
        """Create an error response"""
        return cls(success=False, error=error)

class BaseAgent:
    """Base class for all agents"""

    def __init__(self, agent_type: AgentType, name: str):
        self.agent_type = agent_type
        self.name = name
        self.logger = get_logger(f"agent.{name}")
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the agent (override in subclass)"""
        self._initialized = True

    async def ensure_initialized(self):
        """Ensure agent is initialized"""
        if not self._initialized:
            await self.initialize()

    async def execute(self, context: AgentContext) -> AgentResponse:
        """Execute agent operation (override in subclass)"""
        raise NotImplementedError("Subclass must implement execute()")

    def get_tools(self) -> List[Tool]:
        """Get available tools (override in subclass)"""
        return []
