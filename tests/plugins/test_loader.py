from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_mcp.plugins.errors import PluginError
from memory_mcp.plugins.loader import load_marketplace, load_plugin_manifest


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def valid_manifest() -> dict:
    return {
        "schema_version": "1",
        "id": "memory-mcp-core",
        "display_name": "memory-mcp Core",
        "description": "Default memory-mcp client setup pack.",
        "version": "0.1.0",
        "min_memory_mcp_version": "0.1.0",
        "update_channel": "stable",
        "category": "Developer Tools",
        "client_targets": {
            "codex": {
                "outputs": [
                    {"source": "clients/codex/AGENTS.md", "target": "AGENTS.md"},
                    {"source": "clients/codex/config.example.toml", "target": "config.example.toml"},
                ]
            },
            "claude-code": {
                "outputs": [
                    {"source": "clients/claude-code/CLAUDE.md", "target": "CLAUDE.md"}
                ]
            },
        },
        "hooks": [
            {"event": "PostToolUse", "source": "hooks/post_tool_use.py"}
        ],
        "server_modes": ["local-docker", "local-http", "remote-authenticated", "manual-stdio"],
    }


def test_load_plugin_manifest_accepts_valid_manifest(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "memory-mcp-core"
    write_json(plugin_root / "plugin.memory-mcp.json", valid_manifest())
    (plugin_root / "clients" / "codex").mkdir(parents=True)
    (plugin_root / "clients" / "codex" / "AGENTS.md").write_text("# workflow\n", encoding="utf-8")
    (plugin_root / "clients" / "codex" / "config.example.toml").write_text("config\n", encoding="utf-8")
    (plugin_root / "clients" / "claude-code").mkdir(parents=True)
    (plugin_root / "clients" / "claude-code" / "CLAUDE.md").write_text("# workflow\n", encoding="utf-8")
    (plugin_root / "hooks").mkdir(parents=True)
    (plugin_root / "hooks" / "post_tool_use.py").write_text("print('hook')\n", encoding="utf-8")

    manifest = load_plugin_manifest(plugin_root)

    assert manifest.id == "memory-mcp-core"
    assert manifest.version == "0.1.0"
    assert list(manifest.client_targets) == ["codex", "claude-code"]
    assert manifest.client_targets["codex"].outputs[0].target == "AGENTS.md"
    assert manifest.server_modes == ("local-docker", "local-http", "remote-authenticated", "manual-stdio")


def test_load_plugin_manifest_rejects_missing_required_fields(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "memory-mcp-core"
    manifest = valid_manifest()
    del manifest["version"]
    write_json(plugin_root / "plugin.memory-mcp.json", manifest)

    with pytest.raises(PluginError, match="version"):
        load_plugin_manifest(plugin_root)


def test_load_plugin_manifest_rejects_missing_declared_output(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins" / "memory-mcp-core"
    write_json(plugin_root / "plugin.memory-mcp.json", valid_manifest())

    with pytest.raises(PluginError, match="clients/codex/AGENTS.md"):
        load_plugin_manifest(plugin_root)


def test_load_marketplace_lists_local_plugins_in_order(tmp_path: Path) -> None:
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    first = tmp_path / "plugins" / "memory-mcp-core"
    second = tmp_path / "plugins" / "memory-mcp-extra"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    write_json(
        marketplace_path,
        {
            "name": "memory-mcp-local-marketplace",
            "interface": {"displayName": "memory-mcp Local Marketplace"},
            "plugins": [
                {"name": "memory-mcp-core", "source": {"source": "local", "path": "../../plugins/memory-mcp-core"}},
                {"name": "memory-mcp-extra", "source": {"source": "local", "path": "../../plugins/memory-mcp-extra"}},
            ],
        },
    )

    marketplace = load_marketplace(marketplace_path)

    assert [entry.name for entry in marketplace.plugins] == ["memory-mcp-core", "memory-mcp-extra"]
    assert marketplace.plugins[0].path == first.resolve()
    assert marketplace.plugins[1].path == second.resolve()
