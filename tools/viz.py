"""Static HTML dashboard for Diplomat negotiation outcomes.

Reads a compiled scenario (scenario_analysis.json) plus the self-play result
JSONs that used that exact scoring + BATNA, enumerates the full deal space,
overlays where each run actually landed, and emits a single self-contained
HTML file (no external libraries).

The dashboard has two sections:
  A · Deal Explorer  — one selector over every *possible* deal; drives charts
                       1-5. Run outcomes appear as a persistent overlay.
  B · Runs           — what *actually* happened: a campaign matrix
                       (model x mode -> close rate) + per-run process
                       trajectories (overview small-multiples + drill-down).

Usage:
    python tools/viz.py \\
        --analysis scenarios/water_rights_beta_squeezed/scenario_analysis.json \\
        --results-dir tests/self_play/results \\
        --title "Water Rights (beta-squeezed)" --output viz_wrbeta.html

Run matching: a result file is included when its embedded ``scenario_analysis``
has the same ``scoring`` and ``batna`` as ``--analysis``. Files containing
"dryrun"/"smoke" or lacking ``scores`` are skipped.
"""

from __future__ import annotations

import argparse
import html as _html
import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FACTION_COLORS = ["#1b4f8a", "#e8531a", "#f5b916", "#2e8b57", "#8e44ad"]
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


# --------------------------------------------------------------------------- #
# deal-space math (mirrors tests/self_play/verify_scenario_optimum.py)
# --------------------------------------------------------------------------- #
def faction_score(analysis: dict[str, Any], faction: str, deal: dict[str, str]) -> float:
    scoring = analysis["scoring"][faction]
    return float(sum(scoring.get(i, {}).get(o, 0) for i, o in deal.items()))


def enumerate_deals(analysis: dict[str, Any]) -> list[dict[str, str]]:
    names = [i["name"] for i in analysis["issues"]]
    outs = [i["outcomes"] for i in analysis["issues"]]
    return [dict(zip(names, combo)) for combo in itertools.product(*outs)]


