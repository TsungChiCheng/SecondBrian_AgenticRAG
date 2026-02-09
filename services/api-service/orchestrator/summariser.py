"""
summariser.py – given a question and joined agent answers,
produce a consensus summary + per-agent listing.
"""

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from config.config import settings
import os

_model = os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL)
_supports_max_tokens = _model.startswith("gpt-4")
_is_new_model = _model.startswith("gpt-5") or _model.startswith("o1") or _model.startswith("o3")

_llm_kwargs = {
    "model": _model,
}
if not _is_new_model:
    _llm_kwargs["temperature"] = 0
_llm_kwargs.update({"max_tokens": 1000} if _supports_max_tokens else {"max_completion_tokens": 1000})

SUMMARY_LLM = ChatOpenAI(**_llm_kwargs)

_PROMPT = PromptTemplate.from_template(
    """You are an expert summariser.
First, give a concise *consensus* answer to the user's question.
Then list each LLM's individual answer in **LLM-Name:** answer format.

User question:
{question}

LLM answers:
{answers}
"""
)

# Public helper ---------------------------------------------------------------


def summarise(question: str, joined_answers: str) -> str:
    return SUMMARY_LLM.invoke(
        _PROMPT.format(question=question, answers=joined_answers)
    ).content
