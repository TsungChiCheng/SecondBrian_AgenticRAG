from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class GraphifyExportError(RuntimeError):
    """Raised when graphify cannot produce the required wiki export."""


@dataclass
class WikiExportResult:
    filename: str
    content: str


@dataclass
class WikiZipExportResult:
    filename: str
    zip_path: Path
    workspace_dir: Path


@dataclass
class GraphifyRunResult:
    command: List[str]
    stdout: str
    stderr: str
    used_fallback: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_segment(value: Any, fallback: str = "item") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-._")
    return text[:120] or fallback


def _data_root(data_root: Optional[Path] = None) -> Path:
    if data_root is not None:
        return Path(data_root)
    return Path(os.getenv("SECOND_BRAIN_DATA_DIR", "/app/data"))


def _export_tmp_root(tmp_root: Optional[Path] = None) -> Path:
    if tmp_root is not None:
        return Path(tmp_root)
    return Path(os.getenv("WIKI_EXPORT_TMP_ROOT", "/tmp"))


def save_session_image_upload(
    *,
    user_id: str,
    session_id: str,
    image_base64: str,
    mime_type: str,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Persist an uploaded image and return metadata safe for message storage."""
    if not image_base64:
        raise ValueError("image_base64 is required")

    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image_base64 is not valid base64") from exc

    if not image_bytes:
        raise ValueError("image_base64 decoded to an empty file")

    clean_mime = (mime_type or "application/octet-stream").split(";")[0].lower()
    extension = IMAGE_EXTENSIONS.get(clean_mime, ".bin")
    timestamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}_{uuid.uuid4().hex}{extension}"

    upload_dir = (
        _data_root(data_root)
        / "uploads"
        / _safe_segment(user_id, "user")
        / _safe_segment(session_id, "session")
    )
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = upload_dir / filename
    image_path.write_bytes(image_bytes)

    return {
        "image_file_path": str(image_path),
        "image_file_name": filename,
        "image_mime_type": clean_mime,
        "image_size_bytes": len(image_bytes),
        "image_saved_at": _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def _metadata_dict(message: Dict[str, Any]) -> Dict[str, Any]:
    metadata = message.get("metadata") or {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalize_message_for_export(message: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(message)
    normalized["metadata"] = _metadata_dict(message)
    return normalized


def _format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _table_escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _markdown_code_block(text: str) -> str:
    fence = "```"
    if "```" in text:
        fence = "````"
    return f"{fence}\n{text.rstrip()}\n{fence}\n"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _demote_headings(markdown: str, levels: int = 1) -> str:
    def _replace(match: re.Match[str]) -> str:
        hashes = match.group(1)
        suffix = match.group(2)
        return f"{'#' * min(6, len(hashes) + levels)}{suffix}"

    return re.sub(r"^(#{1,6})(\s+)", _replace, markdown, flags=re.MULTILINE)


def _copy_message_images(messages: Sequence[Dict[str, Any]], raw_dir: Path) -> List[Dict[str, Any]]:
    image_dir = raw_dir / "images"
    copied: List[Dict[str, Any]] = []

    for index, message in enumerate(messages, start=1):
        metadata = _metadata_dict(message)
        source_path = metadata.get("image_file_path")
        if not source_path:
            continue

        source = Path(source_path)
        if not source.exists() or not source.is_file():
            copied.append({
                "message_index": index,
                "missing": True,
                "source_path": str(source),
                "filename": metadata.get("image_file_name") or source.name,
            })
            continue

        image_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"message_{index:03d}_{_safe_segment(metadata.get('image_file_name') or source.name, 'image')}"
        target = image_dir / target_name
        shutil.copy2(source, target)
        copied.append({
            "message_index": index,
            "missing": False,
            "source_path": str(source),
            "filename": target_name,
            "relative_path": f"images/{target_name}",
            "mime_type": metadata.get("image_mime_type"),
            "size_bytes": metadata.get("image_size_bytes"),
        })

    return copied


def _write_session_sources(
    *,
    session: Dict[str, Any],
    messages: Sequence[Dict[str, Any]],
    raw_dir: Path,
    images: Sequence[Dict[str, Any]],
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    message_dir = raw_dir / "messages"
    message_dir.mkdir(parents=True, exist_ok=True)
    images_by_message = {item["message_index"]: item for item in images}

    session_lines = [
        f"# {session.get('title') or 'Conversation Session'}",
        "",
        "## Session Metadata",
        "",
        f"- Session ID: {session.get('id', '')}",
        f"- Created: {_format_dt(session.get('created_at'))}",
        f"- Updated: {_format_dt(session.get('updated_at'))}",
        f"- Message count: {len(messages)}",
        f"- Image count: {sum(1 for image in images if not image.get('missing'))}",
        "",
        "## Conversation Transcript",
        "",
    ]

    for index, message in enumerate(messages, start=1):
        role = _safe_segment(message.get("role"), "message").title()
        created = _format_dt(message.get("created_at"))
        content = str(message.get("content") or "")
        image = images_by_message.get(index)

        block = [
            f"## Message {index:03d}: {role}",
            "",
            f"- Created: {created}",
            f"- Role: {role}",
        ]
        if image:
            if image.get("missing"):
                block.append(f"- Image source missing: {image.get('filename')}")
            else:
                block.append(f"- Image: {image.get('relative_path')}")
        block.extend(["", content or "(empty message)", ""])
        if image and not image.get("missing"):
            block.extend([f"![Uploaded image]({image['relative_path']})", ""])

        message_markdown = "\n".join(block)
        session_lines.append(message_markdown)
        (message_dir / f"message_{index:03d}_{role.lower()}.md").write_text(
            message_markdown,
            encoding="utf-8",
        )

    (raw_dir / "session.md").write_text("\n".join(session_lines), encoding="utf-8")

    inventory = [
        "# Source Inventory",
        "",
        "| Type | Name | Detail |",
        "| --- | --- | --- |",
        f"| Session | {_table_escape(session.get('id'))} | {_table_escape(session.get('title'))} |",
    ]
    for image in images:
        status = "missing" if image.get("missing") else image.get("relative_path", "")
        inventory.append(
            f"| Image | {_table_escape(image.get('filename'))} | {_table_escape(status)} |"
        )
    (raw_dir / "source_inventory.md").write_text("\n".join(inventory) + "\n", encoding="utf-8")


def _reset_export_workspace(session_id: str, tmp_root: Optional[Path] = None) -> Path:
    safe_session_id = _safe_segment(session_id, "session")
    root = _export_tmp_root(tmp_root)
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / safe_session_id

    resolved_root = root.resolve()
    resolved_workspace = workspace.resolve() if workspace.exists() else workspace.parent.resolve() / workspace.name
    if resolved_workspace.parent != resolved_root:
        raise GraphifyExportError(f"Refusing to use unsafe export workspace: {workspace}")

    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _write_workspace_zip(workspace_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(workspace_dir.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            archive.write(path, path.relative_to(workspace_dir).as_posix())


def _render_markdown_to_html(markdown: str) -> str:
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        return f"<pre>{escape(markdown)}</pre>"

    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
    return renderer.render(markdown)


def _html_export_styles() -> str:
    return """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --ink: #1d2433;
  --muted: #667085;
  --line: #d8dee8;
  --accent: #2563eb;
  --accent-soft: #e8f0ff;
  --code-bg: #101828;
  --code-ink: #f8fafc;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.shell {
  display: grid;
  grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
  padding: 28px 24px;
  border-right: 1px solid var(--line);
  background: #111827;
  color: #f9fafb;
}
.brand { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #93c5fd; }
.sidebar h1 { margin: 10px 0 12px; font-size: 24px; line-height: 1.2; }
.meta { margin: 0 0 22px; color: #cbd5e1; font-size: 13px; }
.toc-title { margin: 24px 0 8px; font-size: 13px; color: #93c5fd; text-transform: uppercase; }
.toc { display: grid; gap: 6px; }
.toc a { color: #e5e7eb; text-decoration: none; font-size: 14px; line-height: 1.35; }
.toc a:hover { color: #93c5fd; }
.content {
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  padding: 48px 36px 80px;
}
article {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 42px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.06);
}
h1, h2, h3, h4 { line-height: 1.25; color: #111827; }
h1 { margin-top: 0; font-size: 36px; }
h2 { margin-top: 42px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 26px; }
h3 { margin-top: 30px; font-size: 20px; }
p, ul, ol, table, pre { margin: 0 0 18px; }
a { color: var(--accent); }
blockquote {
  margin: 0 0 20px;
  padding: 12px 16px;
  background: var(--accent-soft);
  border-left: 4px solid var(--accent);
  color: #344054;
}
code {
  padding: 2px 5px;
  border-radius: 4px;
  background: #eef2f7;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .92em;
}
pre {
  overflow: auto;
  padding: 16px;
  border-radius: 8px;
  background: var(--code-bg);
  color: var(--code-ink);
}
pre code { padding: 0; background: transparent; color: inherit; }
table {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
}
th, td { padding: 10px 12px; border: 1px solid var(--line); vertical-align: top; }
th { background: #f2f5f9; text-align: left; }
img { max-width: 100%; border-radius: 8px; border: 1px solid var(--line); }
@media (max-width: 860px) {
  .shell { display: block; }
  .sidebar { position: static; height: auto; }
  .content { padding: 20px; }
  article { padding: 24px; }
}
"""


def _compose_html_export(*, title: str, markdown: str, session: Dict[str, Any]) -> str:
    document_title = f"{title} - LLM Wiki"
    rendered = _render_markdown_to_html(markdown)
    generated_at = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    session_id = escape(str(session.get("id") or ""))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(document_title)}</title>
  <style>{_html_export_styles()}</style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">Second Brain LLM Wiki</div>
      <h1>{escape(title)}</h1>
      <p class="meta">Generated {escape(generated_at)}<br>Session {session_id}</p>
      <div class="toc-title">Contents</div>
      <nav class="toc" id="toc"></nav>
    </aside>
    <main class="content">
      <article id="wiki-content">{rendered}</article>
    </main>
  </div>
  <script>
    const toc = document.getElementById('toc');
    const headings = document.querySelectorAll('#wiki-content h1, #wiki-content h2, #wiki-content h3');
    headings.forEach((heading, index) => {{
      const text = heading.textContent || 'section';
      const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || `section-${{index + 1}}`;
      heading.id = `${{id}}-${{index + 1}}`;
      const link = document.createElement('a');
      link.href = `#${{heading.id}}`;
      link.textContent = text;
      link.style.paddingLeft = heading.tagName === 'H3' ? '14px' : '0';
      toc.appendChild(link);
    }});
  </script>
</body>
</html>
"""


def _write_html_exports(workspace_dir: Path, *, title: str, session: Dict[str, Any], markdown: str) -> None:
    html = _compose_html_export(title=title, session=session, markdown=markdown)
    wiki_html_path = workspace_dir / "wiki" / "session-wiki.html"
    wiki_html_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_html_path.write_text(html, encoding="utf-8")
    (workspace_dir / "index.html").write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=wiki/session-wiki.html">
  <title>Second Brain LLM Wiki</title>
</head>
<body>
  <p><a href="wiki/session-wiki.html">Open the LLM Wiki HTML export</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )


async def _run_graphify_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Dict[str, str],
    timeout: int,
    phase: str,
) -> tuple[str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise GraphifyExportError(f"Graphify {phase} timed out after {timeout} seconds") from exc

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if process.returncode != 0:
        detail = (stderr or stdout).strip()[:1200]
        raise GraphifyExportError(f"Graphify {phase} failed with exit code {process.returncode}: {detail}")
    return stdout, stderr


def _sanitize_graphify_graph(graph_path: Path) -> int:
    """Normalize graphify graph metadata that can crash `graphify export wiki`."""
    if not graph_path.exists():
        raise GraphifyExportError(f"Graphify extract did not produce {graph_path}")

    try:
        graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphifyExportError(f"Graphify produced invalid graph JSON: {exc}") from exc

    changed = 0

    def _sanitize(value: Any) -> Any:
        nonlocal changed
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "source_file" and not isinstance(item, str):
                    value[key] = "" if item is None else str(item)
                    changed += 1
                else:
                    value[key] = _sanitize(item)
            return value
        if isinstance(value, list):
            for index, item in enumerate(value):
                value[index] = _sanitize(item)
        return value

    _sanitize(graph_data)
    if changed:
        _write_json(graph_path, graph_data)
    return changed


async def _run_graphify(raw_dir: Path, work_dir: Path, timeout: int) -> GraphifyRunResult:
    extra_args: List[str] = []
    backend = os.getenv("GRAPHIFY_BACKEND")
    if backend:
        extra_args.extend(["--backend", backend])
    extra_args.extend(shlex.split(os.getenv("GRAPHIFY_EXTRA_ARGS", "")))

    command_prefixes = [
        [os.getenv("GRAPHIFY_COMMAND", "graphify")],
        [sys.executable, "-m", "graphify"],
    ]
    last_error: Optional[BaseException] = None
    env = os.environ.copy()
    if env.get("CLAUDE_API_KEY") and not env.get("ANTHROPIC_API_KEY"):
        env["ANTHROPIC_API_KEY"] = env["CLAUDE_API_KEY"]

    for prefix in command_prefixes:
        extract_command = [
            *prefix,
            "extract",
            str(raw_dir),
            "--out",
            str(work_dir),
            *extra_args,
        ]
        export_command = [
            *prefix,
            "export",
            "wiki",
            "--graph",
            str(work_dir / "graphify-out" / "graph.json"),
        ]
        try:
            extract_stdout, extract_stderr = await _run_graphify_command(
                extract_command,
                cwd=work_dir,
                env=env,
                timeout=timeout,
                phase="extract",
            )
            sanitized_count = _sanitize_graphify_graph(work_dir / "graphify-out" / "graph.json")
            if sanitized_count:
                extract_stdout = (
                    f"{extract_stdout.rstrip()}\n"
                    f"[secondbrain wiki export] normalized {sanitized_count} graph source_file fields before wiki export\n"
                )
            export_stdout, export_stderr = await _run_graphify_command(
                export_command,
                cwd=work_dir,
                env=env,
                timeout=timeout,
                phase="wiki export",
            )
        except FileNotFoundError as exc:
            last_error = exc
            continue

        return GraphifyRunResult(
            command=[*extract_command, "&&", *export_command],
            stdout="\n".join(part for part in [extract_stdout, export_stdout] if part),
            stderr="\n".join(part for part in [extract_stderr, export_stderr] if part),
        )

    if last_error:
        raise GraphifyExportError(
            "Graphify is required for wiki export but could not be executed. "
            "Install the official PyPI package with `pip install graphifyy`."
        ) from last_error

    raise GraphifyExportError("Graphify is required for wiki export but no command could be executed")


def _find_wiki_dir(work_dir: Path, raw_dir: Path) -> Path:
    candidates = [
        work_dir / "graphify-out" / "wiki",
        raw_dir / "graphify-out" / "wiki",
        raw_dir.parent / "graphify-out" / "wiki",
    ]
    for candidate in candidates:
        if (candidate / "index.md").exists():
            return candidate
    discovered = sorted(str(path.relative_to(work_dir)) for path in work_dir.rglob("*") if path.is_file())
    preview = ", ".join(discovered[:20]) or "no files"
    raise GraphifyExportError(
        "Graphify completed but did not produce graphify-out/wiki/index.md. "
        f"Files found under export workspace: {preview}"
    )


def _read_wiki_files(wiki_dir: Path) -> List[Path]:
    files = sorted(path for path in wiki_dir.rglob("*.md") if path.is_file())
    index_path = wiki_dir / "index.md"
    if index_path in files:
        files.remove(index_path)
        return [index_path, *files]
    return files


def _compose_single_markdown(
    *,
    session: Dict[str, Any],
    messages: Sequence[Dict[str, Any]],
    images: Sequence[Dict[str, Any]],
    wiki_dir: Path,
    graphify_result: GraphifyRunResult,
) -> str:
    generated_at = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    title = session.get("title") or "Conversation Session"
    wiki_files = _read_wiki_files(wiki_dir)
    copied_images = [image for image in images if not image.get("missing")]

    parts = [
        f"# {title} - LLM Wiki Export",
        "",
        "## Export Metadata",
        "",
        f"- Generated: {generated_at}",
        f"- Session ID: {session.get('id', '')}",
        f"- Message count: {len(messages)}",
        f"- Image sources: {len(copied_images)}",
        f"- Graphify fallback used: {'yes' if graphify_result.used_fallback else 'no'}",
        f"- Graphify command: `{' '.join(graphify_result.command)}`",
        "",
        "## Export Index",
        "",
        "- Graphify Wiki",
        "- Source Inventory",
        "- Session Log",
        "- Export Log",
        "",
        "## Graphify Wiki",
        "",
    ]

    for wiki_file in wiki_files:
        relative = wiki_file.relative_to(wiki_dir)
        content = wiki_file.read_text(encoding="utf-8", errors="replace").strip()
        parts.extend([
            f"### {relative}",
            "",
            _demote_headings(content, levels=1) if content else "(empty wiki file)",
            "",
        ])

    parts.extend([
        "## Source Inventory",
        "",
        "| Type | Name | Detail |",
        "| --- | --- | --- |",
        f"| Session | {_table_escape(session.get('id'))} | {_table_escape(title)} |",
    ])
    for image in images:
        detail = "missing source file" if image.get("missing") else image.get("relative_path")
        parts.append(f"| Image | {_table_escape(image.get('filename'))} | {_table_escape(detail)} |")

    parts.extend(["", "## Session Log", ""])
    images_by_message = {image["message_index"]: image for image in images}
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role") or "message").title()
        content = str(message.get("content") or "")
        parts.extend([
            f"### Message {index:03d}: {role}",
            "",
            f"- Created: {_format_dt(message.get('created_at'))}",
        ])
        image = images_by_message.get(index)
        if image:
            status = "missing source file" if image.get("missing") else image.get("relative_path")
            parts.append(f"- Image: {status}")
        parts.extend(["", _markdown_code_block(content or "(empty message)")])

    log_lines = [
        "## Export Log",
        "",
        f"- {generated_at}: Built raw markdown source from {len(messages)} session messages.",
        f"- {generated_at}: Copied {len(copied_images)} image source files for Graphify extraction.",
        (
            f"- {generated_at}: Graphify wiki export was unavailable; merged fallback markdown."
            if graphify_result.used_fallback
            else f"- {generated_at}: Ran Graphify wiki export and merged {len(wiki_files)} markdown files."
        ),
    ]
    if graphify_result.stderr.strip():
        log_lines.extend(["", "### Graphify stderr", "", _markdown_code_block(graphify_result.stderr.strip()[:4000])])
    parts.extend(["", *log_lines, ""])

    return "\n".join(parts)


async def build_session_wiki_export(
    *,
    session: Dict[str, Any],
    messages: Sequence[Dict[str, Any]],
    timeout: Optional[int] = None,
) -> WikiExportResult:
    graphify_timeout = timeout or int(os.getenv("GRAPHIFY_EXPORT_TIMEOUT", "300"))
    with tempfile.TemporaryDirectory(prefix="secondbrain-wiki-") as temp_name:
        work_dir = Path(temp_name)
        raw_dir = work_dir / "raw"
        images = _copy_message_images(messages, raw_dir)
        _write_session_sources(session=session, messages=messages, raw_dir=raw_dir, images=images)

        try:
            graphify_result = await _run_graphify(raw_dir, work_dir, graphify_timeout)
            wiki_dir = _find_wiki_dir(work_dir, raw_dir)
        except GraphifyExportError as exc:
            wiki_dir = work_dir / "graphify-out" / "wiki"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            (wiki_dir / "index.md").write_text(
                "\n".join([
                    "# Graphify Wiki Export Unavailable",
                    "",
                    "Graphify could not produce a wiki for this session, so this file contains the structured session export instead.",
                    "",
                    "## Error",
                    "",
                    _markdown_code_block(str(exc)).rstrip(),
                    "",
                ]),
                encoding="utf-8",
            )
            graphify_result = GraphifyRunResult(
                command=["graphify", "extract", str(raw_dir), "&&", "graphify", "export", "wiki"],
                stdout="",
                stderr=str(exc),
                used_fallback=True,
            )
        content = _compose_single_markdown(
            session=session,
            messages=messages,
            images=images,
            wiki_dir=wiki_dir,
            graphify_result=graphify_result,
        )

    title = _safe_segment(session.get("title"), "session")
    session_id = _safe_segment(session.get("id"), "session")
    filename = f"{title}-{session_id}-llm-wiki.md"
    return WikiExportResult(filename=filename, content=content)


async def build_session_wiki_export_zip(
    *,
    session: Dict[str, Any],
    messages: Sequence[Dict[str, Any]],
    timeout: Optional[int] = None,
    tmp_root: Optional[Path] = None,
) -> WikiZipExportResult:
    graphify_timeout = timeout or int(os.getenv("GRAPHIFY_EXPORT_TIMEOUT", "300"))
    generated_at = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    title = _safe_segment(session.get("title"), "session")
    session_id = _safe_segment(session.get("id"), "session")
    workspace_dir = _reset_export_workspace(session_id, tmp_root)
    raw_dir = workspace_dir / "raw"

    images = _copy_message_images(messages, raw_dir)
    _write_session_sources(session=session, messages=messages, raw_dir=raw_dir, images=images)
    _write_json(workspace_dir / "metadata" / "session.json", session)
    _write_json(
        workspace_dir / "metadata" / "messages.json",
        [_normalize_message_for_export(message) for message in messages],
    )

    try:
        graphify_result = await _run_graphify(raw_dir, workspace_dir, graphify_timeout)
        wiki_dir = _find_wiki_dir(workspace_dir, raw_dir)
    except GraphifyExportError as exc:
        wiki_dir = workspace_dir / "graphify-out" / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "index.md").write_text(
            "\n".join([
                "# Graphify Wiki Export Unavailable",
                "",
                "Graphify could not produce a wiki for this session, so this file contains the structured session export instead.",
                "",
                "## Error",
                "",
                _markdown_code_block(str(exc)).rstrip(),
                "",
            ]),
            encoding="utf-8",
        )
        graphify_result = GraphifyRunResult(
            command=["graphify", "extract", str(raw_dir), "&&", "graphify", "export", "wiki"],
            stdout="",
            stderr=str(exc),
            used_fallback=True,
        )

    content = _compose_single_markdown(
        session=session,
        messages=messages,
        images=images,
        wiki_dir=wiki_dir,
        graphify_result=graphify_result,
    )
    wiki_output_dir = workspace_dir / "wiki"
    wiki_output_dir.mkdir(parents=True, exist_ok=True)
    (wiki_output_dir / "session-wiki.md").write_text(content, encoding="utf-8")
    _write_html_exports(
        workspace_dir,
        title=str(session.get("title") or title),
        session=session,
        markdown=content,
    )

    files = sorted(
        path.relative_to(workspace_dir).as_posix()
        for path in workspace_dir.rglob("*")
        if path.is_file()
    )
    _write_json(
        workspace_dir / "logs" / "export.json",
        {
            "generated_at": generated_at,
            "session_id": session.get("id"),
            "title": session.get("title"),
            "message_count": len(messages),
            "image_count": sum(1 for image in images if not image.get("missing")),
            "workspace_dir": str(workspace_dir),
            "graphify": {
                "command": graphify_result.command,
                "used_fallback": graphify_result.used_fallback,
                "stdout": graphify_result.stdout[-4000:],
                "stderr": graphify_result.stderr[-4000:],
            },
            "files": files,
        },
    )

    filename = f"{title}-{session_id}-llm-wiki.zip"
    zip_path = workspace_dir / filename
    _write_workspace_zip(workspace_dir, zip_path)
    return WikiZipExportResult(filename=filename, zip_path=zip_path, workspace_dir=workspace_dir)
