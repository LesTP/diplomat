"""Static HTML dashboard for Diplomat negotiation outcomes.

Run-discovery over self-play result JSONs stays here. Scenario rendering lives
in `scenario_authoring.scenario_viz`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scenario_authoring.scenario_viz import build_deals, build_scenario_viz, find_narrative

MODEL_PRETTY = {
    "gpt41nano": "gpt-4.1-nano",
    "gpt41mini": "gpt-4.1-mini",
    "gpt54mini": "gpt-5.4-mini",
    "claudesonnet46": "claude-sonnet-4-6",
    "claudehaiku45": "claude-haiku-4-5",
    "gemini25flashlite": "gemini-2.5-flash-lite",
    "gemini25flash": "gemini-2.5-flash",
    "deepseekchat": "deepseek-v3",
    "deepseekr1": "deepseek-r1",
    "llama3370binstruct": "llama-3.3-70b",
}


def _outcome_tokens(outcome: str) -> set[str]:
    toks = {outcome.split("(")[0].strip().lower()}
    for m in re.findall(r"\d+\s*[a-zA-Z]+", outcome):
        toks.add(m.replace(" ", "").lower())
    return toks


def extract_positions(round_responses: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rnd in sorted(round_responses, key=lambda x: int(x)):
        out[rnd] = {}
        for fac, msg in round_responses[rnd].items():
            text = (msg or "").lower()
            compact = text.replace(" ", "")
            fp: dict[str, str | None] = {}
            for iss in issues:
                best, best_pos = None, -1
                for outcome in iss["outcomes"]:
                    for tok in _outcome_tokens(outcome):
                        idx = text.rfind(tok)
                        if idx < 0:
                            idx = compact.rfind(tok.replace(" ", ""))
                        if idx > best_pos:
                            best_pos, best = idx, outcome
                fp[iss["name"]] = best
            out[rnd][fac] = fp
    return out


def _gen_provider(log: list[dict[str, Any]]) -> str:
    cnt: dict[str, int] = {}
    for c in log:
        p = c.get("config_provider")
        if isinstance(p, str):
            cnt[p] = cnt.get(p, 0) + 1
    if not cnt:
        return "?"
    if len(cnt) == 1:
        return next(iter(cnt))
    return min(cnt, key=lambda k: cnt[k])


def _run_meta(stem: str, gen_prov: str) -> dict[str, str]:
    parts = stem.split("_")
    run_tag = parts[0].replace("run", "R") if parts[0].startswith("run") else parts[0]
    mode = next((p for p in parts if p in ("full", "bare")), "full")
    model_key = next((p for p in parts if p in MODEL_PRETTY), "")
    n = parts[-1] if parts[-1].isdigit() else ""
    model_disp = MODEL_PRETTY.get(model_key, "")
    cell = f"{model_disp} · {mode}" if model_disp else f"{run_tag} · {gen_prov}-gen"
    label = " · ".join(b for b in [run_tag, mode, (model_disp or gen_prov + "-gen"), ("#" + n) if n else ""] if b)
    return {"run_tag": run_tag, "mode": mode, "model": model_disp, "cell": cell, "label": label, "gen": gen_prov}


def discover_runs(results_dir: Path, analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    runs: list[dict[str, Any]] = []
    matched_finals = checked_finals = 0
    for path in sorted(results_dir.glob("*.json")):
        name = path.name.lower()
        if "dryrun" in name or "smoke" in name:
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        sa = d.get("scenario_analysis")
        if not isinstance(sa, dict) or "scores" not in d:
            continue
        if sa.get("scoring") != analysis["scoring"] or sa.get("batna") != analysis["batna"]:
            continue
        s = d["scores"]
        deal = s.get("agreed_outcomes") if s.get("deal_reached") else None
        positions = extract_positions(d.get("round_responses", {}), analysis["issues"])
        if deal and positions:
            checked_finals += 1
            last = positions[max(positions, key=lambda x: int(x))]
            if all(any(last[f].get(iss) == out for f in analysis["factions"]) for iss, out in deal.items()):
                matched_finals += 1
        meta = _run_meta(path.stem, _gen_provider(d.get("llm_call_log", [])))
        runs.append(
            {
                "id": path.stem,
                **meta,
                "deal_reached": bool(s.get("deal_reached")),
                "agreed_outcomes": deal,
                "scores": {f: s["faction_scores"][f]["points"] for f in analysis["factions"]},
                "surplus": s.get("negotiated_surplus_share"),
                "bare_mode": bool(d.get("bare_mode")),
                "positions": positions,
            }
        )
    return runs, matched_finals, checked_finals


def detect_bottleneck(runs: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
    issues = [i["name"] for i in analysis["issues"]]
    counts = {i: 0 for i in issues}
    for r in runs:
        pos = r["positions"]
        if not pos:
            continue
        last = pos[max(pos, key=lambda x: int(x))]
        for iss in issues:
            vals = {last[f].get(iss) for f in analysis["factions"]}
            if len(vals) > 1:
                counts[iss] += 1
    return max(counts, key=lambda k: counts[k]) if any(counts.values()) else issues[-1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--analysis", required=True, type=Path)
    p.add_argument("--results-dir", type=Path, default=Path("tests/self_play/results"))
    p.add_argument("--narrative", type=Path, default=None, help="Scenario narrative .md (auto-detected if omitted)")
    p.add_argument("--title", default="negotiation outcomes")
    p.add_argument("--output", type=Path, default=Path("viz.html"))
    args = p.parse_args(argv)

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    runs, matched, checked = discover_runs(args.results_dir, analysis)
    bottleneck = detect_bottleneck(runs, analysis)
    note = (
        f"Final-round extraction matched the recorded deal in {matched}/{checked} closing run(s) — earlier rounds are approximate."
        if checked
        else "Positions are heuristic substring matches over round messages — approximate."
    )
    nar_path = args.narrative or find_narrative(args.analysis)
    narrative_text = nar_path.read_text(encoding="utf-8") if nar_path and nar_path.exists() else ""
    build_scenario_viz(
        analysis,
        args.output,
        runs=runs,
        title=args.title,
        narrative_text=narrative_text,
        extraction_note=note,
        bottleneck=bottleneck,
        fallback_title=args.title,
    )
    print(
        f"Wrote {args.output} · {len(runs)} run(s) · {len(build_deals(analysis))} deals · "
        f"extraction {matched}/{checked} · narrative {'yes' if narrative_text else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
