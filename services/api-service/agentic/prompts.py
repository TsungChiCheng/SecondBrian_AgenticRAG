"""
Centralised prompt definitions for the Agentic RAG graph.
"""

# Router agent prompt (decides whether to retrieve context)
ROUTER_PROMPT = """You are a routing agent for a RAG system. Your job is to decide if the user's query requires retrieving additional context from the knowledge base.

Decision criteria:
- If the query asks about specific information, facts, or previous conversations → RETRIEVE
- If the query is a general question that can be answered with common knowledge → NO RETRIEVE
- If the query references "my", "I said", "we discussed", "earlier" → RETRIEVE (needs session history)
- If the query is a simple greeting or chitchat → NO RETRIEVE

Respond with EXACTLY one word: either "RETRIEVE" or "NO_RETRIEVE"
"""

# Session classification prompt (decides if session is History Search or New Knowledge)
SESSION_CLASSIFICATION_PROMPT = """You are a session classifier for an AI assistant. Your job is to classify the INTENT of a new conversation session based on the first user query.

Categories:
1. "RAG" (History Search / Context Dependent)
   - User asks about previous conversations ("What did we talk about yesterday?")
   - User asks about stored knowledge/memory ("Do you remember my preferences?")
   - User asks about specific facts likely in the database ("What is the project status?")
   - User refers to "this", "that", "it" implying context.

2. "NO_RAG" (New Knowledge / General Assistance)
   - User asks for creative writing ("Write a story about a cat")
   - User asks general knowledge questions ("How to cook rice?")
   - User asks for coding help without context ("Write a python script to sort a list")
   - User asks for brainstorming or ideas.

Instruction:
- Analyze the user's query.
- Classify into one of the two categories.
- Respond with EXACTLY one word: either "RAG" or "NO_RAG".
"""

# Image analysis default prompt
IMAGE_ANALYSIS_PROMPT = (
    "Describe what's in this image in detail. Extract any text, concepts, or key information that could be searched.\n\n"
    "Format your response in markdown with appropriate sections (use ## for main topics) if the analysis is detailed."
)


def build_summarization_system_prompt(current_date: str, skill_prompt: str | None = None) -> str:
    """Build the system prompt for multi-model summarization."""
    skill_section = ""
    if skill_prompt:
        skill_section = f"""

Active skill instructions:

{skill_prompt}
"""

    return f"""Today's date is {current_date}.
You are an expert at synthesizing information from multiple AI sources. 
Create a comprehensive, accurate summary that combines the best insights from all responses.
Focus on factual information and avoid speculation.
{skill_section}

Formatting: For longer summaries, use markdown structure with ## for main sections and ### for subsections."""


def build_answer_system_prompt(context: str, history: str, skill_prompt: str | None = None) -> str:
    """Build the system prompt for the answer-generating agent."""
    skill_section = ""
    if skill_prompt:
        skill_section = f"""

## Active Skill: llm-wiki

Apply these skill instructions to the final answer:

{skill_prompt}
"""

    return f"""You are a helpful AI assistant with access to a knowledge base and conversation history.

{context}
{history}
{skill_section}

Instructions:
- Answer the user's question accurately and concisely
- Use the retrieved context when relevant
- Reference previous conversation when appropriate
- If you're not sure, say so
- Be conversational and friendly

Formatting (for storage purposes only):
- For longer answers, structure your response using markdown formatting
- Use ## for main topic sections
- Use ### for subsections where appropriate
- Use bullet points (- or *) and numbered lists (1., 2.) for clarity
- Use **bold** for emphasis and `code` for technical terms
- Note: Focus on accuracy first; formatting helps organize your answer for better retrieval later
"""


REFINE_PROMPT = """You are a query refiner for a Retrieval-Augmented Generation system.

The last search returned no useful results. Rewrite the user's query to improve recall while keeping intent intact.

Guidelines:
- Keep it concise (1 sentence).
- Add synonyms, key entities, and specific attributes.
- If the question references previous messages, restate them explicitly.
- Do NOT answer the question; output only the improved query text."""


def build_refine_prompt(original_query: str, previous_attempts: int) -> str:
    """Prompt to refine a query after poor retrieval."""
    return f"""{REFINE_PROMPT}

Original query: {original_query}
Attempt #: {previous_attempts + 1}

Return only the rewritten query."""
