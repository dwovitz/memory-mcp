# Plugin Package Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `MMCP-016A`: local plugin package discovery, manifest validation, marketplace loading, deterministic render-only client outputs, and focused `memory-mcp plugins` commands.

**Architecture:** Add a small `memory_mcp.plugins` package with pure data models, loaders, renderer, and CLI command handlers. The bundled `plugins/memory-mcp-core` package mirrors the existing `client-setups/` assets as the first source package, while rendering writes reviewable files into an output directory without editing live client config. `src/memory_mcp/main.py` dispatches to plugin commands only when the first argument is `plugins`; otherwise it keeps launching the MCP server exactly as today.

**Tech Stack:** Python 3.12, standard library `argparse`, `dataclasses`, `json`, `pathlib`, `shutil`; pytest; existing Hatch package layout under `src/`.

---

## File Structure

- Create `src/memory_mcp/plugins/__init__.py`: exports public plugin helpers.
- Create `src/memory_mcp/plugins/errors.py`: plugin-specific exception type.
- Create `src/memory_mcp/plugins/models.py`: dataclasses for manifest, clients, render outputs, and marketplace entries.
- Create `src/memory_mcp/plugins/loader.py`: JSON parsing and validation for plugin manifests and marketplace files.
- Create `src/memory_mcp/plugins/renderer.py`: deterministic file renderer with overwrite protection.
- Create `src/memory_mcp/plugins/cli.py`: `memory-mcp plugins list/show/render` parser and command handlers.
- Modify `src/memory_mcp/main.py`: route `plugins` subcommands to `memory_mcp.plugins.cli.run_plugins_cli`, keep server behavior unchanged otherwise.
- Create `plugins/memory-mcp-core/.codex-plugin/plugin.json`: Codex-compatible local plugin metadata.
- Create `plugins/memory-mcp-core/plugin.memory-mcp.json`: memory-mcp manifest consumed by the loader.
- Create `plugins/memory-mcp-core/clients/...`: package copies of current client setup assets.
- Create `plugins/memory-mcp-core/hooks/...`: package copies of current hook scripts.
- Create `plugins/memory-mcp-core/README.md`: bundled plugin summary and render examples.
- Create `.agents/plugins/marketplace.json`: local marketplace entry for `memory-mcp-core`.
- Create `tests/plugins/test_loader.py`: manifest and marketplace loader tests.
- Create `tests/plugins/test_renderer.py`: deterministic renderer tests.
- Create `tests/plugins/test_cli.py`: focused plugin CLI dispatch tests.
- Modify `tests/test_mcp_tools.py`: keep client setup coverage and add a small docs assertion for plugin rendering.
- Modify `client-setups/README.md`: mark plugin rendering as preferred while preserving manual template instructions.

---

### Task 1: Add Manifest And Marketplace Loader Tests

**Files:**
- Create: `tests/plugins/test_loader.py`
- Create: `tests/plugins/__init__.py`
- Create later in this task: `src/memory_mcp/plugins/errors.py`
- Create later in this task: `src/memory_mcp/plugins/models.py`
- Create later in this task: `src/memory_mcp/plugins/loader.py`
- Create later in this task: `src/memory_mcp/plugins/__init__.py`

- [ ] **Step 1: Write the failing loader tests**

Create `tests/plugins/__init__.py` as an empty package marker.

Create `tests/plugins/test_loader.py`:

```python
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
```

- [ ] **Step 2: Run loader tests to verify they fail**

Run:

```powershell
pytest tests/plugins/test_loader.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'memory_mcp.plugins'`.

- [ ] **Step 3: Add minimal plugin model and loader implementation**

Create `src/memory_mcp/plugins/errors.py`:

```python
"""Plugin marketplace exceptions."""

from __future__ import annotations


class PluginError(ValueError):
    """Raised when a plugin package or marketplace file is invalid."""
```

Create `src/memory_mcp/plugins/models.py`:

