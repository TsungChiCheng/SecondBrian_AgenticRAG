import base64
import json
import zipfile

import pytest

from utils.llm_wiki_skill import get_llm_wiki_skill_prompt
from utils import wiki_export


def test_save_session_image_upload_persists_file(tmp_path):
    payload = base64.b64encode(b"fake-image").decode("ascii")

    metadata = wiki_export.save_session_image_upload(
        user_id="user@example.com",
        session_id="session-123",
        image_base64=payload,
        mime_type="image/png",
        data_root=tmp_path,
    )

    saved_path = tmp_path / "uploads" / "user-example.com" / "session-123" / metadata["image_file_name"]
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"fake-image"
    assert metadata["image_file_path"] == str(saved_path)
    assert metadata["image_mime_type"] == "image/png"
    assert metadata["image_size_bytes"] == len(b"fake-image")


def test_llm_wiki_skill_prompt_loads():
    prompt = get_llm_wiki_skill_prompt()

    assert "name: llm-wiki" in prompt
    assert "Wiki Filing Suggestions" in prompt


def test_sanitize_graphify_graph_normalizes_non_string_source_files(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps({
            "nodes": [
                {"id": "a", "source_file": None},
                {"id": "b", "source_file": 123},
                {"id": "c", "source_file": "session.md"},
            ],
            "links": [{"source_file": None}],
        }),
        encoding="utf-8",
    )

    changed = wiki_export._sanitize_graphify_graph(graph_path)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    assert changed == 3
    assert graph["nodes"][0]["source_file"] == ""
    assert graph["nodes"][1]["source_file"] == "123"
    assert graph["nodes"][2]["source_file"] == "session.md"
    assert graph["links"][0]["source_file"] == ""


@pytest.mark.asyncio
async def test_build_session_wiki_export_merges_graphify_output(tmp_path, monkeypatch):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake-image")

    async def fake_run_graphify(raw_dir, work_dir, timeout):
        assert (raw_dir / "session.md").exists()
        assert (raw_dir / "images" / "message_001_image.png").exists()

        wiki_dir = work_dir / "graphify-out" / "wiki"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "index.md").write_text("# Index\n\n- [[Image Notes]]\n", encoding="utf-8")
        (wiki_dir / "image-notes.md").write_text("# Image Notes\n\nDetected diagram content.\n", encoding="utf-8")
        return wiki_export.GraphifyRunResult(
            command=["graphify", str(raw_dir), "--wiki"],
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(wiki_export, "_run_graphify", fake_run_graphify)

    result = await wiki_export.build_session_wiki_export(
        session={
            "id": "session-123",
            "title": "Test Session",
            "created_at": "2026-05-24T00:00:00Z",
            "updated_at": "2026-05-24T00:00:00Z",
        },
        messages=[
            {
                "role": "user",
                "content": "[Image uploaded]",
                "created_at": "2026-05-24T00:00:00Z",
                "metadata": json.dumps({
                    "is_image": True,
                    "image_file_path": str(image_path),
                    "image_file_name": "image.png",
                    "image_mime_type": "image/png",
                    "image_size_bytes": image_path.stat().st_size,
                }),
            },
            {
                "role": "assistant",
                "content": "The image contains a diagram.",
                "created_at": "2026-05-24T00:01:00Z",
                "metadata": {},
            },
        ],
        timeout=5,
    )

    assert result.filename == "Test-Session-session-123-llm-wiki.md"
    assert "# Test Session - LLM Wiki Export" in result.content
    assert "Detected diagram content." in result.content
    assert "| Image | message_001_image.png | images/message_001_image.png |" in result.content
    assert "The image contains a diagram." in result.content


@pytest.mark.asyncio
async def test_build_session_wiki_export_zip_writes_workspace_and_archive(tmp_path, monkeypatch):
    async def fake_run_graphify(raw_dir, work_dir, timeout):
        wiki_dir = work_dir / "graphify-out" / "wiki"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "index.md").write_text("# Index\n\n- [[Session Notes]]\n", encoding="utf-8")
        return wiki_export.GraphifyRunResult(
            command=["graphify", "extract", str(raw_dir)],
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(wiki_export, "_run_graphify", fake_run_graphify)

    result = await wiki_export.build_session_wiki_export_zip(
        session={
            "id": "session-123",
            "title": "Zip Session",
            "created_at": "2026-05-24T00:00:00Z",
            "updated_at": "2026-05-24T00:00:00Z",
        },
        messages=[
            {
                "role": "user",
                "content": "hello",
                "created_at": "now",
                "metadata": json.dumps({"skill": "llm-wiki"}),
            }
        ],
        timeout=5,
        tmp_root=tmp_path,
    )

    assert result.filename == "Zip-Session-session-123-llm-wiki.zip"
    assert result.workspace_dir == tmp_path / "session-123"
    assert result.zip_path.exists()
    assert (result.workspace_dir / "metadata" / "session.json").exists()
    assert (result.workspace_dir / "metadata" / "messages.json").exists()
    assert (result.workspace_dir / "raw" / "session.md").exists()
    assert (result.workspace_dir / "wiki" / "session-wiki.md").exists()
    assert (result.workspace_dir / "wiki" / "session-wiki.html").exists()
    assert (result.workspace_dir / "index.html").exists()
    assert (result.workspace_dir / "logs" / "export.json").exists()

    export_log = json.loads((result.workspace_dir / "logs" / "export.json").read_text(encoding="utf-8"))
    exported_messages = json.loads((result.workspace_dir / "metadata" / "messages.json").read_text(encoding="utf-8"))
    html = (result.workspace_dir / "wiki" / "session-wiki.html").read_text(encoding="utf-8")
    assert export_log["graphify"]["used_fallback"] is False
    assert exported_messages[0]["metadata"] == {"skill": "llm-wiki"}
    assert "<table>" in html
    assert "Second Brain LLM Wiki" in html

    with zipfile.ZipFile(result.zip_path) as archive:
        names = set(archive.namelist())

    assert "index.html" in names
    assert "metadata/session.json" in names
    assert "metadata/messages.json" in names
    assert "raw/session.md" in names
    assert "wiki/session-wiki.md" in names
    assert "wiki/session-wiki.html" in names
    assert "logs/export.json" in names


@pytest.mark.asyncio
async def test_build_session_wiki_export_zip_falls_back_when_graphify_fails(tmp_path, monkeypatch):
    async def fake_run_graphify(raw_dir, work_dir, timeout):
        raise wiki_export.GraphifyExportError("graphify failed")

    monkeypatch.setattr(wiki_export, "_run_graphify", fake_run_graphify)

    result = await wiki_export.build_session_wiki_export_zip(
        session={"id": "session-456", "title": "Fallback Session"},
        messages=[{"role": "assistant", "content": "fallback content", "created_at": "now", "metadata": {}}],
        timeout=5,
        tmp_root=tmp_path,
    )

    wiki_md = (result.workspace_dir / "wiki" / "session-wiki.md").read_text(encoding="utf-8")
    export_log = json.loads((result.workspace_dir / "logs" / "export.json").read_text(encoding="utf-8"))

    assert "Graphify Wiki Export Unavailable" in wiki_md
    assert "fallback content" in wiki_md
    assert export_log["graphify"]["used_fallback"] is True
