"""
Conversation state schema for LangGraph
"""
from typing import TypedDict, List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict
import operator


class ConversationState(TypedDict):
    """State maintained across conversation turns in a LangGraph session"""
    
    # Session identifiers
    session_id: str
    user_id: str
    
    # Conversation messages
    messages: Annotated[List[Dict[str, str]], operator.add]  # List of {"role": "...", "content": "..."}
    
    # Current query being processed
    current_query: str
    
    # RAG retrieval results
    retrieved_context: List[Dict[str, Any]]
    llm_answers: Dict[str, str]        # Per-model answers (non-error) gathered before synthesis
    llm_errors: Dict[str, str]         # Per-model error strings (not fed to synthesis)
    
    # Agent reasoning
    agent_thoughts: List[str]  # Track agent's reasoning steps
    
    # Control flow
    iteration_count: int  # Prevent infinite loops
    max_iterations: int   # Maximum allowed iterations
    should_retrieve: bool  # Whether to retrieve context
    should_refine: bool    # Whether to refine the query
    
    # Final output
    final_answer: Optional[str]
    
    # Model selection
    selected_models: List[str]  # Which LLMs to use for final answer

    # Session Intent
    session_mode: Optional[str] # "RAG" or "NO_RAG"
