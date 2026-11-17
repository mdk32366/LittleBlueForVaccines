"""A stand-in for the Bluebird sidecar in tests (D-0049): a llama.cpp-style POST /completion on 127.0.0.1 only, on a
free port, in a daemon thread. No model: it answers from a rule, so the UI tests are deterministic. Every request
body is kept in `requests` so a test can check what the client sent."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Stub:
    def __init__(self, answer=lambda body: "Positive", status: int = 200, delay: float = 0.0):
        self.answer, self.status, self.delay, self.requests = answer, status, delay, []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server API)
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                stub.requests.append({"path": self.path, "body": body})
                if stub.delay:
                    time.sleep(stub.delay)
                out = json.dumps({"content": stub.answer(body), "stop": True}).encode()
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def free_port_url() -> str:
    """A loopback URL with nothing listening (connection refused): the model is down."""
    s = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = s.server_address[1]
    s.server_close()
    return f"http://127.0.0.1:{port}"
