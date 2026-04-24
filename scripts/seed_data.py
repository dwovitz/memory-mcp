"""Populate the database with synthetic memory test data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from memory_mcp.config import load_database_config
from memory_mcp.db import create_db_engine
from memory_mcp.models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_NAMESPACE = "memory-mcp.seed"


def seed_id(name: str) -> UUID:
    """Return a stable UUID for idempotent seed data."""

    return uuid5(NAMESPACE_URL, f"{SEED_NAMESPACE}:{name}")


ENTITY_IDS = {
    "self": seed_id("entity:self:alex-rivera"),
    "partner": seed_id("entity:person:jordan-lee"),
    "cetirizine": seed_id("entity:medication:cetirizine"),
    "magnesium": seed_id("entity:medication:magnesium-glycinate"),
    "severance": seed_id("entity:show:severance"),
    "ted_lasso": seed_id("entity:show:ted-lasso"),
    "zombie_show": seed_id("entity:show:bleak-zombie-series"),
    "sci_fi": seed_id("entity:genre:sci-fi"),
    "workplace_comedy": seed_id("entity:genre:workplace-comedy"),
    "cozy_mystery": seed_id("entity:genre:cozy-mystery"),
    "dark_tone": seed_id("entity:tone:dark"),
    "hopeful_tone": seed_id("entity:tone:hopeful"),
    "windows_pc": seed_id("entity:device:windows-pc"),
    "phone": seed_id("entity:device:android-phone"),
    "netflix": seed_id("entity:service:netflix"),
    "spotify": seed_id("entity:service:spotify"),
    "codex": seed_id("entity:app:codex"),
    "memory_mcp": seed_id("entity:project:memory-mcp"),
    "coding_preferences": seed_id("entity:preference-area:coding"),
}

MEMORY_IDS = {
    "self_profile": seed_id("memory:self-profile"),
    "partner_profile": seed_id("memory:partner-profile"),
    "cetirizine": seed_id("memory:medication:cetirizine"),
    "magnesium": seed_id("memory:medication:magnesium"),
    "likes_severance": seed_id("memory:entertainment:likes-severance"),
    "likes_ted_lasso": seed_id("memory:entertainment:likes-ted-lasso"),
    "dislikes_zombie_show": seed_id("memory:entertainment:dislikes-zombie-show"),
    "inferred_sci_fi": seed_id("memory:inferred:character-driven-sci-fi"),
    "windows_device": seed_id("memory:device:windows-pc"),
    "services": seed_id("memory:services:streaming-audio"),
    "project_fact": seed_id("memory:project:memory-mcp-local-first"),
    "codex_app": seed_id("memory:app:codex"),
    "old_coding_pref": seed_id("memory:coding:old-large-files"),
    "new_coding_pref": seed_id("memory:coding:small-modules"),
    "archived_noise": seed_id("memory:archived:one-off-lunch"),
}

RELATIONSHIP_IDS = {
    "partner": seed_id("relationship:self-partner"),
    "cetirizine_for_self": seed_id("relationship:cetirizine-for-self"),
    "magnesium_for_self": seed_id("relationship:magnesium-for-self"),
    "severance_sci_fi": seed_id("relationship:severance-sci-fi"),
    "ted_lasso_workplace": seed_id("relationship:ted-lasso-workplace"),
    "zombie_dark": seed_id("relationship:zombie-dark-tone"),
    "project_uses_codex": seed_id("relationship:memory-mcp-uses-codex"),
    "self_uses_windows": seed_id("relationship:self-uses-windows-pc"),
}

PROFILE_IDS = {
    "daily_context": seed_id("retrieval-profile:daily-context"),
    "coding_context": seed_id("retrieval-profile:coding-context"),
}

PACKET_IDS = {
    "coding": seed_id("context-packet:coding-snapshot"),
    "entertainment": seed_id("context-packet:entertainment-snapshot"),
}


def common_metadata(category: str, *, explicit: bool = True) -> dict[str, Any]:
    return {
        "seed": True,
        "synthetic": True,
        "category": category,
        "source": "scripts/seed_data.py",
        "capture_method": "explicit" if explicit else "inferred",
    }


def evidence(kind: str, text: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": kind,
            "text": text,
            "source": "synthetic seed data",
        }
    ]


def rows() -> dict[str, list[dict[str, Any]]]:
    entities = [
        {
            "id": ENTITY_IDS["self"],
            "entity_type": "person",
            "name": "Alex Rivera",
            "aliases": ["self", "primary user"],
            "attributes": {"role": "self", "synthetic": True},
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "personal"},
        },
        {
            "id": ENTITY_IDS["partner"],
            "entity_type": "person",
            "name": "Jordan Lee",
            "aliases": ["partner"],
            "attributes": {"relationship": "partner", "synthetic": True},
            "confidence": "0.980",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "personal"},
        },
        {
            "id": ENTITY_IDS["cetirizine"],
            "entity_type": "medication",
            "name": "Cetirizine",
            "aliases": ["Zyrtec"],
            "attributes": {"form": "tablet", "example_only": True},
            "confidence": "0.950",
            "sensitivity": "sensitive",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["magnesium"],
            "entity_type": "medication",
            "name": "Magnesium glycinate",
            "aliases": ["magnesium"],
            "attributes": {"form": "capsule", "example_only": True},
            "confidence": "0.850",
            "sensitivity": "sensitive",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["severance"],
            "entity_type": "show",
            "name": "Severance",
            "aliases": [],
            "attributes": {"service": "Apple TV+", "liked": True},
            "confidence": "0.920",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["ted_lasso"],
            "entity_type": "show",
            "name": "Ted Lasso",
            "aliases": [],
            "attributes": {"service": "Apple TV+", "liked": True},
            "confidence": "0.900",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["partner"])},
        },
        {
            "id": ENTITY_IDS["zombie_show"],
            "entity_type": "show",
            "name": "Bleak Zombie Series",
            "aliases": ["sample disliked show"],
            "attributes": {"liked": False, "reason": "too grim"},
            "confidence": "0.800",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["sci_fi"],
            "entity_type": "genre",
            "name": "Science fiction",
            "aliases": ["sci-fi"],
            "attributes": {"media": "television"},
            "confidence": "0.900",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
        {
            "id": ENTITY_IDS["workplace_comedy"],
            "entity_type": "genre",
            "name": "Workplace comedy",
            "aliases": [],
            "attributes": {"media": "television"},
            "confidence": "0.880",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
        {
            "id": ENTITY_IDS["cozy_mystery"],
            "entity_type": "genre",
            "name": "Cozy mystery",
            "aliases": [],
            "attributes": {"media": "books"},
            "confidence": "0.640",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
        {
            "id": ENTITY_IDS["dark_tone"],
            "entity_type": "tone",
            "name": "Dark and grim",
            "aliases": ["bleak"],
            "attributes": {"preference": "avoid_when_sustained"},
            "confidence": "0.720",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
        {
            "id": ENTITY_IDS["hopeful_tone"],
            "entity_type": "tone",
            "name": "Hopeful and character-driven",
            "aliases": ["warm", "optimistic"],
            "attributes": {"preference": "likes"},
            "confidence": "0.760",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
        {
            "id": ENTITY_IDS["windows_pc"],
            "entity_type": "device",
            "name": "Windows development PC",
            "aliases": ["desktop", "Windows machine"],
            "attributes": {"os": "Windows", "primary_for": "development"},
            "confidence": "0.990",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["phone"],
            "entity_type": "device",
            "name": "Android phone",
            "aliases": ["phone"],
            "attributes": {"os": "Android", "example_only": True},
            "confidence": "0.700",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["netflix"],
            "entity_type": "service",
            "name": "Netflix",
            "aliases": [],
            "attributes": {"category": "streaming video"},
            "confidence": "0.780",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"household": True},
        },
        {
            "id": ENTITY_IDS["spotify"],
            "entity_type": "service",
            "name": "Spotify",
            "aliases": [],
            "attributes": {"category": "music"},
            "confidence": "0.750",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": ENTITY_IDS["codex"],
            "entity_type": "app",
            "name": "Codex",
            "aliases": ["coding assistant"],
            "attributes": {"category": "developer tool"},
            "confidence": "0.980",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
        },
        {
            "id": ENTITY_IDS["memory_mcp"],
            "entity_type": "project",
            "name": "memory-mcp",
            "aliases": ["local memory MCP"],
            "attributes": {"language": "Python", "database": "PostgreSQL"},
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
        },
        {
            "id": ENTITY_IDS["coding_preferences"],
            "entity_type": "preference_area",
            "name": "Coding preferences",
            "aliases": ["engineering style"],
            "attributes": {"domain": "software development"},
            "confidence": "0.950",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
        },
    ]
    for entity in entities:
        entity["attributes"] = {"seed": True, "synthetic": True, **entity["attributes"]}

    memories = [
        {
            "id": MEMORY_IDS["self_profile"],
            "entity_id": ENTITY_IDS["self"],
            "memory_type": "personal_fact",
            "content": "Alex Rivera is the synthetic primary user for local memory testing.",
            "summary": "Synthetic self profile.",
            "evidence": evidence("explicit", "Seed data defines Alex Rivera as the primary user."),
            "metadata": common_metadata("people"),
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
        },
        {
            "id": MEMORY_IDS["partner_profile"],
            "entity_id": ENTITY_IDS["partner"],
            "memory_type": "personal_fact",
            "content": "Jordan Lee is the synthetic partner used for relationship test data.",
            "summary": "Synthetic partner profile.",
            "evidence": evidence("explicit", "Seed data defines Jordan Lee as partner."),
            "metadata": common_metadata("people"),
            "confidence": "0.980",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["partner"])},
        },
        {
            "id": MEMORY_IDS["cetirizine"],
            "entity_id": ENTITY_IDS["cetirizine"],
            "memory_type": "medication",
            "content": "Synthetic example: Alex takes cetirizine 10 mg in the evening for seasonal allergies.",
            "summary": "Example cetirizine medication memory.",
            "evidence": evidence("explicit", "User stated cetirizine example in seed scenario."),
            "metadata": common_metadata("medications"),
            "confidence": "0.950",
            "sensitivity": "sensitive",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"]), "time": "evening"},
        },
        {
            "id": MEMORY_IDS["magnesium"],
            "entity_id": ENTITY_IDS["magnesium"],
            "memory_type": "medication",
            "content": "Synthetic example: Alex sometimes takes magnesium glycinate before bed.",
            "summary": "Example magnesium medication memory.",
            "evidence": evidence("explicit", "Seed scenario includes magnesium glycinate."),
            "metadata": common_metadata("medications"),
            "confidence": "0.850",
            "sensitivity": "sensitive",
            "status": "active",
            "applies_to": {"person_id": str(ENTITY_IDS["self"]), "time": "bedtime"},
        },
        {
            "id": MEMORY_IDS["likes_severance"],
            "entity_id": ENTITY_IDS["severance"],
            "memory_type": "entertainment_preference",
            "content": "Alex likes Severance for its mystery, workplace satire, and controlled sci-fi tone.",
            "summary": "Likes Severance.",
            "evidence": evidence("explicit", "Seed scenario says Alex liked Severance."),
            "metadata": common_metadata("entertainment"),
            "confidence": "0.920",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {
                "person_id": str(ENTITY_IDS["self"]),
                "media": "show",
                "scope": "entertainment",
            },
        },
        {
            "id": MEMORY_IDS["likes_ted_lasso"],
            "entity_id": ENTITY_IDS["ted_lasso"],
            "memory_type": "entertainment_preference",
            "content": "Jordan likes Ted Lasso because it is warm, funny, and character-driven.",
            "summary": "Partner likes Ted Lasso.",
            "evidence": evidence("explicit", "Seed scenario says Jordan liked Ted Lasso."),
            "metadata": common_metadata("entertainment"),
            "confidence": "0.900",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {
                "person_id": str(ENTITY_IDS["partner"]),
                "media": "show",
                "scope": "entertainment",
            },
        },
        {
            "id": MEMORY_IDS["dislikes_zombie_show"],
            "entity_id": ENTITY_IDS["zombie_show"],
            "memory_type": "entertainment_preference",
            "content": "Alex disliked the bleak zombie series because it felt relentlessly grim.",
            "summary": "Dislikes sustained bleak zombie tone.",
            "evidence": evidence("explicit", "Seed scenario marks the zombie series as disliked."),
            "metadata": common_metadata("entertainment"),
            "confidence": "0.800",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {
                "person_id": str(ENTITY_IDS["self"]),
                "media": "show",
                "scope": "entertainment",
            },
        },
        {
            "id": MEMORY_IDS["inferred_sci_fi"],
            "entity_id": ENTITY_IDS["sci_fi"],
            "memory_type": "inferred_preference",
            "content": "Alex likely prefers character-driven sci-fi with mystery over bleak survival horror.",
            "summary": "Inferred sci-fi preference.",
            "evidence": evidence("inference", "Inferred from liking Severance and disliking a bleak zombie show."),
            "metadata": common_metadata("entertainment", explicit=False),
            "confidence": "0.680",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {
                "person_id": str(ENTITY_IDS["self"]),
                "inferred": True,
                "scope": "entertainment",
            },
        },
        {
            "id": MEMORY_IDS["windows_device"],
            "entity_id": ENTITY_IDS["windows_pc"],
            "memory_type": "device_fact",
            "content": "Alex's development environment is a Windows PC using Docker Desktop.",
            "summary": "Windows development setup.",
            "evidence": evidence("explicit", "Project setup targets Windows and Docker Desktop."),
            "metadata": common_metadata("devices"),
            "confidence": "0.990",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development", "os": "Windows"},
        },
        {
            "id": MEMORY_IDS["services"],
            "entity_id": ENTITY_IDS["netflix"],
            "memory_type": "service_fact",
            "content": "Synthetic household service examples include Netflix for video and Spotify for music.",
            "summary": "Example services.",
            "evidence": evidence("explicit", "Seed data includes services for testing app knowledge."),
            "metadata": common_metadata("services"),
            "confidence": "0.760",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"household": True},
        },
        {
            "id": MEMORY_IDS["project_fact"],
            "entity_id": ENTITY_IDS["memory_mcp"],
            "memory_type": "project_fact",
            "content": "memory-mcp is a local-first personal memory MCP server using Python, PostgreSQL, Docker, and pgvector.",
            "summary": "memory-mcp architecture fact.",
            "evidence": evidence("explicit", "Project requirements define the local-first memory MCP architecture."),
            "metadata": common_metadata("project"),
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"project": "memory-mcp"},
        },
        {
            "id": MEMORY_IDS["codex_app"],
            "entity_id": ENTITY_IDS["codex"],
            "memory_type": "app_knowledge",
            "content": "Codex is used as the local coding assistant while building the memory-mcp project.",
            "summary": "Codex app usage.",
            "evidence": evidence("explicit", "Project work is being performed through Codex."),
            "metadata": common_metadata("app"),
            "confidence": "0.980",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"project": "memory-mcp", "app": "Codex"},
        },
        {
            "id": MEMORY_IDS["old_coding_pref"],
            "entity_id": ENTITY_IDS["coding_preferences"],
            "memory_type": "coding_preference",
            "content": "Older synthetic preference: Alex preferred large single-file prototypes.",
            "summary": "Superseded coding preference.",
            "evidence": evidence("explicit", "Older seed example retained for superseding lifecycle tests."),
            "metadata": common_metadata("coding"),
            "confidence": "0.700",
            "sensitivity": "normal",
            "status": "superseded",
            "applies_to": {"scope": "development"},
            "superseded_at": datetime(2026, 4, 23, tzinfo=timezone.utc),
        },
        {
            "id": MEMORY_IDS["new_coding_pref"],
            "entity_id": ENTITY_IDS["coding_preferences"],
            "memory_type": "coding_preference",
            "content": "Alex prefers small, modular Python changes with clear summaries and no overbuilding.",
            "summary": "Current coding preference.",
            "evidence": evidence("explicit", "Seed scenario includes coding preferences."),
            "metadata": common_metadata("coding"),
            "confidence": "0.960",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
            "supersedes_memory_id": MEMORY_IDS["old_coding_pref"],
        },
        {
            "id": MEMORY_IDS["archived_noise"],
            "entity_id": ENTITY_IDS["self"],
            "memory_type": "ephemeral_note",
            "content": "Archived synthetic note: Alex ate a turkey sandwich for lunch once.",
            "summary": "Archived low-value one-off note.",
            "evidence": evidence("explicit", "Seed example for pruning low-value memories."),
            "metadata": common_metadata("pruning"),
            "confidence": "0.600",
            "sensitivity": "normal",
            "status": "archived",
            "applies_to": {"person_id": str(ENTITY_IDS["self"]), "value": "low"},
        },
    ]

    tags = [
        tag("medications", "cetirizine", "health"),
        tag("medications", "magnesium", "health"),
        tag("entertainment", "likes_severance", "liked"),
        tag("entertainment", "likes_ted_lasso", "liked"),
        tag("entertainment", "dislikes_zombie_show", "disliked"),
        tag("inferred", "inferred_sci_fi", "inferred"),
        tag("devices", "windows_device", "windows"),
        tag("services", "services", "subscription"),
        tag("project", "project_fact", "architecture"),
        tag("app", "codex_app", "codex"),
        tag("coding", "new_coding_pref", "preference"),
        tag("archived", "archived_noise", "low-value", status="archived"),
    ]

    relationships = [
        relationship("partner", "self", "partner", "partner", "Alex and Jordan are synthetic partners."),
        relationship("cetirizine_for_self", "self", "cetirizine", "takes_medication", "Alex takes cetirizine in this synthetic example.", sensitivity="sensitive"),
        relationship("magnesium_for_self", "self", "magnesium", "takes_medication", "Alex sometimes takes magnesium glycinate.", confidence="0.850", sensitivity="sensitive"),
        relationship("severance_sci_fi", "severance", "sci_fi", "has_genre", "Severance is categorized as sci-fi."),
        relationship("ted_lasso_workplace", "ted_lasso", "workplace_comedy", "has_genre", "Ted Lasso is categorized as workplace comedy."),
        relationship("zombie_dark", "zombie_show", "dark_tone", "has_tone", "The disliked zombie show has a bleak tone.", confidence="0.800"),
        relationship("project_uses_codex", "memory_mcp", "codex", "uses_tool", "memory-mcp is built with Codex assistance."),
        relationship("self_uses_windows", "self", "windows_pc", "uses_device", "Alex uses a Windows PC for development."),
    ]

    retrieval_profiles = [
        {
            "id": PROFILE_IDS["daily_context"],
            "name": "daily_context",
            "description": "Synthetic profile for everyday personal context packets.",
            "query_config": {"limit": 20, "include_inferred": True},
            "filters": {"status": ["active"], "sensitivity": ["normal"]},
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "daily"},
        },
        {
            "id": PROFILE_IDS["coding_context"],
            "name": "coding_context",
            "description": "Synthetic profile for project and coding preference context.",
            "query_config": {"limit": 12, "prefer_recent": True},
            "filters": {"tags": ["coding", "project", "app"], "status": ["active"]},
            "confidence": "1.000",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
        },
    ]

    context_packets = [
        {
            "id": PACKET_IDS["coding"],
            "retrieval_profile_id": PROFILE_IDS["coding_context"],
            "title": "Coding Context Snapshot",
            "purpose": "Synthetic compact packet for project work.",
            "content": "Project: memory-mcp is local-first Python/PostgreSQL. Preference: keep changes modular and avoid overbuilding.",
            "token_estimate": 34,
            "metadata": common_metadata("context_packet"),
            "confidence": "0.950",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "development"},
        },
        {
            "id": PACKET_IDS["entertainment"],
            "retrieval_profile_id": PROFILE_IDS["daily_context"],
            "title": "Entertainment Preference Snapshot",
            "purpose": "Synthetic compact packet for recommendations.",
            "content": "Alex likes mystery-driven sci-fi such as Severance and dislikes relentlessly bleak zombie stories.",
            "token_estimate": 28,
            "metadata": common_metadata("context_packet"),
            "confidence": "0.820",
            "sensitivity": "normal",
            "status": "active",
            "applies_to": {"scope": "entertainment"},
        },
    ]

    context_packet_memories = [
        packet_memory("coding", "project_fact", 1),
        packet_memory("coding", "new_coding_pref", 2),
        packet_memory("coding", "codex_app", 3),
        packet_memory("entertainment", "likes_severance", 1),
        packet_memory("entertainment", "dislikes_zombie_show", 2),
        packet_memory("entertainment", "inferred_sci_fi", 3),
    ]

    pruning_log = [
        {
            "id": seed_id("pruning-log:archived-noise"),
            "memory_id": MEMORY_IDS["archived_noise"],
            "action": "archive",
            "reason": "Low-value one-off personal note retained only as archived seed data.",
            "confidence": "0.900",
            "sensitivity": "normal",
            "status": "applied",
            "applies_to": {"person_id": str(ENTITY_IDS["self"])},
            "before_state": {"status": "active"},
            "after_state": {"status": "archived"},
            "metadata": common_metadata("pruning"),
        },
        {
            "id": seed_id("pruning-log:superseded-coding-pref"),
            "memory_id": MEMORY_IDS["old_coding_pref"],
            "action": "supersede",
            "reason": "Older coding preference replaced by current modularity preference.",
            "confidence": "0.950",
            "sensitivity": "normal",
            "status": "applied",
            "applies_to": {"scope": "development"},
            "before_state": {"status": "active"},
            "after_state": {"status": "superseded", "superseded_by": str(MEMORY_IDS["new_coding_pref"])},
            "metadata": common_metadata("pruning"),
        },
    ]

    return {
        "entities": entities,
        "memories": memories,
        "memory_tags": tags,
        "relationships": relationships,
        "retrieval_profiles": retrieval_profiles,
        "context_packets": context_packets,
        "context_packet_memories": context_packet_memories,
        "pruning_log": pruning_log,
    }


def tag(category: str, memory_key: str, value: str, *, status: str = "active") -> dict[str, Any]:
    return {
        "id": seed_id(f"memory-tag:{memory_key}:{value}"),
        "memory_id": MEMORY_IDS[memory_key],
        "tag": value,
        "attributes": {"category": category, "seed": True},
        "confidence": "0.900",
        "sensitivity": "normal",
        "status": status,
        "applies_to": {"category": category},
    }


def relationship(
    key: str,
    source_key: str,
    target_key: str,
    relationship_type: str,
    description: str,
    *,
    confidence: str = "0.900",
    sensitivity: str = "normal",
) -> dict[str, Any]:
    return {
        "id": RELATIONSHIP_IDS[key],
        "source_entity_id": ENTITY_IDS[source_key],
        "target_entity_id": ENTITY_IDS[target_key],
        "relationship_type": relationship_type,
        "description": description,
        "evidence": evidence("explicit", description),
        "metadata": common_metadata("relationships", explicit=True),
        "confidence": confidence,
        "sensitivity": sensitivity,
        "status": "active",
        "applies_to": {"source": source_key, "target": target_key},
    }


def packet_memory(packet_key: str, memory_key: str, rank: int) -> dict[str, Any]:
    return {
        "id": seed_id(f"context-packet-memory:{packet_key}:{memory_key}"),
        "context_packet_id": PACKET_IDS[packet_key],
        "memory_id": MEMORY_IDS[memory_key],
        "rank": rank,
        "metadata": {"seed": True, "synthetic": True},
    }


def upsert_rows(connection: Any, table: Table, table_rows: Iterable[Mapping[str, Any]]) -> int:
    rows_to_insert = list(table_rows)
    if not rows_to_insert:
        return 0

    for row in rows_to_insert:
        statement = insert(table).values(row)
        update_columns = {
            column_name: getattr(statement.excluded, column_name)
            for column_name in row
            if column_name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.id],
            set_=update_columns,
        )
        connection.execute(statement)
    return len(rows_to_insert)


def main() -> int:
    config = load_database_config(
        PROJECT_ROOT / ".env",
        require_env_file=True,
        require_values=True,
    )
    engine = create_db_engine(config)
    seed_rows = rows()

    try:
        with engine.begin() as connection:
            inserted_counts = {
                table_name: upsert_rows(connection, Base.metadata.tables[table_name], table_rows)
                for table_name, table_rows in seed_rows.items()
            }
    finally:
        engine.dispose()

    print("Seed data upsert complete:")
    for table_name, count in inserted_counts.items():
        print(f"- {table_name}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