def build_deals(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    factions = analysis["factions"]
    batna = analysis["batna"]
    raw = []
    for deal in enumerate_deals(analysis):
        sc = {f: faction_score(analysis, f, deal) for f in factions}
        raw.append({"outcomes": deal, "sc": sc, "sum": sum(sc.values())})
    for d in raw:
        d["clears"] = all(d["sc"][f] > batna[f] for f in factions)
        d["pareto"] = not any(
            o is not d
            and all(o["sc"][f] >= d["sc"][f] for f in factions)
            and any(o["sc"][f] > d["sc"][f] for f in factions)
            for o in raw
        )
        d["label"] = " · ".join(_short(o) for o in d["outcomes"].values())
    raw.sort(key=lambda d: d["sum"], reverse=True)
    return raw


def _short(outcome: str) -> str:
    return outcome.split("(")[0].strip()


def md_to_html(text: str) -> str:
    """Light markdown -> HTML for the scenario narrative (headings, bold, bullets)."""
    def esc_bold(s: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _html.escape(s))

    out: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip("\n")
        if not block.strip():
            continue
        first = block.split("\n", 1)[0]
        rest = block.split("\n", 1)[1] if "\n" in block else ""
        if first.startswith("# "):  # title handled separately; keep any trailing prose
            if rest.strip():
                out.append("<p>" + esc_bold(" ".join(l.strip() for l in rest.splitlines())) + "</p>")
            continue
        if first.startswith("#"):
            out.append("<h4>" + esc_bold(re.sub(r"^#+\s*", "", first)) + "</h4>")
            if rest.strip():
                out.append("<p>" + esc_bold(" ".join(l.strip() for l in rest.splitlines())) + "</p>")
            continue
        if first.lstrip().startswith("- "):
            items = [esc_bold(l.strip()[2:]) for l in block.splitlines() if l.strip().startswith("- ")]
            out.append("".join(f'<div class="bullet">\u2022 {it}</div>' for it in items))
            continue
        out.append("<p>" + esc_bold(" ".join(l.strip() for l in block.splitlines())) + "</p>")
    return "\n".join(out)


def find_narrative(analysis_path: Path) -> Path | None:
    """Find the scenario .md whose stem is the longest prefix of the analysis dir name."""
    adir = analysis_path.parent
    dirname = adir.name
    cands: list[tuple[int, Path]] = []
    for base in (adir, adir.parent):
        if base.is_dir():
            for md in base.glob("*.md"):
                if dirname.startswith(md.stem):
                    cands.append((len(md.stem), md))
    cands.sort(reverse=True)
    return cands[0][1] if cands else None


def build_scenario_html(analysis: dict[str, Any], narrative_text: str, fallback_title: str) -> str:
    title = fallback_title
    body = narrative_text or ""
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    for marker in ("## Negotiation Issues", "## The Issues", "## Issues"):
        idx = body.find(marker)
        if idx != -1:
            body = body[:idx]
            break
    # split into intro (before the first '## ' section) and the parties/sections block
    # parse the narrative into intro + '## ' sections, then route by section type:
    #   parties/factions  -> right column
    #   intro, issues, game, everything else -> left column
    lines = [l for l in body.splitlines() if not l.startswith("# ")]
    idxs = [k for k, l in enumerate(lines) if l.startswith("## ")]
    intro_md = "\n".join(lines[: idxs[0]] if idxs else lines)
    sections = []
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        sections.append((lines[start][3:].strip(), "\n".join(lines[start:end])))
    parties_re = re.compile(r"part(y|ies)|partie|agenc|player|faction|team|nation|stakeholder", re.I)
    issue_re = re.compile(r"issue", re.I)
    game_re = re.compile(r"\bgame\b|\brules?\b|how it works|how to play|mechanic|negotiation format", re.I)
    right_secs = [raw for h, raw in sections if parties_re.search(h)]
    left_secs = [raw for h, raw in sections if not parties_re.search(h) and not game_re.search(h)]
    has_issue_section = any(issue_re.search(h) for h, _ in sections)

    left_html = md_to_html(intro_md) if intro_md.strip() else ""
    for raw in left_secs:
        left_html += md_to_html(raw)
    if not has_issue_section:  # only synthesize the issue list when the narrative lacks one
        items = "".join(
            f'<div class="it"><b>{_html.escape(i["name"].replace("_", " "))}</b>'
            + (f' — {_html.escape(i.get("description", ""))}' if i.get("description") else "")
            + "</div>"
            for i in analysis["issues"]
        )
        left_html += f'<div class="issuelist"><b>Issues negotiated</b>{items}</div>'
    left_html += (  # canonical rules block (harness-level, identical across scenarios)
        "<h4>The Game</h4>"
        "<p>Four rounds. Each round every faction posts one public proposal (sealed-bid — no "
        "within-round back-and-forth). After the final round the proposals are scored: a deal is reached "
        "only if all factions agree on the same outcome for <i>every</i> issue; otherwise each faction "
        "falls back to its BATNA.</p>"
    )
    right_html = "".join(md_to_html(raw) for raw in right_secs)
    return (
        f'<h2 style="margin-top:0">{_html.escape(title)}</h2>'
        f'<div class="scen2">'
        f'<div class="scencol">{left_html}</div>'
        f'<div class="scencol">{right_html}</div>'
        f'</div>'
    )


def priority_deal_index(analysis: dict[str, Any], deals: list[dict[str, Any]]) -> int:
    """Index of the 'everyone gets their top issue' deal, or -1 if priorities conflict."""
    factions, issues = analysis["factions"], analysis["issues"]
    pri: dict[str, str] = {}
    for f in factions:
        best_i = best_o = ""
        best_p = -1.0
        for issue, outs in analysis["scoring"][f].items():
            for o, p in outs.items():
                if p > best_p:
                    best_p, best_i, best_o = p, issue, o
        if best_i in pri and pri[best_i] != best_o:
            return -1
        pri[best_i] = best_o
    for issue in issues:
        if issue["name"] not in pri:
            best_o, best_s = None, -1.0
            for o in issue["outcomes"]:
                s = sum(analysis["scoring"][f].get(issue["name"], {}).get(o, 0) for f in factions)
                if s > best_s:
                    best_s, best_o = s, o
            pri[issue["name"]] = best_o
    for i, d in enumerate(deals):
        if d["outcomes"] == pri:
            return i
    return -1


# --------------------------------------------------------------------------- #
# run discovery, model/mode parsing, heuristic position extraction
# --------------------------------------------------------------------------- #
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
    return min(cnt, key=lambda k: cnt[k])  # minority provider = the generator override


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


# --------------------------------------------------------------------------- #
# assemble + render
# --------------------------------------------------------------------------- #
def build_data(analysis: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    factions = analysis["factions"]
    deals = build_deals(analysis)
    by_outcomes = {json.dumps(d["outcomes"], sort_keys=True): i for i, d in enumerate(deals)}
    for r in runs:
        r["dealIdx"] = by_outcomes.get(json.dumps(r["agreed_outcomes"], sort_keys=True), -1) if r["agreed_outcomes"] else -1
    maxf = {
        f: sum(max(analysis["scoring"][f].get(i["name"], {}).values(), default=0) for i in analysis["issues"])
        for f in factions
    }
    optimum = next((i for i, d in enumerate(deals) if d["clears"]), 0)
    return {
        "factions": factions,
        "colors": {f: FACTION_COLORS[i % len(FACTION_COLORS)] for i, f in enumerate(factions)},
        "issues": analysis["issues"],
        "scoring": analysis["scoring"],
        "batna": analysis["batna"],
        "maxf": maxf,
        "sumBatna": sum(analysis["batna"].values()),
        "maxParetoSum": max((d["sum"] for d in deals if d["clears"]), default=0),
        "deals": deals,
        "optimumIdx": optimum,
        "priorityIdx": priority_deal_index(analysis, deals),
        "bottleneck": detect_bottleneck(runs, analysis),
        "runs": runs,
    }


def render_html(data: dict[str, Any], title: str, extraction_note: str, scenario_html: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = (
        _BODY.replace("{{TITLE}}", title)
        .replace("{{GENERATED}}", generated)
        .replace("{{NRUNS}}", str(len(data["runs"])))
        .replace("{{NFAC}}", str(len(data["factions"])))
        .replace("{{NISS}}", str(len(data["issues"])))
        .replace("{{BOTTLENECK}}", str(data["bottleneck"]).replace("_", " "))
        .replace("{{SCENARIO}}", scenario_html)
        .replace("{{EXTRACTION}}", extraction_note)
    )
    return _HEAD.replace("{{TITLE}}", title) + body + "<script>\nconst DATA = " + json.dumps(data) + ";\n" + _JS + "\n</script>\n</body>\n</html>\n"


_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diplomat — {{TITLE}}</title>
<style>
  :root { --ink:#1c1c1c; --muted:#6a6a6a; --line:#e3e3e3; --hl:#dfeafb; }
  * { box-sizing:border-box; }
  body { font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; margin:0; background:#fafafa; color:var(--ink); }
  .wrap { max-width:1180px; margin:0 auto; padding:2.2em 1.4em 4em; }
  h1 { margin:0 0 .1em; font-size:1.65em; letter-spacing:-.01em; }
  .sub { color:var(--muted); margin:0 0 1.4em; }
  h2 { font-size:1.12em; margin:0 0 .15em; }
  h2.section { font-size:1.3em; margin:1.8em 0 .2em; padding-top:1em; border-top:2px solid #e7e7e7; }
  .card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:1.1em 1.2em 1.3em; box-shadow:0 1px 2px rgba(0,0,0,.04); margin-bottom:1.1em; }
  .cap { color:var(--muted); font-size:.9em; margin:.2em 0 .9em; max-width:78ch; }
  .cap b { color:var(--ink); }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:1.1em; align-items:start; }
  @media (max-width:860px){ .grid2 { grid-template-columns:1fr; } }
  .grid-uneven { display:grid; grid-template-columns:1fr 1fr; gap:1.1em; align-items:start; }
  @media (max-width:860px){ .grid-uneven { grid-template-columns:1fr; } }
  .cols2 { display:grid; grid-template-columns:1fr 1fr; gap:1.1em; align-items:start; }
  @media (max-width:860px){ .cols2 { grid-template-columns:1fr; } }
  .colstack { display:flex; flex-direction:column; gap:1.1em; }
  .scen2 { display:grid; grid-template-columns:1fr 1fr; gap:1.8em; align-items:start; }
  @media (max-width:860px){ .scen2 { grid-template-columns:1fr; } }
  .scencol p { margin:.2em 0 .6em; color:#444; font-size:.9em; }
  .scencol h4 { margin:.5em 0 .2em; font-size:.9em; color:#333; }
  .scencol .bullet { font-size:.9em; color:#555; margin:.1em 0 .1em .3em; }
  .scencol .issuelist { margin-top:.8em; font-size:.9em; }
  .scencol .issuelist .it { margin:.25em 0; color:#555; }
  .selbar { display:flex; align-items:center; gap:.7em; flex-wrap:wrap; background:#eef3fb; border:1px solid #cdddf2;
            border-radius:9px; padding:.7em 1em; margin-bottom:1.1em; }
  .selbar b { font-weight:600; }
  .selbar select { font:inherit; padding:5px 9px; border:1px solid #9bb6dc; border-radius:6px; max-width:460px; }
  .selbar button { font:inherit; font-size:.86em; padding:4px 10px; border:1px solid #9bb6dc; background:#fff; border-radius:6px; cursor:pointer; }
  .selbar button:hover { background:#dce8fa; }
  .selbar .meta { color:#3a567e; font-size:.9em; }
  .legend { display:flex; flex-wrap:wrap; gap:.3em 1.1em; margin:.1em 0 .6em; font-size:.9em; }
  .chip { display:inline-flex; align-items:center; gap:.4em; }
  .sw { width:13px; height:13px; border-radius:3px; display:inline-block; }
  table.heat { border-collapse:collapse; font-variant-numeric:tabular-nums; width:100%; }
  table.heat th,table.heat td { padding:3px 7px; border-bottom:1px solid #f0f0f0; text-align:center; white-space:nowrap; }
  table.heat th { background:#eaf0fa; font-weight:600; position:sticky; top:0; }
  table.heat td.deal { text-align:left; color:var(--muted); font-size:.86em; }
  table.heat tr.sel td { border-top:2px solid #111; border-bottom:2px solid #111; }
  table.heat tr.sel td:first-child { border-left:2px solid #111; }
  table.heat tr.sel td:last-child { border-right:2px solid #111; }
  table.heat tr.batnarow td { background:#f3f3f3; font-style:italic; }
  table.heat tr[data-deal]{ cursor:pointer; }
  table.matrix { border-collapse:collapse; font-variant-numeric:tabular-nums; }
  table.matrix th,table.matrix td { padding:5px 12px; border-bottom:1px solid #eee; text-align:left; }
  table.matrix th { background:#f6f6f6; font-weight:600; }
  table.matrix td.num { text-align:right; }
  .good { color:#1a7f37; font-weight:600; } .bad { color:#b03030; font-weight:600; }
  .scrollable { max-height:430px; overflow:auto; border:1px solid var(--line); border-radius:8px; }
  .mark { font-weight:700; } .mark.par { color:#1a5fb4; } .mark.cl { color:#1a7f37; }
  .pill { display:inline-block; font-size:.72em; font-weight:700; text-transform:uppercase; letter-spacing:.04em; padding:1px 7px; border-radius:20px; }
  .pill.deal { background:#e6f4ea; color:#1a7f37; } .pill.nodeal { background:#fdecea; color:#b03030; }
  .badge { display:inline-block; font-size:.72em; font-weight:600; text-transform:uppercase; letter-spacing:.04em; padding:2px 8px; border-radius:20px; margin-left:.5em; }
  .badge.real { background:#e6f4ea; color:#1a7f37; } .badge.heur { background:#fff4e0; color:#b5710a; }
  .intro2 { display:grid; grid-template-columns:minmax(280px,330px) 1fr; gap:1.6em; align-items:start; }
  @media (max-width:860px){ .intro2 { grid-template-columns:1fr; } }
  .introtext p { margin:.2em 0 .7em; color:#444; font-size:.93em; }
  .introtext h2 { margin-bottom:.4em; }
  .introtext h4 { margin:.7em 0 .15em; font-size:.95em; color:#333; }
  .introtext .bullet { font-size:.86em; color:#555; margin:.1em 0 .1em .3em; }
  .issuelist { margin-top:.9em; font-size:.88em; }
  .issuelist .it { margin:.25em 0; color:#555; }
  .issuelist .it b { color:#333; }
  .chartcap { color:#6a6a6a; font-size:.88em; margin:.2em 0 .5em; max-width:70ch; }
  .dealtotal { font-size:.92em; margin:.2em 0 .5em; color:#234; background:#f4f8ff; border:1px solid #dbe7f8; border-radius:6px; padding:.4em .7em; }
  .multi { display:flex; flex-wrap:wrap; gap:.9em; }
  .multi .cell { border:1px solid #eee; border-radius:8px; padding:.4em .5em; }
  .multi .ct { font-size:.82em; font-weight:600; color:#333; margin:.1em .2em .2em; }
  .footer { color:#9a9a9a; font-size:.84em; margin-top:2em; }
  svg text { font-family:inherit; }
</style>
</head>
<body>
"""

_BODY = """<div class="wrap">
  <h1>Diplomat — {{TITLE}}</h1>
  <p class="sub">Deal space + where each self-play run landed · generated {{GENERATED}} · {{NRUNS}} run(s)</p>

  <div class="card">
    {{SCENARIO}}
  </div>

  <h2 class="section">A · Deal explorer</h2>

  <div class="card">
    <h2>Deal space — click a row to inspect</h2>
    <p class="cap">Every deal sorted by surplus; cells coloured by Δ-above-BATNA (green good / red below floor).
      <span class="mark par">◆</span> Pareto · <span class="mark cl">✓</span> clears all BATNAs. The <b>BATNA floor</b>
      row (Δ 0/0/0) marks the waterline — rows above it carry net-positive surplus. <b>Click any row</b> to inspect that deal.</p>
    <div class="scrollable"><div id="heat"></div></div>
  </div>

  <div class="cols2">
    <div class="colstack">
      <div class="card">
        <h2>Per-issue payoff decomposition</h2>
        <p class="chartcap">One stacked bar per (issue, outcome); height = points that outcome gives, summed over
          factions. A ★ marks each faction's preferred outcome; stars in different columns = a <b>contested</b>
          issue (logrolling lives there). The selected deal's chosen column is tinted.</p>
        <div id="legend" class="legend"></div>
        <div id="dealTotal" class="dealtotal"></div>
        <div id="grid" style="overflow-x:auto;margin-top:.2em"></div>
      </div>
      <div class="card">
        <h2>Per-faction outcome of the selected deal</h2>
        <p class="cap">BATNA floor (dashed), achieved, max ceiling (ghost). Gap above the floor = captured surplus.</p>
        <div id="bars"></div>
      </div>
    </div>
    <div class="colstack">
      <div class="card">
        <h2>Parallel coordinates</h2>
        <p class="cap">One axis per faction; each deal a line (blue = Pareto, grey = dominated). Dashed = BATNA. Selected deal in black.</p>
        <div id="parallel"></div>
      </div>
      <div class="card">
        <h2>Surplus-share ternary</h2>
        <p class="cap">Each point = a BATNA-clearing <b>deal</b>; size ∝ total surplus; blue = Pareto. The selected deal is outlined (if it clears BATNA). A corner = that faction takes most of the surplus.</p>
        <div id="ternary"></div>
      </div>
    </div>
  </div>

  <div class="footer">Self-contained · no external libraries · deal space computed from the scoring tables; overlays read from result JSONs.</div>
</div>
"""

_JS = r"""
const SVGNS="http://www.w3.org/2000/svg";
const F=DATA.factions, COL=DATA.colors, ISS=DATA.issues, SC=DATA.scoring, BA=DATA.batna, MX=DATA.maxf;
const DEALS=DATA.deals, RUNS=DATA.runs, SUMBA=DATA.sumBatna, MAXP=DATA.maxParetoSum, BOTTLE=DATA.bottleneck;
let selDeal=DATA.optimumIdx;                              // index into DEALS, or -1 for BATNA floor
let selRun=Math.max(0, RUNS.findIndex(r=>r.deal_reached)); // index into RUNS (section B)

function el(t,a,x){const e=document.createElementNS(SVGNS,t);for(const k in a)e.setAttribute(k,a[k]);if(x!=null)e.textContent=x;return e;}
function svg(w,h){return el("svg",{viewBox:`0 0 ${w} ${h}`,width:"100%",style:`max-width:${w}px`});}
function dcol(d){const m=Math.max(6,(MAXP-SUMBA)/2),t=Math.max(-m,Math.min(m,d))/m;
  if(t>=0){const a=t;return `rgb(${Math.round(255-150*a)},${Math.round(255-35*a)},${Math.round(255-150*a)})`;}
  const a=-t;return `rgb(${Math.round(255-15*a)},${Math.round(255-150*a)},${Math.round(255-150*a)})`;}
function host(id){const h=document.getElementById(id);h.innerHTML="";return h;}
function dealScores(){return selDeal<0?Object.assign({},BA):DEALS[selDeal].sc;}

/* legend */
(function(){const L=document.getElementById("legend");
  F.forEach(f=>{const c=document.createElement("span");c.className="chip";c.innerHTML=`<span class="sw" style="background:${COL[f]}"></span>${f}`;L.appendChild(c);});})();

/* per-issue grid with selected-deal column tint (vertical issue labels) */
function renderGrid(){
  const nOut=ISS[0].outcomes.length,cellW=160,cellH=150,gut=56,top=30,barMax=104;
  const maxv=Math.max(...ISS.flatMap(i=>i.outcomes.map(o=>F.reduce((a,f)=>a+(SC[f][i.name][o]||0),0))));
  const w=gut+cellW*nOut+10,h=top+(cellH+8)*ISS.length;
  const s=svg(w,h);s.setAttribute("style","width:100%;height:auto");
  const selOut=selDeal>=0?DEALS[selDeal].outcomes:null;
  ["A","B","C","D","E"].slice(0,nOut).forEach((lab,o)=>s.appendChild(el("text",{x:gut+cellW*o+cellW/2,y:18,"text-anchor":"middle","font-weight":600,"font-size":15,fill:"#444"},lab)));
  ISS.forEach((iss,r)=>{
    const y0=top+r*(cellH+8),cy=y0+cellH/2;
    const prefs=F.map(f=>{const v=iss.outcomes.map(o=>SC[f][iss.name][o]||0);return v.indexOf(Math.max(...v));});
    const contested=!(prefs.every(p=>p===prefs[0]));
    s.appendChild(el("text",{x:18,y:cy,transform:`rotate(-90 18 ${cy})`,"text-anchor":"middle","font-weight":600,"font-size":13,fill:"#333"},iss.name.replace(/_/g," ")));
    s.appendChild(el("text",{x:36,y:cy,transform:`rotate(-90 36 ${cy})`,"text-anchor":"middle","font-size":12,fill:contested?"#b5710a":"#1a7f37"},contested?"contested":"aligned"));
    iss.outcomes.forEach((o,oi)=>{
      const colX=gut+oi*cellW;
      if(selOut && selOut[iss.name]===o)s.appendChild(el("rect",{x:colX+5,y:y0+2,width:cellW-10,height:cellH-2,rx:7,fill:"var(--hl)"}));
      const bw2=cellW-58,x0=colX+(cellW-bw2)/2,base=y0+cellH-22;
      s.appendChild(el("line",{x1:x0-4,y1:base,x2:x0+bw2+4,y2:base,stroke:"#ddd"}));
      let acc=0;
      F.forEach(f=>{const v=SC[f][iss.name][o]||0,hh=v/maxv*barMax,yy=base-acc-hh;
        s.appendChild(el("rect",{x:x0,y:yy,width:bw2,height:hh,fill:COL[f],opacity:.92}));
        if(hh>18)s.appendChild(el("text",{x:x0+bw2/2,y:yy+hh/2+4,"text-anchor":"middle","font-size":13,fill:"#fff","font-weight":600},v));
        acc+=hh;});
      const sum=F.reduce((a,f)=>a+(SC[f][iss.name][o]||0),0);
      s.appendChild(el("text",{x:x0+bw2/2,y:base-acc-5,"text-anchor":"middle","font-size":13,fill:"#666","font-weight":600},"Σ"+sum));
      const star=F.filter((f,fi)=>prefs[fi]===oi);
      star.forEach((f,si)=>s.appendChild(el("text",{x:x0+bw2/2+(si-(star.length-1)/2)*14,y:base+15,"text-anchor":"middle","font-size":15,fill:COL[f]},"★")));
    });
  });
  host("grid").appendChild(s);
  updateDealTotal();
}
function updateDealTotal(){
  const e=document.getElementById("dealTotal");if(!e)return;
  if(selDeal<0){e.innerHTML=`<b>BATNA floor</b> — no deal · every faction at its no-deal value · Σ${SUMBA}`;return;}
  const d=DEALS[selDeal],sp=d.sum-SUMBA;
  e.innerHTML=`<b>Selected deal:</b> ${F.map(f=>`${f} ${d.sc[f]}`).join(" · ")} &nbsp;→&nbsp; <b>Σ${d.sum}</b> (surplus ${sp>=0?"+"+sp:sp})`;
}

/* 2 · per-faction bars for the selected deal */
function renderBars(){
  const sc=dealScores(),w=560,h=380,padB=50,padT=20,base=h-padB,top=padT,colW=170,barW=70,padL=20,scale=Math.max(...F.map(f=>MX[f]))+2;
  const s=svg(w,h);s.setAttribute("style","width:100%;height:auto");
  F.forEach((f,fi)=>{const cx=padL+fi*colW+colW/2,v=sc[f],ba=BA[f],mx=MX[f];
    const yM=base-mx/scale*(base-top),yS=base-v/scale*(base-top),yB=base-ba/scale*(base-top);
    s.appendChild(el("rect",{x:cx-barW/2,y:yM,width:barW,height:base-yM,fill:COL[f],opacity:.13}));
    s.appendChild(el("rect",{x:cx-barW/2,y:yS,width:barW,height:base-yS,fill:COL[f],opacity:.9}));
    s.appendChild(el("line",{x1:cx-barW/2-9,y1:yB,x2:cx+barW/2+9,y2:yB,stroke:"#c0392b","stroke-width":2,"stroke-dasharray":"5 3"}));
    s.appendChild(el("text",{x:cx+barW/2+11,y:yB+4,"font-size":12,fill:"#c0392b"},"BATNA "+ba));
    s.appendChild(el("text",{x:cx,y:yS-6,"text-anchor":"middle","font-weight":700,"font-size":16,fill:"#222"},v));
    s.appendChild(el("text",{x:cx,y:yM-5,"text-anchor":"middle","font-size":12,fill:"#999"},"max "+mx));
    s.appendChild(el("text",{x:cx,y:base+16,"text-anchor":"middle","font-weight":600,"font-size":14,fill:COL[f]},f));
    const dl=v-ba;s.appendChild(el("text",{x:cx,y:base+31,"text-anchor":"middle","font-size":12,fill:dl>0?"#1a7f37":(dl<0?"#c0392b":"#999")},(dl>=0?"+":"")+dl+" vs BATNA"));});
  host("bars").appendChild(s);
}

/* deal-space table = the selector (BATNA floor row marks the waterline) */
function renderHeat(){
  const rows=DEALS.map((d,i)=>({type:"deal",d,i,sum:d.sum})); rows.push({type:"batna",sum:SUMBA}); rows.sort((a,b)=>b.sum-a.sum);
  let html=`<table class="heat"><thead><tr><th style="text-align:left">Deal</th>`+F.map(f=>`<th>${f} Δ</th>`).join("")+`<th>Σ surplus</th><th></th></tr></thead><tbody>`;
  rows.forEach(row=>{
    if(row.type==="batna"){
      html+=`<tr class="batnarow${selDeal<0?" sel":""}" data-deal="-1"><td class="deal"><b>BATNA floor — no deal</b></td>${F.map(()=>"<td>0</td>").join("")}<td>0</td><td></td></tr>`;
      return;
    }
    const d=row.d,i=row.i,surplus=d.sum-SUMBA,sw=Math.max(0,surplus)/Math.max(1,MAXP-SUMBA);
    const cells=F.map(f=>{const dl=d.sc[f]-BA[f];return `<td style="background:${dcol(dl)}">${dl>=0?"+":""}${dl}</td>`;}).join("");
    const bar=`<div style="background:#e7eefb;border-radius:3px;height:11px;width:74px;display:inline-block;vertical-align:middle"><div style="background:#5a7fb8;height:11px;border-radius:3px;width:${Math.round(sw*74)}px"></div></div>`;
    const marks=`${d.pareto?'<span class="mark par">◆</span>':''}${d.clears?'<span class="mark cl">✓</span>':''}`;
    html+=`<tr class="${i===selDeal?"sel":""}" data-deal="${i}"><td class="deal">${d.label}</td>${cells}<td>${surplus>=0?"+"+surplus:surplus} ${bar}</td><td>${marks}</td></tr>`;
  });
  html+=`</tbody></table>`;
  const h=host("heat");h.innerHTML=html;
  h.querySelectorAll("tr[data-deal]").forEach(tr=>tr.onclick=()=>setDeal(+tr.dataset.deal));
}

/* parallel coordinates (enlarged) */
function renderParallel(){
  const w=640,h=560,padT=42,padB=54,padL=58,padR=58,base=h-padB;
  const ax=F.map((f,i)=>padL+i*(w-padL-padR)/(F.length-1));
  const s=svg(w,h);s.setAttribute("style","width:100%;height:auto");
  F.forEach((f,fi)=>{const x=ax[fi];
    s.appendChild(el("line",{x1:x,y1:padT,x2:x,y2:base,stroke:"#ccc"}));
    s.appendChild(el("text",{x,y:base+24,"text-anchor":"middle","font-weight":600,"font-size":17,fill:COL[f]},f));
    s.appendChild(el("text",{x,y:padT-12,"text-anchor":"middle","font-size":14,fill:"#999"},"max "+MX[f]));
    const yB=base-BA[f]/MX[f]*(base-padT);
    s.appendChild(el("line",{x1:x-14,y1:yB,x2:x+14,y2:yB,stroke:"#c0392b","stroke-dasharray":"4 2","stroke-width":1.5}));
    s.appendChild(el("text",{x:x+18,y:yB+4,"font-size":13,fill:"#c0392b"},"BATNA "+BA[f]));});
  const yOf=(f,v)=>base-v/MX[f]*(base-padT);
  DEALS.map((d,i)=>i).sort((a,b)=>(DEALS[a].pareto?1:0)-(DEALS[b].pareto?1:0)).forEach(i=>{const d=DEALS[i];
    s.appendChild(el("polyline",{points:F.map((f,fi)=>`${ax[fi]},${yOf(f,d.sc[f])}`).join(" "),fill:"none",stroke:d.pareto?"#1a5fb4":"#d3d3d3","stroke-width":d.pareto?1.6:1,opacity:d.pareto?.8:.4}));});
  if(selDeal>=0){const d=DEALS[selDeal];s.appendChild(el("polyline",{points:F.map((f,fi)=>`${ax[fi]},${yOf(f,d.sc[f])}`).join(" "),fill:"none",stroke:"#000","stroke-width":3.4}));}
  else{s.appendChild(el("polyline",{points:F.map((f,fi)=>`${ax[fi]},${yOf(f,BA[f])}`).join(" "),fill:"none",stroke:"#000","stroke-width":2.6,"stroke-dasharray":"6 3"}));}
  host("parallel").appendChild(s);
}

/* 5 · ternary: persistent run points + selected-deal highlight */
function renderTernary(){
  const w=460,h=370,cx=w/2,m=56;
  if(F.length!==3){host("ternary").innerHTML='<p style="color:#999">Ternary shown for 3-faction scenarios only.</p>';return;}
  const V=[{x:cx,y:m},{x:m,y:h-m-22},{x:w-m,y:h-m-22}],s=svg(w,h);s.setAttribute("style","width:100%;height:auto");
  s.appendChild(el("polygon",{points:V.map(p=>`${p.x},${p.y}`).join(" "),fill:"#f7f9fc",stroke:"#ccc"}));
  s.appendChild(el("text",{x:V[0].x,y:V[0].y-9,"text-anchor":"middle","font-weight":600,"font-size":14,fill:COL[F[0]]},F[0]+" →"));
  s.appendChild(el("text",{x:V[1].x-2,y:V[1].y+18,"text-anchor":"middle","font-weight":600,"font-size":14,fill:COL[F[1]]},F[1]));
  s.appendChild(el("text",{x:V[2].x+2,y:V[2].y+18,"text-anchor":"middle","font-weight":600,"font-size":14,fill:COL[F[2]]},F[2]));
  const pos=(a,b,c)=>({x:a*V[0].x+b*V[1].x+c*V[2].x,y:a*V[0].y+b*V[1].y+c*V[2].y});
  const share=sc=>{const su=F.map(f=>Math.max(0,sc[f]-BA[f])),t=su[0]+su[1]+su[2];return t>0?pos(su[0]/t,su[1]/t,su[2]/t):null;};
  DEALS.forEach((d,i)=>{if(!d.clears)return;const p=share(d.sc);if(!p)return;
    const rad=4+(d.sum-SUMBA)/Math.max(1,MAXP-SUMBA)*9;
    s.appendChild(el("circle",{cx:p.x,cy:p.y,r:rad,fill:d.pareto?"#1a5fb4":"#9aa7b5",opacity:.55,stroke:"#fff","stroke-width":1}));});
  if(selDeal>=0&&DEALS[selDeal].clears){const p=share(DEALS[selDeal].sc);if(p)s.appendChild(el("circle",{cx:p.x,cy:p.y,r:8,fill:"#ffd23f",opacity:1,stroke:"#000","stroke-width":2.5}));}
  s.appendChild(el("text",{x:cx,y:h-8,"text-anchor":"middle","font-size":12,fill:"#999"},"each dot = a BATNA-clearing deal · size ∝ surplus · outlined = selected"));
  host("ternary").appendChild(s);
}

/* wiring */
function setDeal(i){selDeal=i;renderGrid();renderBars();renderHeat();renderParallel();renderTernary();}
(function init(){
  renderGrid();renderBars();renderHeat();renderParallel();renderTernary();
})();
"""


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
    note = (
        f"Final-round extraction matched the recorded deal in {matched}/{checked} closing run(s) — earlier rounds are approximate."
        if checked
        else "Positions are heuristic substring matches over round messages — approximate."
    )
    nar_path = args.narrative or find_narrative(args.analysis)
    narrative_text = nar_path.read_text(encoding="utf-8") if nar_path and nar_path.exists() else ""
    data = build_data(analysis, runs)
    scenario_html = build_scenario_html(analysis, narrative_text, args.title)
    args.output.write_text(render_html(data, args.title, note, scenario_html), encoding="utf-8")
    print(f"Wrote {args.output} · {len(runs)} run(s) · {len(data['deals'])} deals · extraction {matched}/{checked} · narrative {'yes' if narrative_text else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
