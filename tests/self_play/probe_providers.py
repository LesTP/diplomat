"""Live probe of LLM providers — cheap end-to-end auth + parse check.

Hits each configured provider once with a trivial prompt, asks for a JSON
response, and verifies the round-trip works (auth + completion + parse).
Catches the kind of integration bugs that DryRunLLMClient cannot:
- Missing API keys (e.g., `.env` not loaded)
- Markdown fence wrapping (Anthropic / Google JSON output)
- Provider-specific schema or parsing quirks
- Network/quota issues (429s) before they bite a real run

Run this before any live multi-provider simulation. ~$0.001 per provider
(10-50 input tokens, 10-30 output tokens). Uses 1 request per provider —
well under any reasonable daily quota.

Usage:
    python -m tests.self_play.probe_providers \\
        --providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},"beta":{"provider":"anthropic","model":"claude-haiku-4-5"},"gamma":{"provider":"google","model":"gemini-2.5-flash"}}'

Exits 0 if every probe passes; nonzero on any failure. Suitable for use
as a guard in scripts that launch live runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Load .env so all provider keys are visible to subprocess SDKs.
# This is the same fix run_simulation.py uses to avoid silent auth
# failures on Anthropic/Google when only OPENAI_API_KEY is in the shell.
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path)
except ImportError:
    pass

# Ensure src/ is importable.
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))


_PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        type=str,
        required=True,
        help=(
            "JSON map of label -> {provider, model}. Same format as "
            "run_simulation.py --per-faction-providers. The label is "
            "purely for readable output."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=50,
        help="Max tokens per probe (default: 50, keeps cost minimal)",
    )
    return parser.parse_args()


def _build_config(provider: str, model: str) -> dict:
    api_key_env = _PROVIDER_API_KEY_ENV.get(provider, "")
    api_key = os.getenv(api_key_env) if api_key_env else ""
    return {
        "provider": provider,
        "models": {
            "quality": model,
            "default": model,
            "commodity": model,
        },
        "api_key": api_key or "",
        "api_key_env": api_key_env,
    }


async def _probe_one(
    label: str,
    provider: str,
    model: str,
    adapter,
    max_tokens: int,
) -> dict:
    """Probe a single provider end to end. Return a result dict."""
    from toolkit.structured_llm.core import parse_json_response

    config = _build_config(provider, model)
    if not config["api_key"]:
        return {
            "label": label,
            "provider": provider,
            "model": model,
            "passed": False,
            "stage": "auth",
            "error": f"No API key found in env var {config['api_key_env']!r}",
            "duration_seconds": 0.0,
        }

    messages = [
        {
            "role": "system",
            "content": (
                'Reply with exactly this JSON object and nothing else: '
                '{"ok": true, "echo": "<the word from the user message>"}'
            ),
        },
        {"role": "user", "content": "ping"},
    ]

    start = time.monotonic()
    response_text = ""
    parsed: dict = {}
    try:
        result = adapter.complete(
            messages=messages, config=config, tier="commodity", max_tokens=max_tokens
        )
        if asyncio.iscoroutine(result):
            result = await result
        response_text = result if isinstance(result, str) else str(result)
    except Exception as exc:
        return {
            "label": label,
            "provider": provider,
            "model": model,
            "passed": False,
            "stage": "complete",
            "error": str(exc)[:300],
            "duration_seconds": round(time.monotonic() - start, 3),
            "response_preview": "",
        }

    if not response_text.strip():
        return {
            "label": label,
            "provider": provider,
            "model": model,
            "passed": False,
            "stage": "empty",
            "error": "Provider returned empty response",
            "duration_seconds": round(time.monotonic() - start, 3),
            "response_preview": "",
        }

    try:
        parsed = parse_json_response(response_text)
    except ValueError as exc:
        return {
            "label": label,
            "provider": provider,
            "model": model,
            "passed": False,
            "stage": "parse",
            "error": str(exc)[:300],
            "duration_seconds": round(time.monotonic() - start, 3),
            "response_preview": response_text[:200],
        }

    if "ok" not in parsed:
        return {
            "label": label,
            "provider": provider,
            "model": model,
            "passed": False,
            "stage": "schema",
            "error": (
                "Response parsed as JSON but did not contain 'ok' key. "
                f"Got keys: {sorted(parsed.keys())}"
            ),
            "duration_seconds": round(time.monotonic() - start, 3),
            "response_preview": response_text[:200],
        }

    return {
        "label": label,
        "provider": provider,
        "model": model,
        "passed": True,
        "stage": "ok",
        "error": None,
        "duration_seconds": round(time.monotonic() - start, 3),
        "response_preview": response_text[:200],
    }


async def _run(args: argparse.Namespace) -> int:
    try:
        providers_map = json.loads(args.providers)
    except json.JSONDecodeError as exc:
        print(f"ERROR: --providers is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(providers_map, dict):
        print("ERROR: --providers must be a JSON object", file=sys.stderr)
        return 2

    # Build the same adapter that the main runner uses.
    try:
        from adapters import ToolkitLLMAdapter
        import toolkit.llm_client as llm_module
        adapter = ToolkitLLMAdapter(llm_module)
    except ImportError as exc:
        print(f"ERROR: toolkit not importable: {exc}", file=sys.stderr)
        return 2

    print(f"Probing {len(providers_map)} provider(s)...")
    print()

    results = []
    for label, cfg in providers_map.items():
        if not isinstance(cfg, dict) or "provider" not in cfg or "model" not in cfg:
            print(f"  [{label}] SKIP — entry missing 'provider' or 'model'")
            results.append({
                "label": label, "passed": False, "stage": "config",
                "error": "missing provider or model",
            })
            continue
        provider = cfg["provider"]
        model = cfg["model"]
        print(f"  [{label}] {provider}/{model} ... ", end="", flush=True)
        result = await _probe_one(label, provider, model, adapter, args.max_tokens)
        if result["passed"]:
            print(f"OK ({result['duration_seconds']}s)")
        else:
            print(f"FAIL at '{result['stage']}' ({result['duration_seconds']}s)")
        results.append(result)

    # Report
    print()
    print("=" * 70)
    passed_n = sum(1 for r in results if r.get("passed"))
    print(f"Results: {passed_n}/{len(results)} passed")
    print("=" * 70)
    for r in results:
        if r.get("passed"):
            print(f"  [PASS] {r['label']:8s}  {r['provider']}/{r['model']}  "
                  f"({r['duration_seconds']}s)")
        else:
            print(f"  [FAIL] {r['label']:8s}  stage={r.get('stage','?')}")
            err = r.get("error") or "?"
            for line in err.splitlines()[:3]:
                print(f"          {line}")
            preview = r.get("response_preview", "")
            if preview:
                print(f"          response preview: {preview[:120]!r}")

    return 0 if passed_n == len(results) else 1


def main() -> None:
    args = _parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
