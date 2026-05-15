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


def load_plugin_manifest(plugin_root: Path) -> PluginManifest:
    manifest_path = plugin_root / "plugin.memory-mcp.json"
    payload = _load_json_object(manifest_path)

    schema_version = _require_string(payload, "schema_version", manifest_path)
    plugin_id = _require_string(payload, "id", manifest_path)
    display_name = _require_string(payload, "display_name", manifest_path)
    description = _require_string(payload, "description", manifest_path)
    version = _require_string(payload, "version", manifest_path)
    min_memory_mcp_version = _require_string(payload, "min_memory_mcp_version", manifest_path)
    update_channel = _require_string(payload, "update_channel", manifest_path)
    category = _require_string(payload, "category", manifest_path)
    client_targets = _load_client_targets(plugin_root, payload, manifest_path)
    hooks = _load_hooks(plugin_root, payload, manifest_path)
    server_modes = _load_string_list(payload, "server_modes", manifest_path)

    return PluginManifest(
        root=plugin_root.resolve(),
        schema_version=schema_version,
        id=plugin_id,
        display_name=display_name,
        description=description,
        version=version,
        min_memory_mcp_version=min_memory_mcp_version,
        update_channel=update_channel,
        category=category,
        client_targets=client_targets,
        hooks=hooks,
        server_modes=server_modes,
    )


def load_marketplace(marketplace_path: Path) -> Marketplace:
    payload = _load_json_object(marketplace_path)
    name = _require_string(payload, "name", marketplace_path)

    interface = payload.get("interface")
    if not isinstance(interface, dict):
        raise PluginError(f"{marketplace_path} missing interface object")
    display_name = _require_string(interface, "displayName", marketplace_path)

    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        raise PluginError(f"{marketplace_path} missing plugins list")

    entries: list[MarketplaceEntry] = []
    for index, item in enumerate(plugins):
        if not isinstance(item, dict):
            raise PluginError(f"{marketplace_path} plugins[{index}] must be an object")
        entry_name = _require_string(item, "name", marketplace_path)
        source = item.get("source")
        if not isinstance(source, dict):
            raise PluginError(f"{marketplace_path} plugins[{index}] missing source object")
        source_type = _require_string(source, "source", marketplace_path)
        if source_type != "local":
            raise PluginError(f"{marketplace_path} plugins[{index}] source must be local")
        relative_path = _require_string(source, "path", marketplace_path)
        entries.append(
            MarketplaceEntry(
                name=entry_name,
                path=(marketplace_path.parent / relative_path).resolve(),
            )
        )

    return Marketplace(name=name, display_name=display_name, plugins=tuple(entries))


def _load_client_targets(
    plugin_root: Path, payload: dict[str, Any], manifest_path: Path
) -> dict[str, PluginClientTarget]:
    raw_targets = payload.get("client_targets")
    if not isinstance(raw_targets, dict) or not raw_targets:
        raise PluginError(f"{manifest_path} missing client_targets")

    client_targets: dict[str, PluginClientTarget] = {}
    for name, config in raw_targets.items():
        if not isinstance(name, str) or not name:
            raise PluginError(f"{manifest_path} has invalid client target name")
        if not isinstance(config, dict):
            raise PluginError(f"{manifest_path} client_targets.{name} must be an object")
        outputs_value = config.get("outputs")
        if not isinstance(outputs_value, list) or not outputs_value:
            raise PluginError(f"{manifest_path} client_targets.{name} missing outputs")

        outputs: list[PluginOutput] = []
        for output_index, raw_output in enumerate(outputs_value):
            if not isinstance(raw_output, dict):
                raise PluginError(
                    f"{manifest_path} client_targets.{name}.outputs[{output_index}] must be an object"
                )
            source_text = _require_string(raw_output, "source", manifest_path)
            target_text = _require_string(raw_output, "target", manifest_path)
            source_path = plugin_root / source_text
            if not source_path.is_file():
                raise PluginError(f"{manifest_path} declared output source is missing: {source_text}")
            outputs.append(PluginOutput(source=source_path.resolve(), target=target_text))

        client_targets[name] = PluginClientTarget(name=name, outputs=tuple(outputs))

    return client_targets


def _load_hooks(plugin_root: Path, payload: dict[str, Any], manifest_path: Path) -> tuple[PluginHook, ...]:
    raw_hooks = payload.get("hooks")
    if not isinstance(raw_hooks, list):
        raise PluginError(f"{manifest_path} missing hooks list")

    hooks: list[PluginHook] = []
    for index, raw_hook in enumerate(raw_hooks):
        if not isinstance(raw_hook, dict):
            raise PluginError(f"{manifest_path} hooks[{index}] must be an object")
        event = _require_string(raw_hook, "event", manifest_path)
        source_text = _require_string(raw_hook, "source", manifest_path)
        source_path = plugin_root / source_text
        if not source_path.is_file():
            raise PluginError(f"{manifest_path} declared hook source is missing: {source_text}")
        hooks.append(PluginHook(event=event, source=source_path.resolve()))

    return tuple(hooks)


def _load_string_list(payload: dict[str, Any], key: str, manifest_path: Path) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise PluginError(f"{manifest_path} missing {key}")
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise PluginError(f"{manifest_path} {key}[{index}] must be a non-empty string")
        strings.append(item)
    return tuple(strings)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PluginError(f"{path} does not exist") from exc
    except json.JSONDecodeError as exc:
        raise PluginError(f"{path} is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise PluginError(f"{path} must contain a JSON object")
    return payload


def _require_string(payload: dict[str, Any], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise PluginError(f"{path} missing {key}")
    return value
