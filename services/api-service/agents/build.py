"""
build.py  –  construct all runnable LLM agents and return them
as a Dict[str, Runnable].  Every agent returns a JSON object
matching AnswerSchema {"answer": "<text>"} and keeps its own
ConversationBufferMemory.
"""

from __future__ import annotations

from typing import Dict
import textwrap

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from config.config import settings
# ---------------------------------------------------------------------------
# 1) Schema & parser → {"answer": "..."}
# ---------------------------------------------------------------------------
class AnswerSchema(BaseModel):
    answer: str = Field(description="Direct answer to the user's question")


parser = PydanticOutputParser(pydantic_object=AnswerSchema)

# ---------------------------------------------------------------------------
# 2) Prompt template
# ---------------------------------------------------------------------------
SYSTEM_MSG = SystemMessagePromptTemplate.from_template(
    "You are a helpful assistant. Provide concise answers.\n\n{format_instructions}"
)

HUMAN_MSG = HumanMessagePromptTemplate.from_template(
    textwrap.dedent(
        """
        Chat history:
        {chat_history}

        Question: {input}
        """
    ).strip()
)

QUESTION_PROMPT = ChatPromptTemplate.from_messages([SYSTEM_MSG, HUMAN_MSG]).partial(
    format_instructions=parser.get_format_instructions()
)

# ---------------------------------------------------------------------------
# 3) Helper: build a runnable chain that goes  str → dict{'answer': str}
# ---------------------------------------------------------------------------
def _build_chain(llm) -> RunnablePassthrough:
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="input",
        return_messages=False,
    )
    chain = LLMChain(llm=llm, prompt=QUESTION_PROMPT, memory=memory)

    adapter_in  = RunnableLambda(lambda s: {"input": s})       # str → dict
    adapter_out = RunnableLambda(lambda d: d["text"])          # chain output → str

    # Pipeline: str → dict → LLMChain → str → parser → {"answer": str}
    return adapter_in | chain | adapter_out | parser


# ---------------------------------------------------------------------------
# 4) Public factory
# ---------------------------------------------------------------------------
def build_agents() -> Dict[str, RunnablePassthrough]:
    """Return dict {name: runnable_agent}."""
    agents = {}
    
    # Only create agents for which we have API keys
    if settings.OPENAI_API_KEY:
        # GPT-5 models don't support temperature parameter
        openai_model = settings.OPENAI_MODEL
        is_new_model = openai_model.startswith("gpt-5") or openai_model.startswith("o1") or openai_model.startswith("o3")
        
        openai_kwargs = {
            "model": openai_model,
            "api_key": settings.OPENAI_API_KEY,
        }
        
        if is_new_model:
            openai_kwargs["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS
        else:
            openai_kwargs["temperature"] = settings.OPENAI_TEMPERATURE
            openai_kwargs["max_tokens"] = settings.OPENAI_MAX_TOKENS
        
        agents["openai"] = _build_chain(ChatOpenAI(**openai_kwargs))
    
    if settings.GEMINI_API_KEY:
        agents["gemini"] = _build_chain(
            ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=settings.GEMINI_TEMPERATURE,
                max_output_tokens=settings.GEMINI_MAX_TOKENS
            )
        )
    
    if settings.GROK_API_KEY:
        agents["grok"] = _build_chain(
            ChatOpenAI(
                model=settings.GROK_MODEL,
                base_url=settings.GROK_BASE_URL,
                api_key=settings.GROK_API_KEY,
                temperature=settings.GROK_TEMPERATURE,
                max_tokens=settings.GROK_MAX_TOKENS
            )
        )
    
    if settings.CLAUDE_API_KEY:
        agents["claude"] = _build_chain(
            ChatAnthropic(
                model=settings.CLAUDE_MODEL,
                api_key=settings.CLAUDE_API_KEY,
                temperature=settings.CLAUDE_TEMPERATURE,
                max_tokens=settings.CLAUDE_MAX_TOKENS
            )
        )
    
    return agents


# ---------------------------------------------------------------------------
# 5) Convenience re-export for `from agents import build_agents`
# ---------------------------------------------------------------------------
__all__ = ["build_agents"]