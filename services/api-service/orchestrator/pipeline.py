"""
pipeline.py – run one prompt through all LLM agents in parallel,
then call the summariser.  Public API:  run_pipeline(prompt:str) -> (summary, answers_dict)
"""

from __future__ import annotations
import asyncio, logging
from typing import Dict, Tuple, List

from pydantic import BaseModel
from langchain_core.exceptions import OutputParserException

from agents.build import build_agents           # your original builder
from .summariser import summarise               # local summariser helper

log = logging.getLogger(__name__)

# Build agents once at import time --------------------------------------------
AGENTS: Dict[str, object] = build_agents()      # {"openai": runnable, …}

# -----------------------------------------------------------------------------


class QA(BaseModel):
    name: str
    answer: str


def _invoke_sync(agent_name: str, question: str) -> QA:
    """Invoke one runnable agent synchronously (for executor thread)."""
    try:
        raw = AGENTS[agent_name].invoke(question)

        if isinstance(raw, dict):
            answer = raw.get("answer", str(raw))
        elif isinstance(raw, BaseModel):
            answer = raw.answer
        else:
            answer = str(raw)

    except OutputParserException as e:
        answer = f"[parser-error] {e}"
    except Exception as e:                       # catch & log everything else
        log.exception("Agent %s threw:", agent_name)
        answer = f"[error] {e}"

    return QA(name=agent_name, answer=answer)


async def _gather_answers(question: str) -> List[QA]:
    """Run all agents in parallel (thread pool)."""
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, _invoke_sync, name, question)
        for name in AGENTS
    ]
    return await asyncio.gather(*tasks)


# -----------------------------------------------------------------------------


async def run_pipeline(user_input: str) -> tuple[str, Dict[str, str]]:
    """
    Main entry-point used by FastAPI.
    Returns (summary_text, answers_dict).
    """
    qas = await _gather_answers(user_input)                 # list[QA]
    joined = "\n\n".join(f"{qa.name}: {qa.answer}" for qa in qas)

    summary = summarise(user_input, joined)                 # str
    answers = {qa.name: qa.answer for qa in qas}

    return summary, answers