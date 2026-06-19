"""Workspace ingestion pipeline for seeding memory-mcp from documentation files."""

from memory_mcp.ingest.sources import SourceConfig, load_manifest
from memory_mcp.ingest.parser import extract_markdown_sections, extract_mermaid_nodes, extract_apim_routes
from memory_mcp.ingest.writer import IngestWriter
from memory_mcp.ingest.wiki import (
    WIKI_PROVENANCE,
    WikiIngestResult,
    WikiIngestService,
    WikiSource,
    build_wiki_records,
)
from memory_mcp.ingest.wiki_graph import (
    WIKI_DOCUMENT_ENTITY_TYPE,
    WIKI_REFERENCES_RELATIONSHIP,
    WikiGraphProjection,
    WikiGraphResult,
    WikiGraphService,
    build_wiki_graph_projection,
)

__all__ = [
    "SourceConfig",
    "load_manifest",
    "extract_markdown_sections",
    "extract_mermaid_nodes",
    "extract_apim_routes",
    "IngestWriter",
    "WIKI_PROVENANCE",
    "WikiIngestResult",
    "WikiIngestService",
    "WikiSource",
    "build_wiki_records",
    "WIKI_DOCUMENT_ENTITY_TYPE",
    "WIKI_REFERENCES_RELATIONSHIP",
    "WikiGraphProjection",
    "WikiGraphResult",
    "WikiGraphService",
    "build_wiki_graph_projection",
]
