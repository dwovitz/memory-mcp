"""Tests for ingest parser extractors."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from memory_mcp.ingest.parser import (
    extract_apim_routes,
    extract_markdown_sections,
    extract_mermaid_nodes,
    _stable_ingest_key,
)


SCOPE = {"workspace": "testws", "project": "testproj"}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _expected_key(source_path: str, heading_path: str) -> str:
    raw = f"{source_path}::{heading_path}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Markdown extraction
# ---------------------------------------------------------------------------


def test_extract_markdown_two_headings(tmp_path: Path) -> None:
    """Two headings produce two memories with correct structure."""
    md_file = tmp_path / "doc.md"
    md_file.write_text(
        "# First Heading\n\nSome body text.\n\n## Second Heading\n\nMore content.\n",
        encoding="utf-8",
    )

    memories = extract_markdown_sections(md_file, SCOPE)

    assert len(memories) == 2

    first = memories[0]
    assert "title" not in first
    assert "First Heading" in first["content"]
    assert "Some body text." in first["content"]
    assert first["memory_type"] == "project_fact"
    assert first["applies_to"] == SCOPE
    assert "ingest_key" in first["metadata"]

    second = memories[1]
    assert "title" not in second
    assert "More content." in second["content"]
    assert second["memory_type"] == "project_fact"
    assert "ingest_key" in second["metadata"]


def test_extract_markdown_stable_ingest_keys(tmp_path: Path) -> None:
    """Same file content produces the same ingest_keys on repeated calls."""
    md_file = tmp_path / "stable.md"
    md_file.write_text("# Alpha\n\nBody.\n\n# Beta\n\nOther.\n", encoding="utf-8")

    memories_1 = extract_markdown_sections(md_file, SCOPE)
    memories_2 = extract_markdown_sections(md_file, SCOPE)

    keys_1 = [m["metadata"]["ingest_key"] for m in memories_1]
    keys_2 = [m["metadata"]["ingest_key"] for m in memories_2]
    assert keys_1 == keys_2
    # Keys are 16 hex chars
    for key in keys_1:
        assert len(key) == 16
        int(key, 16)  # valid hex


def test_extract_markdown_ingest_key_is_path_dependent(tmp_path: Path) -> None:
    """Different files with the same heading produce different ingest_keys."""
    content = "# Same Heading\n\nBody.\n"
    file_a = tmp_path / "a.md"
    file_b = tmp_path / "b.md"
    file_a.write_text(content, encoding="utf-8")
    file_b.write_text(content, encoding="utf-8")

    mems_a = extract_markdown_sections(file_a, SCOPE)
    mems_b = extract_markdown_sections(file_b, SCOPE)

    assert mems_a[0]["metadata"]["ingest_key"] != mems_b[0]["metadata"]["ingest_key"]


def test_extract_markdown_empty_file(tmp_path: Path) -> None:
    """Empty markdown file returns no memories."""
    md_file = tmp_path / "empty.md"
    md_file.write_text("", encoding="utf-8")
    assert extract_markdown_sections(md_file, SCOPE) == []


def test_extract_markdown_no_headings(tmp_path: Path) -> None:
    """File with body text but no headings returns no memories."""
    md_file = tmp_path / "nobody.md"
    md_file.write_text("Just some text without any headings.\n", encoding="utf-8")
    assert extract_markdown_sections(md_file, SCOPE) == []


# ---------------------------------------------------------------------------
# Mermaid extraction
# ---------------------------------------------------------------------------

MERMAID_MD = """\
# Diagram

```mermaid
graph TD
  A[Start] --> B(Process)
  B --> C{Decision}
  C --> D[End]
```

