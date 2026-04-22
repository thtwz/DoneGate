_TARGET_CONTEXT = {"repo_root": "str?", "data_root": "str?"}


TOOLS = {
    "project_init": {"project_name": "str", "default_branch": "str?", **_TARGET_CONTEXT},
    "project_dashboard": {"include_tasks": "bool?", "limit": "int?", **_TARGET_CONTEXT},
    "task_create": {
        "title": "str",
        "spec_ref": "str",
        "summary": "str?",
        "verification_mode": "manual|self-test?",
        "test_commands": "list[str]?",
        "required_doc_refs": "list[str]?",
        "required_artifacts": "list[str]?",
        "owned_paths": "list[str]?",
        "plan_node_id": "str?",
        **_TARGET_CONTEXT,
    },
    "task_list": {"status": "str?", "limit": "int?", **_TARGET_CONTEXT},
    "task_transition": {"task_id": "str", "target_status": "str", "reason": "str?", "notes": "str?", **_TARGET_CONTEXT},
    "task_record_verification": {"task_id": "str", "result": "passed|failed", "ref": "str?", "notes": "str?", **_TARGET_CONTEXT},
    "task_record_doc_sync": {"task_id": "str", "result": "synced|outdated", "ref": "str?", "notes": "str?", **_TARGET_CONTEXT},
    "task_update_acceptance_protocol": {"task_id": "str", "verification_mode": "manual|self-test?", "test_commands": "list[str]?", "required_doc_refs": "list[str]?", "required_artifacts": "list[str]?", "owned_paths": "list[str]?", "plan_node_id": "str?", **_TARGET_CONTEXT},
    "task_run_self_test": {"task_id": "str", "workdir": "str?", **_TARGET_CONTEXT},
    "spec_refresh": {"spec_ref": "str", "reason": "str?", **_TARGET_CONTEXT},
    "deviation_record": {"task_id": "str", "summary": "str", "details": "str", "spec_ref": "str?", **_TARGET_CONTEXT},
    "deviation_list": {**_TARGET_CONTEXT},
    "task_block": {"task_id": "str", "reason": "str", **_TARGET_CONTEXT},
    "task_unblock": {"task_id": "str", "target_status": "str", **_TARGET_CONTEXT},
}
