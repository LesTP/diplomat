from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVICE_SH = PROJECT_ROOT / "tools" / "service.sh"


pytestmark = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")


def _run_service(script: Path, session: str, command: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BOT_TMUX_SESSION"] = session
    return subprocess.run(
        ["bash", str(script), command],
        cwd=script.parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tmux", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_service_sh_start_status_stop_with_temp_tmux_session(tmp_path: Path) -> None:
    session = "_test_diplomat_session"
    test_root = tmp_path / "diplomat"
    script = test_root / "tools" / "service.sh"
    fake_python = test_root / ".venv" / "bin" / "python"

    (test_root / "tools").mkdir(parents=True)
    (test_root / ".venv" / "bin").mkdir(parents=True)
    (test_root / "src").mkdir()
    (test_root / "config").mkdir()
    (test_root / "src" / "main.py").write_text("# fake main\n", encoding="utf-8")
    (test_root / "config" / "pipeline_smoke.yaml").write_text("{}\n", encoding="utf-8")
    shutil.copy2(SERVICE_SH, script)
    fake_python.write_text(
        "#!/bin/sh\n"
        "echo fake diplomat started\n"
        "sleep 60\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    _tmux("kill-session", "-t", session)
    assert _tmux("new-session", "-d", "-s", session, "-n", "keep", "sleep 120").returncode == 0
    try:
        start = _run_service(script, session, "start")
        assert start.returncode == 0, start.stderr
        assert f"Diplomat started (tmux window {session}:diplomat" in start.stdout

        deadline = time.time() + 5
        status = _run_service(script, session, "status")
        while "Diplomat is running" not in status.stdout and time.time() < deadline:
            time.sleep(0.1)
            status = _run_service(script, session, "status")
        assert status.returncode == 0
        assert f"Diplomat is running (tmux window {session}:diplomat)" in status.stdout

        stop = _run_service(script, session, "stop")
        assert stop.returncode == 0
        assert f"Diplomat stopped (tmux window {session}:diplomat)" in stop.stdout

        stopped_status = _run_service(script, session, "status")
        assert stopped_status.returncode == 0
        assert "Diplomat is not running" in stopped_status.stdout
    finally:
        _tmux("kill-session", "-t", session)
