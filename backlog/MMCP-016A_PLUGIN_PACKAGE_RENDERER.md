# MMCP-016A — Plugin package discovery and deterministic renderer

**Priority:** P1
**Status:** Ready
**Blocked by:** —
**Parent:** MMCP-016
**Design:** `docs/superpowers/specs/2026-05-15-plugin-marketplace-model-design.md`

## Goal

Create the first local marketplace slice: a `memory-mcp-core` plugin package
that can be discovered from a local marketplace, validated, shown, and rendered
deterministically for supported client targets.

## Scope Of Work

- Add `plugins/memory-mcp-core/` with:
  - `.codex-plugin/plugin.json`
  - `plugin.memory-mcp.json`
  - packaged workflow/client assets for Codex, Claude Code, VS Code Copilot,
    and Cursor
  - packaged hook assets needed by the current Claude Code setup
  - plugin README
- Add `.agents/plugins/marketplace.json` with a local `memory-mcp-core` entry.
- Add plugin manifest models and schema validation under a new
  `src/memory_mcp/plugins/` package.
- Add local marketplace loading that preserves marketplace order.
- Add deterministic renderer support for:
  - Codex `AGENTS.md`
  - Codex MCP config output
  - Claude Code `CLAUDE.md`
  - Claude Code settings/hooks output
  - VS Code Copilot instructions
  - VS Code MCP config output
  - Cursor rule output
- Add focused `memory-mcp plugins list`, `show`, and `render` command handling
  while preserving the current MCP server launcher behavior.
- Update client setup docs so plugin rendering is the preferred path once this
  story ships, while manual templates remain documented.

## Out Of Scope

- Install receipts or lock files.
- Update checks.
- Interactive setup.
- Server profile persistence.
- Remote marketplace fetching.
- Auth profile validation.
- Mutation of live client or user-level configuration.
- Runtime server-side plugin loading.
- Hook behavior changes.

## Acceptance Criteria

- `memory-mcp plugins list --marketplace .agents/plugins/marketplace.json`
  lists `memory-mcp-core`.
- `memory-mcp plugins show memory-mcp-core` prints manifest metadata, supported
  clients, and supported server modes without rendering files.
- `memory-mcp plugins render memory-mcp-core --client codex --output <dir>`
  writes deterministic Codex outputs.
- Equivalent render commands work for `claude-code`, `vscode-copilot`, and
  `cursor`.
- Rendering to an existing non-empty output directory fails unless an explicit
  overwrite flag is supplied.
- Invalid manifests fail before rendering with clear errors.
- Rendered outputs contain no secrets and no credential values.
- Existing MCP server launch behavior still works when no `plugins` subcommand
  is passed.

## Test Plan

- Manifest loader accepts the bundled `memory-mcp-core` plugin.
- Manifest loader rejects missing required fields.
- Marketplace loader lists local plugins in marketplace order.
- Renderer emits Codex outputs from one plugin source.
- Renderer emits Claude Code outputs from one plugin source.
- Renderer emits VS Code Copilot outputs from one plugin source.
- Renderer emits Cursor outputs from one plugin source.
- Renderer refuses to overwrite existing output unless explicitly allowed.
- CLI dispatch covers `plugins list`, `plugins show`, `plugins render`, and the
  existing MCP server path.

## Implementation Notes

- Prefer structured JSON validation over ad hoc string checks for manifests.
- Keep template rendering deterministic so tests can compare exact files.
- Treat `client-setups/` as the source compatibility baseline, not as a runtime
  install location.