Some text.
"""


def test_extract_mermaid_nodes_finds_labels(tmp_path: Path) -> None:
    md_file = tmp_path / "diagram.md"
    md_file.write_text(MERMAID_MD, encoding="utf-8")

    memories = extract_mermaid_nodes(md_file, SCOPE)

    assert len(memories) == 1
    mem = memories[0]
    assert mem["memory_type"] == "project_fact"
    assert mem["applies_to"] == SCOPE
    # Should have found some node labels
    content = mem["content"]
    assert "Start" in content or "Process" in content or "Decision" in content or "End" in content


def test_extract_mermaid_no_blocks_returns_empty(tmp_path: Path) -> None:
    md_file = tmp_path / "plain.md"
    md_file.write_text("# No mermaid here\n\nJust text.\n", encoding="utf-8")
    assert extract_mermaid_nodes(md_file, SCOPE) == []


def test_extract_mermaid_stable_key(tmp_path: Path) -> None:
    md_file = tmp_path / "stable_mermaid.md"
    md_file.write_text(MERMAID_MD, encoding="utf-8")

    mems_1 = extract_mermaid_nodes(md_file, SCOPE)
    mems_2 = extract_mermaid_nodes(md_file, SCOPE)
    assert mems_1[0]["metadata"]["ingest_key"] == mems_2[0]["metadata"]["ingest_key"]


# ---------------------------------------------------------------------------
# APIM / Terraform extraction
# ---------------------------------------------------------------------------

TF_CONTENT = """\
resource "azurerm_api_management" "main" {
  name                = "my-apim"
  location            = var.location
  resource_group_name = var.resource_group_name
  publisher_name      = "Acme Corp"
  publisher_email     = "admin@example.com"
  sku_name            = "Developer_1"
}

resource "azurerm_api_management_api" "demo" {
  name                = "demo-api"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = var.resource_group_name
  revision            = "1"
  display_name        = "Demo API"
  path                = "demo"
  protocols           = ["https"]
}
"""


def test_extract_apim_routes_finds_resources(tmp_path: Path) -> None:
    tf_file = tmp_path / "apim.tf"
    tf_file.write_text(TF_CONTENT, encoding="utf-8")

    memories = extract_apim_routes(tf_file, SCOPE)

    assert len(memories) == 2
    contents = "\n".join(m["content"] for m in memories)
    assert "azurerm_api_management" in contents
    assert "azurerm_api_management_api" in contents

    for mem in memories:
        assert "title" not in mem
        assert mem["memory_type"] == "project_fact"
        assert mem["applies_to"] == SCOPE
        assert len(mem["metadata"]["ingest_key"]) == 16


def test_extract_apim_routes_stable_key(tmp_path: Path) -> None:
    tf_file = tmp_path / "stable.tf"
    tf_file.write_text(TF_CONTENT, encoding="utf-8")

    mems_1 = extract_apim_routes(tf_file, SCOPE)
    mems_2 = extract_apim_routes(tf_file, SCOPE)
    for m1, m2 in zip(mems_1, mems_2):
        assert m1["metadata"]["ingest_key"] == m2["metadata"]["ingest_key"]


def test_extract_apim_routes_empty_file(tmp_path: Path) -> None:
    tf_file = tmp_path / "empty.tf"
    tf_file.write_text("", encoding="utf-8")
    assert extract_apim_routes(tf_file, SCOPE) == []


def test_extract_apim_routes_nonexistent_file() -> None:
    result = extract_apim_routes(Path("/nonexistent/path/apim.tf"), SCOPE)
    assert result == []


# ---------------------------------------------------------------------------
# Stable key helper
# ---------------------------------------------------------------------------


def test_stable_ingest_key_format() -> None:
    key = _stable_ingest_key("docs/arch.md", "Overview > Components")
    assert len(key) == 16
    int(key, 16)  # valid hex


def test_stable_ingest_key_same_input_same_output() -> None:
    k1 = _stable_ingest_key("path/file.md", "Section")
    k2 = _stable_ingest_key("path/file.md", "Section")
    assert k1 == k2


def test_stable_ingest_key_different_inputs_different_outputs() -> None:
    k1 = _stable_ingest_key("path/file.md", "Section A")
    k2 = _stable_ingest_key("path/file.md", "Section B")
    assert k1 != k2
