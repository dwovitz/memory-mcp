# Worktree Strategy

## Why Worktrees

Use one git worktree per story to keep story changes isolated from `main` and from other active work. This prevents mixed changes, branch confusion, and difficult rollback.

## Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Feature branch | `feat/<story-id>` | `feat/MMCP-007` |
| Fix branch | `fix/<story-id>` | `fix/MMCP-007` |
| Spike branch | `spike/<story-id>` | `spike/MMCP-007` |
| Worktree directory | `../wt-<story-id>` | `../wt-MMCP-007` |

## Creation

Create the story worktree from the main checkout before implementation starts:

```bash
git worktree add ../wt-<story-id> -b feat/<story-id>
```

## Working Inside

Run all story commands from the worktree directory. This includes `pytest`, Alembic migrations, syntax checks, and validation commands.

## Completion Reports

Every completion report must name the worktree path and branch used for the story.

## Cleanup

After the story branch is merged or abandoned, remove the worktree:

```bash
git worktree remove ../wt-<story-id>
```

Then delete the completed branch:

```bash
git branch -d feat/<story-id>
```

## Resume

After a session break, resume by re-entering the existing worktree directory and continuing on the existing story branch.
