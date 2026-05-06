# memory-mcp Client Setups

Copy the template for the agent environment used by a target repository, then
adjust paths and project names for that repository.

## Setup Prompts

Run these prompts once per repository to populate memory-mcp with project context:

- **New repository**: `client-setups/setup-new-repo/SETUP_PROMPT.md` — captures intent, stack, architecture, conventions, and test strategy at project start.
- **Existing repository**: `client-setups/setup-existing-repo/SETUP_PROMPT.md` — ingests README, architecture docs, coding rules, ADRs, and component layout from an existing codebase.

## Templates

- Codex: `client-setups/codex/AGENTS.md` plus `client-setups/codex/config.example.toml`
- Claude Code: `client-setups/claude-code/CLAUDE.md` plus `client-setups/claude-code/settings.example.json`
- Cursor: `client-setups/cursor/.cursor/rules/memory-mcp.mdc`
- VS Code Copilot: `client-setups/vscode-copilot/.github/copilot-instructions.md` plus `client-setups/vscode-copilot/.vscode/mcp.json`
- Shared workflow: `client-setups/common/memory-mcp-agent-workflow.md`

## Install Pattern

1. Register the `memory-mcp` MCP server using the config shape for the client.
2. Copy the client instruction file into the target repository.
3. Replace `workspace="ai"` and `repo="<repo-name>"` with the target
   workspace and repository name. (`repo` is the preferred vocabulary; `project`
   remains an alias for backward compatibility.)
4. Keep `include_sensitive=false` by default.
5. Confirm context packets expose `source_read_contract` before relying on
   source-read budget guidance.

