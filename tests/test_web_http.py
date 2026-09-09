import http.client
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

import pytest

from test_web import files, make_project


@pytest.fixture
def running(tmp_path):
    from donegate_mcp.web.registry import ProjectRegistry
    from donegate_mcp.web.server import make_server
    server = make_server(ProjectRegistry(tmp_path / "registry.json"), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


def test_http_register_read_remove_real_project_and_deep_links(running, tmp_path):
    service, spec = make_project(tmp_path / "repo")
    service.create_task("Visible feature", str(spec))
    before = files(service.data_root)
    status, body, _ = request(running, "POST", "/api/projects", json.dumps({"repo_root": str(spec.parent)}), {"Content-Type": "application/json"})
    assert status == 201
    key = json.loads(body)["project"]["key"]
    status, body, _ = request(running, "GET", f"/api/projects/{key}")
    assert status == 200 and json.loads(body)["tasks"][0]["title"] == "Visible feature"
    assert before == files(service.data_root)
    status, body, headers = request(running, "GET", f"/projects/{key}/features")
    assert status == 200 and b"DoneGate" in body
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert request(running, "DELETE", f"/api/projects/{key}")[0] == 200
    assert request(running, "GET", f"/api/projects/{key}")[0] == 404
    assert before == files(service.data_root)


def test_http_guards_invalid_input_paths_host_and_origin(running):
    assert request(running, "GET", "/api/projects", headers={"Host": "evil.example"})[0] == 403
    assert request(running, "POST", "/api/projects", "{}", {"Content-Type": "application/json", "Origin": "https://evil.example"})[0] == 403
    assert request(running, "POST", "/api/projects", "{}", {"Content-Type": "text/plain"})[0] == 415
    for body in ("[]", "null", "{broken", '{"repo_root":123}', '{"repo_root":"relative"}'):
        assert request(running, "POST", "/api/projects", body, {"Content-Type": "application/json"})[0] == 400
    assert request(running, "GET", "/static/../../pyproject.toml")[0] == 404
    assert request(running, "GET", "/api/projects/no-such-project")[0] == 404
    assert request(running, "GET", "/no-such-route")[0] == 404
    assert request(running, "POST", "/api/projects", "x" * 70000, {"Content-Type": "application/json"})[0] == 413


def test_cli_ui_parser_runs_before_repository_service_construction(tmp_path, monkeypatch):
    from donegate_mcp.cli.main import main
    from donegate_mcp.web import server
    calls = []
    monkeypatch.setattr(server, "run_ui", lambda **kwargs: calls.append(kwargs) or 0)
    monkeypatch.chdir(tmp_path)
    assert main(["ui", "--no-open", "--port", "8899", "--registry", str(tmp_path / "registry.json")]) == 0
    assert calls[0]["port"] == 8899
    assert not (tmp_path / ".donegate-mcp").exists()


@pytest.mark.parametrize("row", ['{"type":"spec_drift_detected","payload":null}', '{"payload":null}'])
def test_malformed_history_warns_instead_of_disconnecting(running, tmp_path, row):
    service, spec = make_project(tmp_path / "repo")
    task_id = service.create_task("Feature", str(spec))["task"]["task_id"]
    with (service.data_root / "events" / f"{task_id}.jsonl").open("a") as stream:
        stream.write(row + "\n")
    _, body, _ = request(running, "POST", "/api/projects", json.dumps({"repo_root": str(spec.parent)}), {"Content-Type": "application/json"})
    key = json.loads(body)["project"]["key"]
    status, body, _ = request(running, "GET", f"/api/projects/{key}")
    assert status == 200 and json.loads(body)["warnings"]


def test_concurrent_cli_writes_and_http_reads_are_consistent(running, tmp_path):
    service, spec = make_project(tmp_path / "repo")
    _, body, _ = request(running, "POST", "/api/projects", json.dumps({"repo_root": str(spec.parent)}), {"Content-Type": "application/json"})
    key = json.loads(body)["project"]["key"]

    def write_tasks():
        for i in range(4):
            result = subprocess.run([sys.executable, "-m", "donegate_mcp.cli.main", "--repo-root", str(spec.parent),
                "task", "create", "--title", f"Concurrent {i}", "--spec-ref", str(spec)], capture_output=True)
            assert result.returncode == 0, result.stderr.decode()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write_tasks)
        for _ in range(12):
            status, body, _ = request(running, "GET", f"/api/projects/{key}")
            detail = json.loads(body)
            assert status == 200
            assert detail["summary"]["total_tasks"] == len(detail["tasks"])
            assert all(any(e["type"] == "task_created" for e in t["events"]) for t in detail["tasks"])
        future.result()
    _, body, _ = request(running, "GET", f"/api/projects/{key}")
    assert json.loads(body)["summary"]["total_tasks"] == 4
