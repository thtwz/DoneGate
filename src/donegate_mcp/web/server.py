"""Loopback HTTP entry point for the bundled dashboard."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import webbrowser

from donegate_mcp.errors import DoneGateMcpError, ValidationError
from donegate_mcp.web.read_model import portfolio, project_detail
from donegate_mcp.web.registry import ProjectRegistry

_KEY = r"[a-f0-9]{24}"
_STATIC = {"/static/app.css": ("app.css", "text/css; charset=utf-8"),
           "/static/app.js": ("app.js", "text/javascript; charset=utf-8")}
_CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


def make_server(registry: ProjectRegistry, port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            # Polling should not flood the terminal with a line every 5 seconds.
            pass

        def send_body(self, status, content, content_type="application/json; charset=utf-8"):
            body = json.dumps(content, ensure_ascii=False).encode() if not isinstance(content, bytes) else content
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", _CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def guard(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            if host not in allowed:
                self.send_body(403, {"error": "仅允许本机访问"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{host}":
                self.send_body(403, {"error": "请求来源不匹配"})
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_body(403, {"error": "不允许跨站请求"})
                return False
            return True

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def do_DELETE(self):
            self.dispatch("DELETE")

        def dispatch(self, method):
            try:
                if self.guard():
                    self.route(method, urlsplit(self.path).path)
            except KeyError:
                self.send_body(404, {"error": "找不到项目或记录"})
            except (DoneGateMcpError, OSError, ValueError, TypeError) as exc:
                self.send_body(400 if method == "POST" else 422, {"error": str(exc)})

        def route(self, method, path):
            if method == "GET":
                if path == "/api/projects":
                    return self.send_body(200, portfolio(registry))
                if re.fullmatch(rf"/api/projects/({_KEY})", path):
                    entry = registry.get(path.rsplit("/", 1)[-1])
                    try:
                        result = project_detail(entry)
                    except (DoneGateMcpError, OSError, ValueError, TypeError, KeyError) as exc:
                        return self.send_body(422, {"error": f"项目数据无法读取：{exc}"})
                    return self.send_body(200, result)
                if path in _STATIC:
                    filename, content_type = _STATIC[path]
                    return self.send_body(200, files("donegate_mcp.web").joinpath("static", filename).read_bytes(), content_type)
                if path == "/" or re.fullmatch(rf"/projects/{_KEY}/(overview|features|changes)", path):
                    return self.send_body(200, files("donegate_mcp.web").joinpath("static", "index.html").read_bytes(), "text/html; charset=utf-8")
            if method == "POST" and path == "/api/projects":
                if self.headers.get_content_type() != "application/json":
                    return self.send_body(415, {"error": "需要 application/json 请求"})
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 65536:
                    return self.send_body(413, {"error": "请求内容过大"})
                if self.headers.get("Transfer-Encoding"):
                    return self.send_body(400, {"error": "不支持此传输编码"})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get("repo_root"), str):
                    raise ValidationError("请填写仓库的绝对路径")
                if payload.get("data_root") is not None and not isinstance(payload["data_root"], str):
                    raise ValidationError("数据目录必须是绝对路径字符串")
                entry = registry.add(payload["repo_root"], payload.get("data_root") or None)
                return self.send_body(201, {"project": entry})
            if method == "DELETE" and re.fullmatch(rf"/api/projects/({_KEY})", path):
                registry.remove(path.rsplit("/", 1)[-1])
                return self.send_body(200, {"ok": True})
            self.send_body(404, {"error": "找不到此页面或接口"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def run_ui(*, port: int = 8765, registry_path: str | None = None,
           projects: list[str] | None = None, repo_root: str | None = None,
           data_root: str | None = None, no_open: bool = False) -> int:
    if port < 0 or port > 65535:
        raise ValidationError("端口必须在 0–65535 之间")
    registry = ProjectRegistry(Path(registry_path) if registry_path else None)
    try:
        server = make_server(registry, port=port)
    except OSError as exc:
        raise ValidationError(f"无法启动看板，端口 {port} 可能已被占用；打开已有看板或用 --port 指定其他端口：{exc}") from exc
    try:
        if repo_root:
            registry.add(str(Path(repo_root).expanduser().resolve()), data_root)
        elif data_root:
            raise ValidationError("ui 使用 --data-root 时也需要明确 --repo-root")
        for path in projects or []:
            registry.add(path)
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"DoneGate 看板：{url}\n项目索引：{registry.path}\n按 Ctrl+C 停止服务。", flush=True)
        if not no_open:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
