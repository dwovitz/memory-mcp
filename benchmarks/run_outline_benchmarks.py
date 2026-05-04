"""Command-line entry point for Outline benchmark automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.outline_benchmark_runner import (
    build_run_plan,
    create_run_directory,
    format_preflight_plan,
    load_cases,
    preflight_run_plan,
    run_benchmark_suite,
    select_cases,
    select_variants,
    write_summary_json,
    write_summary_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Outline memory benchmark prompts.")
    parser.add_argument("--outline-repo", default="D:\\git\\ai\\outline")
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--cases", default="")
    parser.add_argument("--variants", default="baseline,memory")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--mode", choices=("smoke", "targeted", "full"), default="targeted")
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "benchmarks" / "results" / "runs")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-large-token-run", action="store_true")
    parser.add_argument("--keep-full-artifacts", action="store_true")
    parser.add_argument("--update-docker", action="store_true")
    parser.add_argument("--continue-on-docker-failure", action="store_true")
    parser.add_argument("--apply-improvement-prompt", action="store_true")
    parser.add_argument(
        "--improvement-prompt",
        type=Path,
        default=REPO_ROOT
        / "benchmarks"
        / "prompts"
        / "04-memory-mcp-implementation-prompt-strict-fallback-and-baseline-isolation.md",
    )
    args = parser.parse_args()

    cases = load_cases(REPO_ROOT / "benchmarks" / "cases.json")
    requested_cases = [case.strip() for case in args.cases.split(",") if case.strip()]
    selected_cases = select_cases(cases, requested_cases or None)
    variants = select_variants(args.variants)
    plan = build_run_plan(
        selected_cases,
        variants,
        REPO_ROOT / "benchmarks" / "prompts",
        iterations=args.iterations,
        mode=args.mode,
        explicit_cases=bool(requested_cases),
    )
    preflight = preflight_run_plan(plan, allow_large_token_run=args.allow_large_token_run)

    if args.dry_run:
        print(format_preflight_plan(preflight))
        if not preflight.suite_budget_obeyed and not args.allow_large_token_run:
            return 1
        return 0

    run_dir = create_run_directory(args.results_dir)
    results = run_benchmark_suite(
        plan,
        agent_command=args.agent_command,
        run_dir=run_dir,
        timeout_seconds=args.timeout_seconds,
        apply_improvement_prompt=args.apply_improvement_prompt,
        improvement_prompt=args.improvement_prompt,
        update_docker=args.update_docker,
        continue_on_docker_failure=args.continue_on_docker_failure,
        allow_large_token_run=args.allow_large_token_run,
        keep_full_artifacts=args.keep_full_artifacts,
        repo_root=REPO_ROOT,
    )
    write_summary_json(results, run_dir / "summary.json")
    write_summary_markdown(results, run_dir / "summary.md")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