```python
"""Data models for local memory-mcp plugin packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginOutput:
    source: Path
    target: Path


@dataclass(frozen=True)
class PluginClientTarget:
    name: str
    outputs: tuple[PluginOutput, ...]


@dataclass(frozen=True)
class PluginHook:
    event: str
    source: Path


@dataclass(frozen=True)
class PluginManifest:
    root: Path
    schema_version: str
    id: str
    display_name: str
    description: str
    version: str
    min_memory_mcp_version: str
    update_channel: str
    category: str
    client_targets: dict[str, PluginClientTarget]
    hooks: tuple[PluginHook, ...]
    server_modes: tuple[str, ...]


@dataclass(frozen=True)
class MarketplaceEntry:
    name: str
    path: Path


@dataclass(frozen=True)
class Marketplace:
    name: str
    display_name: str
    plugins: tuple[MarketplaceEntry, ...]
```

Create `src/memory_mcp/plugins/loader.py`:

```python
"""Load and validate local memory-mcp plugin packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory_mcp.plugins.errors import PluginError
from memory_mcp.plugins.models import (
    Marketplace,
    MarketplaceEntry,
    PluginClientTarget,
    PluginHook,
    PluginManifest,
    PluginOutput,
)

REQUIRED_MANIFEST_FIELDS = (
    "schema_version",
    "id",
    "display_name",
    "description",
    "version",
    "min_memory_mcp_version",
    "update_channel",
    "category",
    "client_targets",
    "server_modes",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PluginError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PluginError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PluginError(f"expected JSON object in {path}")
    return payload


def _require_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PluginError(f"manifest field {field} is required")
    return value


def _resolve_package_path(root: Path, raw_path: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise PluginError("plugin paths must be non-empty strings")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise PluginError(f"plugin path must stay inside package: {raw_path}")
    return root / path


def _load_outputs(root: Path, client_name: str, raw_client: Any) -> PluginClientTarget:
    if not isinstance(raw_client, dict):
        raise PluginError(f"client target {client_name} must be an object")
    raw_outputs = raw_client.get("outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise PluginError(f"client target {client_name} must declare outputs")
    outputs: list[PluginOutput] = []
    for raw_output in raw_outputs:
        if not isinstance(raw_output, dict):
            raise PluginError(f"client output for {client_name} must be an object")
        source_raw = raw_output.get("source")
        target_raw = raw_output.get("target")
        source = _resolve_package_path(root, source_raw)
        if not source.is_file():
            raise PluginError(f"declared output source does not exist: {source_raw}")
        if not isinstance(target_raw, str) or not target_raw.strip():
            raise PluginError(f"client output for {client_name} needs target")
        target = Path(target_raw)
        if target.is_absolute() or ".." in target.parts:
            raise PluginError(f"render target must be relative and safe: {target_raw}")
        outputs.append(PluginOutput(source=source, target=target))
    return PluginClientTarget(name=client_name, outputs=tuple(outputs))


def load_plugin_manifest(plugin_root: Path) -> PluginManifest:
    root = plugin_root.resolve()
    payload = _read_json(root / "plugin.memory-mcp.json")
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in payload:
            raise PluginError(f"manifest field {field} is required")
    client_targets_raw = payload["client_targets"]
    if not isinstance(client_targets_raw, dict) or not client_targets_raw:
        raise PluginError("manifest field client_targets must be a non-empty object")
    client_targets = {
        name: _load_outputs(root, name, raw_client)
        for name, raw_client in client_targets_raw.items()
    }
    hooks_raw = payload.get("hooks", [])
    if not isinstance(hooks_raw, list):
        raise PluginError("manifest field hooks must be a list")
    hooks: list[PluginHook] = []
    for raw_hook in hooks_raw:
        if not isinstance(raw_hook, dict):
            raise PluginError("hook entries must be objects")
        event = raw_hook.get("event")
        source_raw = raw_hook.get("source")
        if not isinstance(event, str) or not event.strip():
            raise PluginError("hook event is required")
        source = _resolve_package_path(root, source_raw)
        if not source.is_file():
            raise PluginError(f"declared hook source does not exist: {source_raw}")
        hooks.append(PluginHook(event=event, source=source))
    server_modes = payload["server_modes"]
    if not isinstance(server_modes, list) or not all(isinstance(item, str) and item for item in server_modes):
        raise PluginError("manifest field server_modes must be a non-empty list of strings")
    return PluginManifest(
        root=root,
        schema_version=_require_text(payload, "schema_version"),
        id=_require_text(payload, "id"),
        display_name=_require_text(payload, "display_name"),
        description=_require_text(payload, "description"),
        version=_require_text(payload, "version"),
        min_memory_mcp_version=_require_text(payload, "min_memory_mcp_version"),
        update_channel=_require_text(payload, "update_channel"),
        category=_require_text(payload, "category"),
        client_targets=client_targets,
        hooks=tuple(hooks),
        server_modes=tuple(server_modes),
    )


def load_marketplace(marketplace_path: Path) -> Marketplace:
    path = marketplace_path.resolve()
    payload = _read_json(path)
    plugins_raw = payload.get("plugins")
    if not isinstance(plugins_raw, list):
        raise PluginError("marketplace field plugins must be a list")
    entries: list[MarketplaceEntry] = []
    for raw_entry in plugins_raw:
        if not isinstance(raw_entry, dict):
            raise PluginError("marketplace plugin entries must be objects")
        name = raw_entry.get("name")
        source = raw_entry.get("source")
        if not isinstance(name, str) or not name.strip():
            raise PluginError("marketplace plugin name is required")
        if not isinstance(source, dict) or source.get("source") != "local":
            raise PluginError(f"marketplace plugin {name} must use local source")
        source_path = source.get("path")
        if not isinstance(source_path, str) or not source_path.strip():
            raise PluginError(f"marketplace plugin {name} needs source.path")
        resolved = (path.parent / source_path).resolve()
        if not resolved.exists():
            raise PluginError(f"marketplace plugin path does not exist: {source_path}")
        entries.append(MarketplaceEntry(name=name, path=resolved))
    interface = payload.get("interface", {})
    display_name = interface.get("displayName") if isinstance(interface, dict) else None
    return Marketplace(
        name=str(payload.get("name", "")),
        display_name=display_name or str(payload.get("name", "")),
        plugins=tuple(entries),
    )
```

