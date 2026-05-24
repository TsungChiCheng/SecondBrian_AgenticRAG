---
name: llm-wiki
description: Maintain and answer from a structured, source-grounded markdown wiki that compounds knowledge across conversation turns and exports.
source: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md
---

# LLM Wiki

Use this skill when the user selects `Advance (llm-wiki)` or asks to export an LLM wiki.

## Core Pattern

Treat the conversation as material for a persistent markdown wiki, not as a one-off chat answer. Raw sources are immutable evidence. The generated wiki is a maintained layer of summaries, entity pages, concept pages, cross-links, contradictions, and synthesis. Each answer should be easy to file back into the wiki.

## Answer Rules

- Answer the user directly first.
- Use markdown headings and stable sections.
- Prefer source-grounded statements over speculation.
- Name uncertainty explicitly.
- Note contradictions or competing claims when present.
- Include filing suggestions that would help a future wiki maintainer.
- Do not invent citations. If no source is available, say the answer is based on general model knowledge.

## Default Answer Shape

Use this structure for normal questions:

```markdown
## Answer

## Key Points

## Notes / Caveats

## Wiki Filing Suggestions

## Related Concepts
```

For image analysis, include visual observations, extracted text, possible entities/concepts, and image-source notes.

## Wiki Maintenance Conventions

- Keep an `index.md` as the navigation entry point.
- Keep a chronological `log.md` of ingests, queries, updates, and lint passes.
- Use descriptive page titles and wiki-style cross-reference suggestions.
- Preserve raw source context separately from generated synthesis.
- When exporting, include metadata, raw message markdown, copied image assets, wiki markdown, and an export log.

## Export Expectations

An LLM Wiki export should include:

- raw conversation sources
- session and message metadata
- copied image sources when available
- generated wiki markdown
- Graphify output when available
- a fallback wiki file and log when Graphify cannot complete
