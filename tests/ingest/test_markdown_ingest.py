"""Tests for parse_markdown_headings and MarkdownSection."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from memory_mcp.ingest.parser import MarkdownSection, parse_markdown_headings


def _write(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


def test_parse_single_heading() -> None:
    p = _write("# Title\n\nSome content here.\n")
    sections = parse_markdown_headings(p)
    assert len(sections) == 1
    assert sections[0].heading == "Title"
    assert "Some content here" in sections[0].body


def test_parse_multiple_headings() -> None:
    p = _write("# H1\n\nBody1.\n\n## H2\n\nBody2.\n")
    sections = parse_markdown_headings(p)
    assert len(sections) == 2
    assert sections[0].heading == "H1"
    assert sections[0].level == 1
    assert sections[1].heading == "H2"
    assert sections[1].level == 2
    assert sections[1].heading_path == ["H1"]


def test_empty_body_sections_have_empty_body_string() -> None:
    p = _write("# H1\n\n## H2\n\nBody.\n")
    sections = parse_markdown_headings(p)
    assert sections[0].body == ""
    assert sections[1].body == "Body."


def test_no_headings_returns_empty() -> None:
    p = _write("Just some text without headings.\n")
    assert parse_markdown_headings(p) == []


def test_empty_file_returns_empty() -> None:
    p = _write("")
    assert parse_markdown_headings(p) == []


def test_deep_heading_breadcrumb() -> None:
    p = _write("# A\n\n## B\n\n### C\n\nDeep body.\n")
    sections = parse_markdown_headings(p)
    assert len(sections) == 3
    assert sections[2].heading == "C"
    assert sections[2].heading_path == ["A", "B"]


def test_source_path_set() -> None:
    p = _write("# Only\n\nContent.\n")
    sections = parse_markdown_headings(p)
    assert sections[0].source_path == str(p)


def test_returns_markdown_section_instances() -> None:
    p = _write("# Title\n\nBody.\n")
    sections = parse_markdown_headings(p)
    assert isinstance(sections[0], MarkdownSection)
