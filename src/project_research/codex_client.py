"""One isolated, structured Codex CLI task per call; no HTTP model provider."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TypeVar

from api_retry import retry_call

from .config import CodexConfig, ROLES
from .schemas import decode, json_schema

T = TypeVar("T")


class CodexError(RuntimeError):
    """A non-retriable CLI/configuration failure."""


class TransientCodexError(CodexError):
    """A bounded retry may recover this call."""


def diagnostic(text: str) -> str:
    for name, value in os.environ.items():
        if len(value) > 5 and any(word in name.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
            text = text.replace(value, "[redacted]")
    text = re.sub(r"(?i)(bearer\s+|(?:api[_-]?key|token|secret)\s*[:=]\s*)\S+", r"\1[redacted]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", text)
    return text[-1500:]


def stop_process(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The process may exit between timeout and cleanup.
    if process.poll() is None:
        process.kill()
    process.communicate()


class CodexClient:
    def __init__(self, config: CodexConfig, roles: dict[str, list[str]]):
        self.config, self.roles = config, roles
        self.calls: list[dict] = []
        self._setup_lock = threading.Lock()
        self._limit = threading.BoundedSemaphore(config.max_concurrency)
        self._command: list[str] | None = None

    def _prepare(self) -> list[str]:
        with self._setup_lock:
            if self._command is not None:
                return list(self._command)
            executable = shutil.which(self.config.executable)
            if not executable:
                raise CodexError("Codex executable not found; set project_research.codex.executable")
            base = [executable]
            # Empty TOML tables merge with user config; enumerate and disable each MCP explicitly.
            try:
                listing = subprocess.run(base + ["mcp", "list", "--json"], capture_output=True, text=True,
                                         encoding="utf-8", timeout=30, check=False,
                                         **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
                if listing.returncode:
                    raise CodexError("Cannot inspect Codex MCP configuration: " + diagnostic(listing.stderr))
                servers = json.loads(listing.stdout)
                if not isinstance(servers, list):
                    raise ValueError("Expected MCP list")
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                raise CodexError("Cannot inspect Codex MCP configuration") from exc
            for server in servers:
                name = server["name"]
                if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    raise CodexError("MCP name cannot be safely overridden; rename it to letters/digits/_/-")
                # Plugin-injected servers may not have a user TOML table. Disabled entries still
                # need a valid transport to deserialize; give them an inert, never-started target.
                transport = server.get("transport", {}).get("type", "stdio")
                endpoint = ("command=" + json.dumps(sys.executable) if transport == "stdio" else
                            'url="https://example.invalid/disabled"')
                base += ["-c", f"mcp_servers.{name}.{endpoint}"]
                base += ["-c", f"mcp_servers.{name}.enabled=false", "-c", f"mcp_servers.{name}.required=false"]
            for feature in ("shell_tool", "unified_exec", "apps", "plugins", "hooks", "multi_agent",
                            "multi_agent_v2", "memories", "skill_mcp_dependency_install"):
                base += ["--disable", feature]
            base += ["-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
                     "-c", 'approval_policy="never"', "-c", 'developer_instructions=""']
            verified = subprocess.run(base + ["mcp", "list", "--json"], capture_output=True, text=True,
                                      encoding="utf-8", timeout=30, check=False,
                                      **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            if verified.returncode or any(s.get("enabled", True) for s in json.loads(verified.stdout)):
                raise CodexError("Cannot disable all MCP servers for this research task")
            self._command = base
            return list(base)

    def __call__(self, role: str, prompt: str, response_type: type[T]) -> T:
        if role not in ROLES:
            raise ValueError(f"Unknown Project role: {role}")
        with self._limit:
            base = self._prepare()
            candidates = self.roles.get(role) or self.config.models or [""]
            failures = []
            for model_name in candidates:
                try:
                    return retry_call(
                        lambda: self._invoke(base, role, model_name, prompt, response_type),
                        attempts=self.config.attempts,
                        should_retry_exception=lambda exc: isinstance(exc, TransientCodexError),
                        operation_name=f"Codex {role}",
                    )
                except (CodexError, RuntimeError) as exc:
                    failures.append(diagnostic(str(exc)))
                    logging.warning("[Codex] %s failed: %s", role, failures[-1])
            raise CodexError(f"{role} exhausted configured models: " + "; ".join(failures))

    def _invoke(self, base: list[str], role: str, model_name: str, prompt: str, response_type: type[T]) -> T:
        started = time.monotonic()
        record = {"role": role, "requested_model": model_name or "Codex configured default",
                  "actual_model": "unknown", "status": "failed"}
        try:
            with tempfile.TemporaryDirectory(prefix="project-research-") as directory:
                workdir = Path(directory)
                schema, output = workdir / "schema.json", workdir / "response.json"
                schema.write_text(json.dumps(json_schema(response_type)), encoding="utf-8")
                command = base + ["exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check",
                                  "--cd", str(workdir), "--output-schema", str(schema), "-o", str(output),
                                  "--json", "--color", "never"]
                if model_name:
                    command += ["--model", model_name]
                if self.config.reasoning_effort:
                    command += ["-c", "model_reasoning_effort=" + json.dumps(self.config.reasoning_effort)]
                command += ["-"]
                kwargs = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
                          if os.name == "nt" else {"start_new_session": True})
                logging.info("[Codex] %s (%s)", role, record["requested_model"])
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                           cwd=workdir, shell=False, **kwargs)
                try:
                    stdout, stderr = process.communicate(prompt, timeout=self.config.timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    stop_process(process)
                    raise TransientCodexError(f"Codex timed out after {self.config.timeout_seconds}s") from exc
                except BaseException:
                    stop_process(process)
                    raise
                record["exit_code"] = process.returncode
                if process.returncode:
                    detail = diagnostic(stderr)
                    transient = any(word in detail.lower() for word in
                                    ("429", "rate limit", "timed out", "connection", "502", "503", "504"))
                    error = TransientCodexError if transient else CodexError
                    raise error(f"Codex exited {process.returncode}: {detail}")
                for line in stdout.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") in ("turn.failed", "error"):
                        raise TransientCodexError("Codex reported a failed turn")
                    if event.get("type") == "turn.completed":
                        record["usage"] = event.get("usage", {})
                    if event.get("item", {}).get("type") in (
                            "command_execution", "file_change", "mcp_tool_call", "web_search"):
                        raise CodexError("Unexpected tool use in a structured research task; result discarded")
                try:
                    result = decode(response_type, json.loads(output.read_text(encoding="utf-8")))
                except (OSError, ValueError) as exc:
                    raise TransientCodexError("Codex returned no valid structured result: " + str(exc)) from exc
                record["status"] = "completed"
                return result
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            self.calls.append(record)