Create `src/memory_mcp/plugins/__init__.py`:

```python
"""Local plugin marketplace helpers for memory-mcp."""

from memory_mcp.plugins.loader import load_marketplace, load_plugin_manifest

__all__ = ["load_marketplace", "load_plugin_manifest"]
```

- [ ] **Step 4: Run loader tests**

Run:

```powershell
pytest tests/plugins/test_loader.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit loader foundation**

Run:

```powershell
git add tests/plugins/test_loader.py tests/plugins/__init__.py src/memory_mcp/plugins
git commit -m "feat(plugins): add manifest and marketplace loaders"
```

---

### Task 2: Add The Bundled memory-mcp-core Plugin Package

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/memory-mcp-core/.codex-plugin/plugin.json`
- Create: `plugins/memory-mcp-core/plugin.memory-mcp.json`
- Create: `plugins/memory-mcp-core/README.md`
- Create: `plugins/memory-mcp-core/clients/codex/AGENTS.md`
- Create: `plugins/memory-mcp-core/clients/codex/config.example.toml`
- Create: `plugins/memory-mcp-core/clients/claude-code/CLAUDE.md`
- Create: `plugins/memory-mcp-core/clients/claude-code/settings.example.json`
- Create: `plugins/memory-mcp-core/clients/vscode-copilot/.github/copilot-instructions.md`
- Create: `plugins/memory-mcp-core/clients/vscode-copilot/.vscode/mcp.json`
- Create: `plugins/memory-mcp-core/clients/cursor/.cursor/rules/memory-mcp.mdc`
- Create: `plugins/memory-mcp-core/clients/common/memory-mcp-agent-workflow.md`
- Create: `plugins/memory-mcp-core/hooks/_client.py`
- Create: `plugins/memory-mcp-core/hooks/post_tool_use.py`
- Create: `plugins/memory-mcp-core/hooks/session_end.py`
- Create: `plugins/memory-mcp-core/hooks/session_start.py`
- Create: `plugins/memory-mcp-core/hooks/user_prompt_submit.py`
- Modify: `tests/plugins/test_loader.py`

- [ ] **Step 1: Add a failing test for the real bundled plugin**

