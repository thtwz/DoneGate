from __future__ import annotations

import os
from pathlib import Path
from functools import wraps
from inspect import signature
from typing import Any, Callable

from donegate_mcp import __version__
from donegate_mcp.domain.services import DoneGateService
from donegate_mcp.errors import DoneGateMcpError, ValidationError
from donegate_mcp.context import resolve_mcp_context
from donegate_mcp.compact import compact_payload


class SimpleToolServer:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {}

    def tool(self, name: str) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
        def decorator(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
            self.tools[name] = func
            return func
        return decorator


class DoneGateMcpApp:
    def __init__(self, data_root: str | None = None) -> None:
        self.default_data_root = str(Path(data_root).resolve()) if data_root is not None else None
        self.server = self._build_server()

    def _resolve_call_context(self, repo_root: str | None = None, data_root: str | None = None) -> tuple[DoneGateService, str | None]:
        resolved_data_root, resolved_repo_root = resolve_mcp_context(repo_root, data_root, self.default_data_root)
        service = DoneGateService(data_root=resolved_data_root, repo_root=resolved_repo_root)
        return service, str(resolved_repo_root) if resolved_repo_root else None

    def _guard(self, func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        @wraps(func)
        def guarded(*args: Any, **kwargs: Any) -> dict[str, Any]:
            bound = signature(func).bind(*args, **kwargs)
            payload = self._safe(func, *args, **kwargs)
            return compact_payload(payload) if bound.arguments.get("compact", False) else payload
        return guarded

    def _build_server(self) -> Any:
        try:
            from mcp.server.fastmcp import FastMCP  # type: ignore
            # Use an identifier-safe MCP server name so host tooling can derive
            # stable namespaces without needing to sanitize hyphenated labels.
            server: Any = FastMCP("donegate_mcp")
            server._mcp_server.version = __version__
        except Exception:
            server = SimpleToolServer()
        self._register_tools(server)
        return server

    def _register_tools(self, server: Any) -> None:
        @server.tool("project_init")
        @self._guard
        def project_init(project_name: str, default_branch: str | None = None, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, resolved_repo_root = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.init_project, project_name, default_branch, repo_root=resolved_repo_root)

        @server.tool("project_dashboard")
        @self._guard
        def project_dashboard(include_tasks: bool = False, limit: int = 10, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.dashboard, include_tasks=include_tasks, limit=limit)

        @server.tool("project_context")
        @self._guard
        def project_context(repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, resolved_repo_root = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return service.get_context(repo_root=resolved_repo_root)

        @server.tool("task_get")
        @self._guard
        def task_get(task_id: str, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return service.get_task(task_id)

        @server.tool("task_activate")
        @self._guard
        def task_activate(task_id: str, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, resolved_repo_root = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return service.activate_task(task_id, repo_root=resolved_repo_root)

        @server.tool("task_create")
        @self._guard
        def task_create(title: str, spec_ref: str, summary: str = "", verification_mode: str = "manual", test_commands: list[str] | None = None, required_doc_refs: list[str] | None = None, required_artifacts: list[str] | None = None, owned_paths: list[str] | None = None, plan_node_id: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.create_task, title, spec_ref, summary=summary, verification_mode=verification_mode, test_commands=test_commands, required_doc_refs=required_doc_refs, required_artifacts=required_artifacts, owned_paths=owned_paths, plan_node_id=plan_node_id)

        @server.tool("task_list")
        @self._guard
        def task_list(status: str | None = None, limit: int | None = None, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.list_tasks, status=status, limit=limit)

        @server.tool("task_transition")
        @self._guard
        def task_transition(task_id: str, target_status: str, reason: str | None = None, notes: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.transition_task, task_id, target_status, reason=reason, notes=notes)

        @server.tool("task_record_verification")
        @self._guard
        def task_record_verification(task_id: str, result: str, ref: str | None = None, notes: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.record_verification, task_id, result, ref=ref, notes=notes)

        @server.tool("task_record_doc_sync")
        @self._guard
        def task_record_doc_sync(task_id: str, result: str, ref: str | None = None, notes: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.record_doc_sync, task_id, result, ref=ref, notes=notes)

        @server.tool("task_update_acceptance_protocol")
        @self._guard
        def task_update_acceptance_protocol(task_id: str, verification_mode: str | None = None, test_commands: list[str] | None = None, required_doc_refs: list[str] | None = None, required_artifacts: list[str] | None = None, owned_paths: list[str] | None = None, plan_node_id: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.update_acceptance_protocol, task_id, verification_mode=verification_mode, test_commands=test_commands, required_doc_refs=required_doc_refs, required_artifacts=required_artifacts, owned_paths=owned_paths, plan_node_id=plan_node_id)

        @server.tool("task_run_self_test")
        @self._guard
        def task_run_self_test(task_id: str, workdir: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.run_self_test, task_id, workdir=workdir)

        @server.tool("spec_refresh")
        @self._guard
        def spec_refresh(spec_ref: str, reason: str | None = None, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.refresh_spec, spec_ref, reason=reason)

        @server.tool("deviation_record")
        @self._guard
        def deviation_record(task_id: str, summary: str, details: str, spec_ref: str | None = None, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.record_deviation, task_id, summary, details, spec_ref=spec_ref)

        @server.tool("deviation_list")
        @self._guard
        def deviation_list(repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.list_deviations)

        @server.tool("task_block")
        @self._guard
        def task_block(task_id: str, reason: str, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.block_task, task_id, reason)

        @server.tool("task_reopen")
        @self._guard
        def task_reopen(task_id: str, target_status: str = "in_progress", repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.reopen_task, task_id, target_status=target_status)

        @server.tool("task_unblock")
        @self._guard
        def task_unblock(task_id: str, target_status: str, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.unblock_task, task_id, target_status)

        @server.tool("task_review")
        @self._guard
        def task_review(
            task_id: str,
            checkpoint: str = "manual",
            provider_id: str = "manual",
            summary: str = "",
            overall_recommendation: str = "proceed",
            findings: list[dict[str, Any]] | None = None,
            review_run_id: str | None = None,
            repo_root: str | None = None,
            data_root: str | None = None,
            compact: bool = False,
        ) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(
                service.record_task_review,
                task_id,
                checkpoint=checkpoint,
                provider_id=provider_id,
                summary=summary,
                overall_recommendation=overall_recommendation,
                findings=findings,
                review_run_id=review_run_id,
            )

        @server.tool("review_list")
        @self._guard
        def review_list(task_id: str | None = None, checkpoint: str | None = None, status: str | None = None, include_findings: bool = False, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.list_reviews, task_id=task_id, checkpoint=checkpoint, status=status, include_findings=include_findings)

        @server.tool("review_disposition")
        @self._guard
        def review_disposition(finding_id: str, disposition: str, notes: str | None = None, followup_task_id: str | None = None, repo_root: str | None = None, data_root: str | None = None) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.set_review_finding_disposition, finding_id, disposition, notes=notes, followup_task_id=followup_task_id)

        @server.tool("task_create_from_finding")
        @self._guard
        def task_create_from_finding(finding_id: str, title: str | None = None, summary: str | None = None, plan_node_id: str | None = None, repo_root: str | None = None, data_root: str | None = None, compact: bool = False) -> dict[str, Any]:
            service, _ = self._resolve_call_context(repo_root=repo_root, data_root=data_root)
            return self._safe(service.create_followup_task_from_finding, finding_id, title=title, summary=summary, plan_node_id=plan_node_id)

    @staticmethod
    def _safe(func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return func(*args, **kwargs)
        except DoneGateMcpError as exc:
            return {"ok": False, "errors": [str(exc)], "error_code": "validation_error" if isinstance(exc, ValidationError) else "domain_error"}


def build_app(data_root: str | None = None) -> DoneGateMcpApp:
    return DoneGateMcpApp(data_root=data_root)


def main(data_root: str | None = None) -> int:
    resolved_root = data_root or os.environ.get("DONEGATE_MCP_DATA_ROOT")
    app = build_app(resolved_root)
    server = app.server
    if hasattr(server, "run"):
        server.run()
        return 0
    raise SystemExit("donegate-mcp fallback server loaded; install mcp in runtime env")


if __name__ == "__main__":
    raise SystemExit(main())
