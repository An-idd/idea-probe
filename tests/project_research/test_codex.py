import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from project_research import codex_client
from project_research.codex_client import CodexClient, CodexError, TransientCodexError, diagnostic
from project_research.config import CodexConfig
from project_research.schemas import ScreenResult


def ready_client(monkeypatch, **kwargs):
    client = CodexClient(CodexConfig(**kwargs), {})
    client._command = [sys.executable]
    monkeypatch.setattr(codex_client.time, "sleep", lambda _: None)
    return client


def test_stdin_schema_unicode_and_isolated_result(monkeypatch):
    commands = []
    class Process:
        returncode = 0
        def __init__(self, args, **kwargs):
            commands.append(args)
            assert kwargs["shell"] is False and kwargs["encoding"] == "utf-8"
            self.output = Path(args[args.index("-o") + 1])
            schema = json.loads(Path(args[args.index("--output-schema") + 1]).read_text())
            assert schema["additionalProperties"] is False
            assert "--ephemeral" in args and "read-only" in args
        def communicate(self, text, timeout):
            assert text == "中文输入 ` $()\nLong prompt"
            self.output.write_text('{"signal_ids": ["中文"]}', encoding="utf-8")
            return '{"type":"turn.completed","usage":{"input_tokens":10}}', ""
    monkeypatch.setattr(codex_client.subprocess, "Popen", Process)
    client = ready_client(monkeypatch, models=["configured-model"], attempts=1)
    for _ in range(2):
        assert client("project_ideator", "中文输入 ` $()\nLong prompt", ScreenResult).signal_ids == ["中文"]
    assert commands[0][commands[0].index("-o") + 1] != commands[1][commands[1].index("-o") + 1]
    assert client.calls[0]["actual_model"] == "unknown"
    assert client.calls[0]["usage"]["input_tokens"] == 10


def test_mcp_servers_are_individually_disabled(monkeypatch):
    monkeypatch.setattr(codex_client.shutil, "which", lambda _: "C:/A Folder/codex.exe")
    monkeypatch.setattr(codex_client.subprocess, "run", lambda args, **k: SimpleNamespace(
        returncode=0, stderr="", stdout=json.dumps([
            {"name": "test-server", "enabled": 'mcp_servers.test-server.enabled=false' not in args}])))
    client = CodexClient(CodexConfig(), {})
    args = client._prepare()
    assert 'mcp_servers.test-server.enabled=false' in args
    assert "hooks" in args and "shell_tool" in args and 'web_search="disabled"' in args


def test_missing_executable(monkeypatch):
    monkeypatch.setattr(codex_client.shutil, "which", lambda _: None)
    with pytest.raises(CodexError, match="not found"):
        CodexClient(CodexConfig(), {})("project_ideator", "hello", ScreenResult)


@pytest.mark.parametrize("mode", ["timeout", "exit", "empty", "bad_json", "tool"])
def test_process_failures_are_not_success(monkeypatch, mode):
    stopped = []
    class Process:
        returncode = 1 if mode == "exit" else 0
        def __init__(self, args, **kwargs):
            self.path = Path(args[args.index("-o") + 1])
        def communicate(self, text, timeout):
            if mode == "timeout":
                raise subprocess.TimeoutExpired("codex", timeout)
            if mode == "bad_json":
                self.path.write_text("not json", encoding="utf-8")
            if mode == "tool":
                return '{"item":{"type":"command_execution"}}', ""
            return "", "authentication failed" if mode == "exit" else ""
    monkeypatch.setattr(codex_client.subprocess, "Popen", Process)
    monkeypatch.setattr(codex_client, "stop_process", lambda p: stopped.append(p))
    client = ready_client(monkeypatch, attempts=1)
    with pytest.raises(CodexError):
        client("project_ideator", "hi", ScreenResult)
    assert len(stopped) == (1 if mode == "timeout" else 0)
    assert client.calls[0]["status"] == "failed"


def test_fallback_only_uses_explicit_models(monkeypatch):
    calls = []
    client = ready_client(monkeypatch, models=["first", "second"], attempts=2)
    def invoke(base, role, model_name, text, cls):
        calls.append(model_name)
        if model_name == "first":
            raise TransientCodexError("temporary")
        return ScreenResult([])
    monkeypatch.setattr(client, "_invoke", invoke)
    assert client("project_ideator", "hi", ScreenResult) == ScreenResult([])
    assert calls == ["first", "first", "second"]


def test_diagnostics_hide_credentials(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "sensitive-value")
    assert "sensitive-value" not in diagnostic("request failed with sensitive-value")


def test_real_subprocess_boundary_with_fake_cli(tmp_path):
    # This tests OS stdin/Unicode/files rather than a real model or network connection.
    shim = tmp_path / "fake codex.py"
    shim.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "text=sys.stdin.read()\n"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps({'signal_ids':[text]}),encoding='utf-8')\n",
        encoding="utf-8")
    client = CodexClient(CodexConfig(attempts=1), {})
    client._command = [sys.executable, "-X", "utf8", str(shim)]
    assert client("project_ideator", "Unicode 中文", ScreenResult).signal_ids == ["Unicode 中文"]
