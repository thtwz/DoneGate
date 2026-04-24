from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from donegate_mcp.cli.formatters import render
from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import DoneGateMcpError, TransitionError, ValidationError


def _csv_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _json_object_list(values: list[str]) -> list[dict]:
    objects: list[dict] = []
    for index, raw_value in enumerate(values, start=1):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"--finding-json #{index} is not valid JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValidationError(f"--finding-json #{index} must decode to a JSON object")
        objects.append(parsed)
    return objects


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="donegate-mcp")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap_p = sub.add_parser("bootstrap")
    bootstrap_p.add_argument("--project-name", required=True)
    bootstrap_p.add_argument("--repo-root", default=".")
    bootstrap_p.add_argument("--default-branch")

    supervision_p = sub.add_parser("supervision")
    supervision_p.add_argument("--repo-root", default=".")

    onboarding_p = sub.add_parser("onboarding")
    onboarding_p.add_argument("--repo-root", default=".")
    onboarding_p.add_argument("--agent", choices=["codex", "hermes"], default="codex")

    init_p = sub.add_parser("init")
    init_p.add_argument("--project-name", required=True)
    init_p.add_argument("--default-branch")
    init_p.add_argument("--repo-root")

    dash_p = sub.add_parser("dashboard")
    dash_p.add_argument("--include-tasks", action="store_true")
    dash_p.add_argument("--limit", type=int, default=10)

    sub.add_parser("plan")
    sub.add_parser("progress")

    spec = sub.add_parser("spec")
    spec_sub = spec.add_subparsers(dest="spec_command", required=True)
    spec_refresh = spec_sub.add_parser("refresh")
    spec_refresh.add_argument("--spec-ref", required=True)
    spec_refresh.add_argument("--reason")

    deviation = sub.add_parser("deviation")
    deviation_sub = deviation.add_subparsers(dest="deviation_command", required=True)
    deviation_add = deviation_sub.add_parser("add")
    deviation_add.add_argument("task_id")
    deviation_add.add_argument("--summary", required=True)
    deviation_add.add_argument("--details", required=True)
    deviation_add.add_argument("--spec-ref")
    deviation_sub.add_parser("list")

    review = sub.add_parser("review")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_list = review_sub.add_parser("list")
    review_list.add_argument("--task-id")
    review_list.add_argument("--checkpoint", choices=["submit", "pre_done", "manual"])
    review_list.add_argument("--status", choices=["requested", "completed"])
    review_list.add_argument("--include-findings", action="store_true")

    review_disposition = review_sub.add_parser("disposition")
    review_disposition.add_argument("finding_id")
    review_disposition.add_argument("--to", required=True, choices=["open", "accepted", "spawned_followup", "waived", "resolved"])
    review_disposition.add_argument("--notes")
    review_disposition.add_argument("--followup-task-id")

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command", required=True)

    create = task_sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--spec-ref", required=True)
    create.add_argument("--summary", default="")
    create.add_argument("--verification-mode", default="manual", choices=["manual", "self-test"])
    create.add_argument("--test-command", action="append", dest="test_commands", default=[])
    create.add_argument("--required-doc-ref", action="append", dest="required_doc_refs", default=[])
    create.add_argument("--required-artifact", action="append", dest="required_artifacts", default=[])
    create.add_argument("--owned-path", action="append", dest="owned_paths", default=[])
    create.add_argument("--plan-node-id")

    list_p = task_sub.add_parser("list")
    list_p.add_argument("--status")
    list_p.add_argument("--limit", type=int)

    activate = task_sub.add_parser("activate")
    activate.add_argument("task_id")
    activate.add_argument("--repo-root")

    active = task_sub.add_parser("active")
    active.add_argument("--repo-root")

    clear_active = task_sub.add_parser("clear-active")
    clear_active.add_argument("--repo-root")

    for name in ["start", "submit", "done"]:
        p = task_sub.add_parser(name)
        p.add_argument("task_id")

    reopen = task_sub.add_parser("reopen")
    reopen.add_argument("task_id")
    reopen.add_argument("--to", choices=["ready", "in_progress", "awaiting_verification"], default="in_progress")

    transition = task_sub.add_parser("transition", help="compatibility escape hatch; prefer start/submit/done plus verify/doc-sync facts")
    transition.add_argument("task_id")
    transition.add_argument("--to", required=True, help="target status; verified/documented remain compatibility aliases")
    transition.add_argument("--reason")
    transition.add_argument("--notes")

    verify = task_sub.add_parser("verify")
    verify.add_argument("task_id")
    verify.add_argument("--result", required=True, choices=["passed", "failed"])
    verify.add_argument("--ref")
    verify.add_argument("--notes")

    doc_sync = task_sub.add_parser("doc-sync")
    doc_sync.add_argument("task_id")
    doc_sync.add_argument("--result", required=True, choices=["synced", "outdated"])
    doc_sync.add_argument("--ref")
    doc_sync.add_argument("--notes")

    protocol = task_sub.add_parser("protocol")
    protocol.add_argument("task_id")
    protocol.add_argument("--verification-mode", choices=["manual", "self-test"])
    protocol.add_argument("--test-commands")
    protocol.add_argument("--required-doc-refs")
    protocol.add_argument("--required-artifacts")
    protocol.add_argument("--owned-paths")
    protocol.add_argument("--plan-node-id")

    task_review = task_sub.add_parser("review")
    task_review.add_argument("task_id")
    task_review.add_argument("--checkpoint", default="manual", choices=["submit", "pre_done", "manual"])
    task_review.add_argument("--provider", default="manual", choices=["manual", "host_skill"])
    task_review.add_argument("--summary", default="")
    task_review.add_argument("--recommendation", default="proceed", choices=["proceed", "proceed_with_followups", "needs_human_attention"])
    task_review.add_argument("--finding-json", action="append", dest="finding_json", default=[])
    task_review.add_argument("--review-run-id")

    create_from_finding = task_sub.add_parser("create-from-finding")
    create_from_finding.add_argument("finding_id")
    create_from_finding.add_argument("--title")
    create_from_finding.add_argument("--summary")
    create_from_finding.add_argument("--plan-node-id")

    self_test = task_sub.add_parser("self-test")
    self_test.add_argument("task_id")
    self_test.add_argument("--workdir")

    block = task_sub.add_parser("block")
    block.add_argument("task_id")
    block.add_argument("--reason", required=True)

    unblock = task_sub.add_parser("unblock")
    unblock.add_argument("task_id")
    unblock.add_argument("--to", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = DoneGateService(data_root=_resolve_service_root(args))
    try:
        if args.command == "bootstrap":
            payload = service.bootstrap_repository(args.project_name, repo_root=args.repo_root, default_branch=args.default_branch)
        elif args.command == "onboarding":
            payload = service.get_onboarding(agent=args.agent, repo_root=args.repo_root)
        elif args.command == "supervision":
            payload = service.get_supervision(repo_root=args.repo_root)
        elif args.command == "init":
            payload = service.init_project(args.project_name, default_branch=args.default_branch, repo_root=args.repo_root)
        elif args.command == "dashboard":
            payload = service.dashboard(include_tasks=args.include_tasks, limit=args.limit)
        elif args.command == "plan":
            payload = service.get_plan()
        elif args.command == "progress":
            payload = service.get_progress()
        elif args.command == "spec":
            payload = service.refresh_spec(args.spec_ref, reason=args.reason)
        elif args.command == "deviation":
            payload = service.list_deviations() if args.deviation_command == "list" else service.record_deviation(args.task_id, args.summary, args.details, spec_ref=args.spec_ref)
        elif args.command == "review":
            payload = _run_review_command(service, args)
        elif args.command == "task":
            payload = _run_task_command(service, args)
        else:
            raise ValidationError(f"unknown command {args.command}")
        print(render(payload, args.as_json))
        return 0
    except TransitionError as exc:
        print(render({"ok": False, "errors": [str(exc)]}, args.as_json))
        return 3
    except ValidationError as exc:
        print(render({"ok": False, "errors": [str(exc)]}, args.as_json))
        return 2
    except DoneGateMcpError as exc:
        print(render({"ok": False, "errors": [str(exc)]}, args.as_json))
        return 4


def _resolve_service_root(args: argparse.Namespace) -> str | None:
    if args.command != "bootstrap" or args.data_root is not None:
        return args.data_root
    repo_root = Path(args.repo_root).resolve()
    return str(repo_root / ".donegate-mcp")


def _run_task_command(service: DoneGateService, args: argparse.Namespace) -> dict:
    cmd = args.task_command
    if cmd == "create":
        return service.create_task(args.title, args.spec_ref, summary=args.summary, verification_mode=args.verification_mode, test_commands=args.test_commands, required_doc_refs=args.required_doc_refs, required_artifacts=args.required_artifacts, owned_paths=args.owned_paths, plan_node_id=args.plan_node_id)
    if cmd == "list":
        return service.list_tasks(status=args.status, limit=args.limit)
    if cmd == "activate":
        return service.activate_task(args.task_id, repo_root=args.repo_root)
    if cmd == "active":
        return service.get_active_task(repo_root=args.repo_root)
    if cmd == "clear-active":
        return service.clear_active_task(repo_root=args.repo_root)
    if cmd == "start":
        return service.transition_task(args.task_id, "in_progress")
    if cmd == "submit":
        return service.transition_task(args.task_id, "awaiting_verification")
    if cmd == "transition":
        return service.transition_task(args.task_id, args.to, reason=args.reason, notes=args.notes)
    if cmd == "verify":
        return service.record_verification(args.task_id, args.result, ref=args.ref, notes=args.notes)
    if cmd == "doc-sync":
        return service.record_doc_sync(args.task_id, args.result, ref=args.ref, notes=args.notes)
    if cmd == "protocol":
        return service.update_acceptance_protocol(args.task_id, verification_mode=args.verification_mode, test_commands=_csv_list(args.test_commands), required_doc_refs=_csv_list(args.required_doc_refs), required_artifacts=_csv_list(args.required_artifacts), owned_paths=_csv_list(args.owned_paths), plan_node_id=args.plan_node_id)
    if cmd == "review":
        return service.record_task_review(
            args.task_id,
            checkpoint=args.checkpoint,
            provider_id=args.provider,
            summary=args.summary,
            overall_recommendation=args.recommendation,
            findings=_json_object_list(args.finding_json),
            review_run_id=args.review_run_id,
        )
    if cmd == "create-from-finding":
        return service.create_followup_task_from_finding(
            args.finding_id,
            title=args.title,
            summary=args.summary,
            plan_node_id=args.plan_node_id,
        )
    if cmd == "self-test":
        return service.run_self_test(args.task_id, workdir=args.workdir)
    if cmd == "done":
        return service.transition_task(args.task_id, "done")
    if cmd == "reopen":
        return service.reopen_task(args.task_id, target_status=args.to)
    if cmd == "block":
        return service.block_task(args.task_id, args.reason)
    if cmd == "unblock":
        return service.unblock_task(args.task_id, args.to)
    raise ValidationError(f"unknown task command {cmd}")


def _run_review_command(service: DoneGateService, args: argparse.Namespace) -> dict:
    cmd = args.review_command
    if cmd == "list":
        return service.list_reviews(
            task_id=args.task_id,
            checkpoint=args.checkpoint,
            status=args.status,
            include_findings=args.include_findings,
        )
    if cmd == "disposition":
        return service.set_review_finding_disposition(
            args.finding_id,
            disposition=args.to,
            notes=args.notes,
            followup_task_id=args.followup_task_id,
        )
    raise ValidationError(f"unknown review command {cmd}")


if __name__ == "__main__":
    sys.exit(main())
