from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class LlmWikiSkillError(RuntimeError):
    """Raised when the llm-wiki skill cannot be loaded."""


@lru_cache(maxsize=1)
def get_llm_wiki_skill_prompt() -> str:
    skill_path = Path(__file__).resolve().parents[1] / "skills" / "llm-wiki" / "SKILL.md"
    if not skill_path.exists():
        raise LlmWikiSkillError(f"llm-wiki skill file not found: {skill_path}")

    content = skill_path.read_text(encoding="utf-8").strip()
    if not content:
        raise LlmWikiSkillError(f"llm-wiki skill file is empty: {skill_path}")
    return content


def skill_name_for_mode(response_mode: str) -> str | None:
    return "llm-wiki" if response_mode == "llm-wiki" else None


def skill_metadata_for_mode(response_mode: str) -> dict:
    skill_name = skill_name_for_mode(response_mode)
    if skill_name:
        return {"response_mode": response_mode, "skill": skill_name}
    return {"response_mode": response_mode}