Append to `tests/plugins/test_loader.py`:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_bundled_memory_mcp_core_plugin_loads_from_marketplace() -> None:
    marketplace = load_marketplace(PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json")

    assert [entry.name for entry in marketplace.plugins] == ["memory-mcp-core"]

    manifest = load_plugin_manifest(marketplace.plugins[0].path)

    assert manifest.id == "memory-mcp-core"
    assert set(manifest.client_targets) == {"codex", "claude-code", "vscode-copilot", "cursor"}
    assert manifest.hooks
    assert "local-docker" in manifest.server_modes
```

- [ ] **Step 2: Run the bundled plugin test to verify it fails**

Run:

```powershell
pytest tests/plugins/test_loader.py::test_bundled_memory_mcp_core_plugin_loads_from_marketplace -v
```

Expected: FAIL because `.agents/plugins/marketplace.json` does not exist.

- [ ] **Step 3: Add the local marketplace file**

Create `.agents/plugins/marketplace.json`:

```json
{
  "name": "memory-mcp-local-marketplace",
  "interface": {
    "displayName": "memory-mcp Local Marketplace"
  },
  "plugins": [
    {
      "name": "memory-mcp-core",
      "source": {
        "source": "local",
        "path": "../../plugins/memory-mcp-core"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

- [ ] **Step 4: Add the Codex-compatible plugin manifest**

Create `plugins/memory-mcp-core/.codex-plugin/plugin.json`:

```json
{
  "id": "memory-mcp-core",
  "name": "memory-mcp-core",
  "version": "0.1.0",
  "displayName": "memory-mcp Core",
  "description": "Default memory-mcp client workflow, MCP config, and hook setup package.",
  "publisher": "memory-mcp",
  "categories": ["Developer Tools"]
}
```

- [ ] **Step 5: Add the memory-mcp plugin manifest**

Create `plugins/memory-mcp-core/plugin.memory-mcp.json`:

```json
{
  "schema_version": "1",
  "id": "memory-mcp-core",
  "display_name": "memory-mcp Core",
  "description": "Default memory-mcp client workflow, MCP config, and hook setup package.",
  "version": "0.1.0",
  "min_memory_mcp_version": "0.1.0",
  "update_channel": "stable",
  "category": "Developer Tools",
  "server_modes": ["local-docker", "local-http", "remote-authenticated", "manual-stdio"],
  "client_targets": {
    "codex": {
      "outputs": [
        {"source": "clients/codex/AGENTS.md", "target": "AGENTS.md"},
        {"source": "clients/codex/config.example.toml", "target": "config.example.toml"}
      ]
    },
    "claude-code": {
      "outputs": [
        {"source": "clients/claude-code/CLAUDE.md", "target": "CLAUDE.md"},
        {"source": "clients/claude-code/settings.example.json", "target": "settings.example.json"}
      ]
    },
    "vscode-copilot": {
      "outputs": [
        {"source": "clients/vscode-copilot/.github/copilot-instructions.md", "target": ".github/copilot-instructions.md"},
        {"source": "clients/vscode-copilot/.vscode/mcp.json", "target": ".vscode/mcp.json"}
      ]
    },
    "cursor": {
      "outputs": [
        {"source": "clients/cursor/.cursor/rules/memory-mcp.mdc", "target": ".cursor/rules/memory-mcp.mdc"}
      ]
    }
  },
  "hooks": [
    {"event": "PostToolUse", "source": "hooks/post_tool_use.py"},
    {"event": "UserPromptSubmit", "source": "hooks/user_prompt_submit.py"},
    {"event": "SessionStart", "source": "hooks/session_start.py"},
    {"event": "SessionEnd", "source": "hooks/session_end.py"}
  ]
}
```

- [ ] **Step 6: Copy existing template and hook assets into the package**

Create package files by copying bytes from these sources:

```text
client-setups/codex/AGENTS.md -> plugins/memory-mcp-core/clients/codex/AGENTS.md
client-setups/codex/config.example.toml -> plugins/memory-mcp-core/clients/codex/config.example.toml
client-setups/claude-code/CLAUDE.md -> plugins/memory-mcp-core/clients/claude-code/CLAUDE.md
client-setups/claude-code/settings.example.json -> plugins/memory-mcp-core/clients/claude-code/settings.example.json
client-setups/vscode-copilot/.github/copilot-instructions.md -> plugins/memory-mcp-core/clients/vscode-copilot/.github/copilot-instructions.md
client-setups/vscode-copilot/.vscode/mcp.json -> plugins/memory-mcp-core/clients/vscode-copilot/.vscode/mcp.json
client-setups/cursor/.cursor/rules/memory-mcp.mdc -> plugins/memory-mcp-core/clients/cursor/.cursor/rules/memory-mcp.mdc
client-setups/common/memory-mcp-agent-workflow.md -> plugins/memory-mcp-core/clients/common/memory-mcp-agent-workflow.md
hooks/_client.py -> plugins/memory-mcp-core/hooks/_client.py
hooks/post_tool_use.py -> plugins/memory-mcp-core/hooks/post_tool_use.py
hooks/session_end.py -> plugins/memory-mcp-core/hooks/session_end.py
hooks/session_start.py -> plugins/memory-mcp-core/hooks/session_start.py
hooks/user_prompt_submit.py -> plugins/memory-mcp-core/hooks/user_prompt_submit.py
```

- [ ] **Step 7: Add the bundled plugin README**

Create `plugins/memory-mcp-core/README.md`:

````markdown
# memory-mcp Core Plugin

`memory-mcp-core` packages the default memory-mcp client workflow, local MCP
configuration examples, and optional Claude Code hook assets.

Render examples:

```powershell
memory-mcp plugins render memory-mcp-core --client codex --output .memory-mcp/rendered/codex
memory-mcp plugins render memory-mcp-core --client claude-code --output .memory-mcp/rendered/claude-code
memory-mcp plugins render memory-mcp-core --client vscode-copilot --output .memory-mcp/rendered/vscode-copilot
memory-mcp plugins render memory-mcp-core --client cursor --output .memory-mcp/rendered/cursor
```

Rendering writes reviewable files into the output directory. It does not mutate
live client configuration.
````

- [ ] **Step 8: Run bundled plugin test**

Run:

```powershell
pytest tests/plugins/test_loader.py::test_bundled_memory_mcp_core_plugin_loads_from_marketplace -v
```

Expected: PASS.

- [ ] **Step 9: Commit bundled package**

Run:

```powershell
git add .agents/plugins/marketplace.json plugins/memory-mcp-core tests/plugins/test_loader.py
git commit -m "feat(plugins): add memory-mcp core plugin package"
```

---

### Task 3: Add Deterministic Renderer

**Files:**
- Create: `tests/plugins/test_renderer.py`
- Create: `src/memory_mcp/plugins/renderer.py`

- [ ] **Step 1: Write failing renderer tests**

Create `tests/plugins/test_renderer.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from memory_mcp.plugins.errors import PluginError
from memory_mcp.plugins.loader import load_plugin_manifest
from memory_mcp.plugins.renderer import render_plugin

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def bundled_manifest():
    return load_plugin_manifest(PROJECT_ROOT / "plugins" / "memory-mcp-core")


def test_render_codex_outputs(tmp_path: Path) -> None:
    written = render_plugin(bundled_manifest(), "codex", tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in written] == [
        "AGENTS.md",
        "config.example.toml",
    ]
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8").startswith("# memory-mcp Workflow")
    assert "memory-mcp" in (tmp_path / "config.example.toml").read_text(encoding="utf-8")


def test_render_claude_code_outputs(tmp_path: Path) -> None:
    render_plugin(bundled_manifest(), "claude-code", tmp_path)

    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / "settings.example.json").is_file()


def test_render_vscode_copilot_outputs(tmp_path: Path) -> None:
    render_plugin(bundled_manifest(), "vscode-copilot", tmp_path)

    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    assert (tmp_path / ".vscode" / "mcp.json").is_file()


def test_render_cursor_outputs(tmp_path: Path) -> None:
    render_plugin(bundled_manifest(), "cursor", tmp_path)

    assert (tmp_path / ".cursor" / "rules" / "memory-mcp.mdc").is_file()


def test_render_refuses_existing_non_empty_output(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("keep\n", encoding="utf-8")

    with pytest.raises(PluginError, match="non-empty"):
        render_plugin(bundled_manifest(), "codex", tmp_path)


def test_render_allows_existing_non_empty_output_with_overwrite(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("keep\n", encoding="utf-8")

    render_plugin(bundled_manifest(), "codex", tmp_path, overwrite=True)

    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "keep\n"
    assert (tmp_path / "AGENTS.md").is_file()


def test_render_rejects_unknown_client(tmp_path: Path) -> None:
    with pytest.raises(PluginError, match="unsupported client"):
        render_plugin(bundled_manifest(), "unknown-client", tmp_path)


def test_rendered_outputs_do_not_contain_credential_values(tmp_path: Path) -> None:
    render_plugin(bundled_manifest(), "codex", tmp_path)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sorted(tmp_path.rglob("*")) if path.is_file())

    forbidden = ["BEGIN PRIVATE KEY", "api_key", "access_token", "refresh_token", "client_secret"]
    for marker in forbidden:
        assert marker not in combined
```

- [ ] **Step 2: Run renderer tests to verify they fail**

Run:

```powershell
pytest tests/plugins/test_renderer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'memory_mcp.plugins.renderer'`.

- [ ] **Step 3: Add renderer implementation**

Create `src/memory_mcp/plugins/renderer.py`:

```python
"""Deterministic renderer for local memory-mcp plugin outputs."""

from __future__ import annotations

import shutil
from pathlib import Path

from memory_mcp.plugins.errors import PluginError
from memory_mcp.plugins.models import PluginManifest


def _directory_has_entries(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def render_plugin(
    manifest: PluginManifest,
    client: str,
    output_dir: Path,
    *,
    overwrite: bool = False,
) -> list[Path]:
    target = manifest.client_targets.get(client)
    if target is None:
        supported = ", ".join(sorted(manifest.client_targets))
        raise PluginError(f"unsupported client {client!r}; supported clients: {supported}")

    output_root = output_dir.resolve()
    if _directory_has_entries(output_root) and not overwrite:
        raise PluginError(f"output directory is non-empty: {output_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for output in target.outputs:
        destination = output_root / output.target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output.source, destination)
        written.append(destination)
    return written
```

- [ ] **Step 4: Run renderer tests**

Run:

```powershell
pytest tests/plugins/test_renderer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit renderer**

Run:

```powershell
git add tests/plugins/test_renderer.py src/memory_mcp/plugins/renderer.py
git commit -m "feat(plugins): render client package outputs"
```

---

### Task 4: Add Focused Plugin CLI Dispatch

**Files:**
- Create: `tests/plugins/test_cli.py`
- Create: `src/memory_mcp/plugins/cli.py`
- Modify: `src/memory_mcp/main.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/plugins/test_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from memory_mcp.main import main
from memory_mcp.plugins.cli import run_plugins_cli

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json"


def test_plugins_list_outputs_marketplace_entries(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_plugins_cli(["list", "--marketplace", str(MARKETPLACE)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "memory-mcp-core" in captured.out


def test_plugins_show_outputs_manifest_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_plugins_cli(["show", "memory-mcp-core", "--marketplace", str(MARKETPLACE)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "memory-mcp Core" in captured.out
    assert "codex" in captured.out
    assert "local-docker" in captured.out


def test_plugins_render_writes_client_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_plugins_cli(
        [
            "render",
            "memory-mcp-core",
            "--client",
            "codex",
            "--output",
            str(tmp_path),
            "--marketplace",
            str(MARKETPLACE),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "AGENTS.md" in captured.out
    assert (tmp_path / "AGENTS.md").is_file()


def test_main_dispatches_plugins_without_starting_server(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    called = {"server": False}

    def fake_run(*, transport: str, host: str, port: int) -> None:
        called["server"] = True

    monkeypatch.setattr("memory_mcp.main.run", fake_run)

    main(["plugins", "list", "--marketplace", str(MARKETPLACE)])

    captured = capsys.readouterr()
    assert "memory-mcp-core" in captured.out
    assert called["server"] is False


def test_main_without_plugins_still_starts_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(*, transport: str, host: str, port: int) -> None:
        calls.append({"transport": transport, "host": host, "port": port})

    monkeypatch.setattr("memory_mcp.main.run", fake_run)

    main(["--transport", "stdio", "--host", "127.0.0.1", "--port", "3001"])

    assert calls == [{"transport": "stdio", "host": "127.0.0.1", "port": 3001}]
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```powershell
pytest tests/plugins/test_cli.py -v
```

Expected: FAIL because `memory_mcp.plugins.cli` does not exist and `main()` does not accept an argument list.

- [ ] **Step 3: Add plugin CLI command handler**

Create `src/memory_mcp/plugins/cli.py`:

```python
"""Command line interface for local plugin rendering."""

from __future__ import annotations

import argparse
from pathlib import Path

from memory_mcp.plugins.errors import PluginError
from memory_mcp.plugins.loader import load_marketplace, load_plugin_manifest
from memory_mcp.plugins.models import MarketplaceEntry, PluginManifest
from memory_mcp.plugins.renderer import render_plugin


def _default_marketplace() -> Path:
    return Path.cwd() / ".agents" / "plugins" / "marketplace.json"


def _find_entry(marketplace_path: Path, plugin_name: str) -> MarketplaceEntry:
    marketplace = load_marketplace(marketplace_path)
    for entry in marketplace.plugins:
        if entry.name == plugin_name:
            return entry
    raise PluginError(f"plugin not found in marketplace: {plugin_name}")


def _print_manifest(manifest: PluginManifest) -> None:
    print(f"{manifest.id} {manifest.version}")
    print(manifest.display_name)
    print(manifest.description)
    print("clients: " + ", ".join(sorted(manifest.client_targets)))
    print("server_modes: " + ", ".join(manifest.server_modes))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-mcp plugins", description="Manage local memory-mcp plugins")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List local marketplace plugins")
    list_parser.add_argument("--marketplace", type=Path, default=_default_marketplace())

    show_parser = subparsers.add_parser("show", help="Show plugin metadata")
    show_parser.add_argument("plugin")
    show_parser.add_argument("--marketplace", type=Path, default=_default_marketplace())

    render_parser = subparsers.add_parser("render", help="Render plugin outputs")
    render_parser.add_argument("plugin")
    render_parser.add_argument("--client", required=True)
    render_parser.add_argument("--output", required=True, type=Path)
    render_parser.add_argument("--marketplace", type=Path, default=_default_marketplace())
    render_parser.add_argument("--overwrite", action="store_true")
    return parser


def run_plugins_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            marketplace = load_marketplace(args.marketplace)
            for entry in marketplace.plugins:
                print(f"{entry.name}\t{entry.path}")
            return 0
        if args.command == "show":
            entry = _find_entry(args.marketplace, args.plugin)
            _print_manifest(load_plugin_manifest(entry.path))
            return 0
        if args.command == "render":
            entry = _find_entry(args.marketplace, args.plugin)
            manifest = load_plugin_manifest(entry.path)
            written = render_plugin(manifest, args.client, args.output, overwrite=args.overwrite)
            for path in written:
                print(path)
            return 0
    except PluginError as exc:
        parser.error(str(exc))
    raise AssertionError(f"unhandled plugin command: {args.command}")
```

- [ ] **Step 4: Modify main entrypoint to dispatch plugin commands**

Modify `src/memory_mcp/main.py`:

```python
"""Command entry point for the memory MCP server."""

from __future__ import annotations

import argparse
import sys

from memory_mcp.mcp_tools.server import run
from memory_mcp.plugins.cli import run_plugins_cli


def main(argv: list[str] | None = None) -> None:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list[:1] == ["plugins"]:
        exit_code = run_plugins_cli(args_list[1:])
        if exit_code:
            raise SystemExit(exit_code)
        return

    parser = argparse.ArgumentParser(description="memory-mcp MCP server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args(args_list)
    run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
pytest tests/plugins/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Run main entrypoint smoke command**

Run:

```powershell
python -m memory_mcp.main plugins list --marketplace .agents/plugins/marketplace.json
```

Expected output includes `memory-mcp-core`.

- [ ] **Step 7: Commit plugin CLI**

Run:

```powershell
git add tests/plugins/test_cli.py src/memory_mcp/plugins/cli.py src/memory_mcp/main.py
git commit -m "feat(plugins): add render-only plugin CLI"
```

---

### Task 5: Update Client Setup Documentation And Coverage

**Files:**
- Modify: `client-setups/README.md`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write failing docs coverage assertion**

In `tests/test_mcp_tools.py`, extend `test_client_setup_templates_cover_supported_agent_environments` after the existing `client_setup` assertions:

```python
    assert "memory-mcp plugins render memory-mcp-core --client codex" in client_setup
    assert "manual template install path remains supported" in client_setup
```

- [ ] **Step 2: Run the docs coverage test to verify it fails**

Run:

```powershell
pytest tests/test_mcp_tools.py::test_client_setup_templates_cover_supported_agent_environments -v
```

Expected: FAIL because the README does not yet mention plugin render commands.

- [ ] **Step 3: Update client setup README**

Modify `client-setups/README.md` so the top of the file reads:

````markdown
# memory-mcp Client Setups

Preferred setup path: render the bundled plugin into a reviewable output
directory, then copy or adapt the rendered files for the target client.

```powershell
memory-mcp plugins render memory-mcp-core --client codex --output .memory-mcp/rendered/codex
memory-mcp plugins render memory-mcp-core --client claude-code --output .memory-mcp/rendered/claude-code
memory-mcp plugins render memory-mcp-core --client vscode-copilot --output .memory-mcp/rendered/vscode-copilot
memory-mcp plugins render memory-mcp-core --client cursor --output .memory-mcp/rendered/cursor
```

The manual template install path remains supported. Copy the template for the
agent environment used by a target repository, then adjust paths and project
names for that repository.
````

Keep the existing `Setup Prompts`, `Templates`, and `Install Pattern` sections after this new introduction.

- [ ] **Step 4: Run docs coverage test**

Run:

```powershell
pytest tests/test_mcp_tools.py::test_client_setup_templates_cover_supported_agent_environments -v
```

Expected: PASS.

- [ ] **Step 5: Commit docs update**

Run:

```powershell
git add client-setups/README.md tests/test_mcp_tools.py
git commit -m "docs(plugins): prefer rendered client setup"
```

---

### Task 6: Full Verification And Review Context

**Files:**
- Verify all files changed in Tasks 1-5.

- [ ] **Step 1: Run focused plugin tests**

Run:

```powershell
pytest tests/plugins tests/test_mcp_tools.py::test_client_setup_templates_cover_supported_agent_environments -v
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
pytest
```

Expected: PASS.

- [ ] **Step 3: Run whitespace/diff check**

Run:

```powershell
git diff --check
```

Expected: no errors. Line-ending conversion warnings are acceptable if no whitespace errors are reported.

- [ ] **Step 4: Inspect graph review context**

Run through code-review-graph:

```text
detect_changes(base="HEAD~5", changed_files=null, include_source=false, max_depth=2, detail_level="minimal")
```

Expected: review context identifies plugin loader, renderer, CLI, docs, and tests as the primary changed areas, with no unexpected runtime MCP server blast radius beyond `src/memory_mcp/main.py`.

- [ ] **Step 5: Refresh project memory**

Store one compact project memory after implementation:

```json
{
  "memory_type": "project_fact",
  "summary": "MMCP-016A plugin renderer implemented.",
  "content": "memory-mcp includes a local memory-mcp-core plugin package, marketplace loader, manifest validation, deterministic render-only client outputs, and memory-mcp plugins list/show/render CLI dispatch while preserving the MCP server launcher path.",
  "memory_scope": "project",
  "workspace": "ai",
  "project": "memory-mcp",
  "repo": "memory-mcp",
  "tags": ["plugin-marketplace", "cli", "client-setup"]
}
```

- [ ] **Step 6: Final commit if any verification fixes were needed**

If verification required changes after the Task 5 commit, run:

```powershell
git add src/memory_mcp/plugins src/memory_mcp/main.py tests/plugins tests/test_mcp_tools.py plugins/memory-mcp-core .agents/plugins/marketplace.json client-setups/README.md
git commit -m "fix(plugins): stabilize package renderer"
```

If no files changed during verification, no commit is needed.

---

## Self-Review

- Spec coverage: `MMCP-016A` manifest validation, local marketplace loading, bundled `memory-mcp-core`, deterministic client rendering, overwrite protection, focused CLI commands, existing server launcher behavior, and docs update are each covered by tasks above.
- Out-of-scope controls: receipts, update checks, server profiles, auth handoff, live config mutation, remote marketplace fetching, and runtime server plugin loading are not implemented in this plan.
- Type consistency: `PluginManifest`, `PluginClientTarget`, `PluginOutput`, `Marketplace`, and `MarketplaceEntry` are introduced in Task 1 and reused by renderer/CLI tasks with matching attribute names.
