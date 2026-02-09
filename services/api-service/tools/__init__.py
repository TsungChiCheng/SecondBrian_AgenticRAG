"""
tools package
─────────────
Central place to expose every MCP-tool router so main.py (or mcp_config.py)
can simply:

    from tools import summarizer_router, notion_router, combo_router
"""

# Individual routers --------------------------------------------------------
from .summarizer import router as summarizer_router             # /tools/daily_summarizer
from .notion_push import router as notion_router                # /tools/notion_push
from .daily_summarize_and_push import router as combo_router    # /tools/daily_summarize_and_push

# What `from tools import *` will deliver -------------------------------
__all__ = [
    "summarizer_router",
    "notion_router",
    "combo_router",
]