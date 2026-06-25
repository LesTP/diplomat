"""Lock the scenario_authoring standalone contract.

Two guarantees:
  (a) Pure-core modules import without pulling in any modules.* namespace.
  (b) LLM paths (analyze_scenario, fill_narrative) raise ImportError, not
      AttributeError, when toolkit is unavailable.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# (a) No modules.* on import
# ---------------------------------------------------------------------------

_PURE_CORE = [
    "scenario_authoring",
    "scenario_authoring.scenario_spec",
    "scenario_authoring.scenario_fitness",
    "scenario_authoring.verify_scenario_optimum",
    "scenario_authoring.scenario_viz",
    "scenario_authoring.scenario_brief",
    "scenario_authoring.round_context",
]

_CHECK_SCRIPT = """
import sys
for mod in {mods!r}:
    __import__(mod)
leaked = [k for k in sys.modules if k == "modules" or k.startswith("modules.")]
if leaked:
    print("LEAKED:", leaked, flush=True)
    sys.exit(1)
sys.exit(0)
"""


def test_pure_core_imports_without_modules_namespace() -> None:
    """Importing pure-core scenario_authoring modules must not load modules.*."""
    result = subprocess.run(
        [sys.executable, "-c", _CHECK_SCRIPT.format(mods=_PURE_CORE)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"modules.* namespace leaked into scenario_authoring import.\n"
        f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
    )


# ---------------------------------------------------------------------------
# (b) LLM paths raise ImportError (not AttributeError) without toolkit
# ---------------------------------------------------------------------------

_TOOLKIT_BLOCKER = {
    "toolkit": None,
    "toolkit.structured_llm": None,
}


def test_analyze_scenario_raises_import_error_without_toolkit() -> None:
    """analyze_scenario raises ImportError when toolkit.structured_llm is absent."""
    from scenario_authoring import analyze_scenario

    with patch.dict(sys.modules, _TOOLKIT_BLOCKER):
        with pytest.raises(ImportError):
            asyncio.run(analyze_scenario("scenario text", object(), {}, "commodity"))


def test_fill_narrative_raises_import_error_without_toolkit() -> None:
    """fill_narrative raises ImportError when toolkit.structured_llm is absent."""
    from scenario_authoring import fill_narrative

    with patch.dict(sys.modules, _TOOLKIT_BLOCKER):
        with pytest.raises(ImportError):
            asyncio.run(fill_narrative({}, "title", object(), {}, "commodity"))


def test_unified_dispatcher_routes_subcommands(tmp_path, monkeypatch) -> None:
    """The package dispatcher should route subcommands without altering behavior."""
    from scenario_authoring.__main__ import main as dispatch_main

    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(
        (
            '{"factions":["a"],"issues":[{"name":"x","outcomes":["y"],'
            '"description":""}],"scoring":{"a":{"x":{"y":1}}},"batna":{"a":0}}'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["scenario_authoring", "verify", "--analysis", str(analysis_path)],
    )
    assert dispatch_main() == 0

    monkeypatch.setattr(sys, "argv", ["scenario_authoring", "does-not-exist"])
    assert dispatch_main() == 2
