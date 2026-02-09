"""
memory_utils.py – wipe conversational memory out of stateful LLM chains.
Exposed as reset_pipeline().
"""

from langchain.chains import LLMChain
from agents.build import build_agents

AGENTS = build_agents()          # same factory used by pipeline

# -----------------------------------------------------------------------------


def _clear_memory(runnable):
    """Find LLMChain(s) inside a RunnableSequence and clear memory."""
    if hasattr(runnable, "steps"):
        for step in runnable.steps:
            if isinstance(step, LLMChain) and getattr(step, "memory", None):
                step.memory.clear()


def reset_pipeline() -> None:
    """Erase conversation history for every agent in-process."""
    for agent in AGENTS.values():
        _clear_memory(agent)