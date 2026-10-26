#!/usr/bin/env python3
"""
Tokenverbruik per zoekactie van de wekelijkse brief (aangeroepen door run_weekbrief.ps1).

Gebruik:
  python scripts/tokens_weekbrief.py --stream LOG.jsonl --json LOG.json [--csv logs/tokens.csv] [--run-datum JJJJ-MM-DD]

Leest de stream-json-uitvoer van `claude -p`, schrijft het eindresultaat naar LOG.json
(zelfde vorm als --output-format json) en voegt aan de CSV toe:
  - één rij per WebSearch-, WebFetch- of sub-agentaanroep;
  - één totaalrij per model, met de kosten (tool = "totaal").

Wat de kolommen betekenen:
  bericht_*            verbruik van het modelbericht waarin de aanroep werd gedaan. Doet één
                       bericht meerdere aanroepen, dan staat bij elk hetzelfde getal (zie gedeeld_door).
                       bericht_uitvoer is de tussenstand uit de stream en kan te laag zijn; de
                       totaalrijen per model zijn exact.
  resultaat_tokens     schatting (tekens / 4) van wat het zoekresultaat aan de context toevoegt;
                       dat deel wordt bij elke volgende stap opnieuw (uit de cache) gelezen.
  subagent_tokens      bij een sub-agent (bijv. web-fetch): diens totale verbruik.
WebSearch draait intern op een apart model; dat verbruik staat alleen in de totaalrij van dat model.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["run_datum", "nr", "tool", "invoer", "agent", "bericht_invoer", "bericht_cache_schrijven",
           "bericht_cache_lezen", "bericht_uitvoer", "gedeeld_door", "resultaat_tekens", "resultaat_tokens",
           "subagent_tokens", "duur_s", "fout", "zoekopdrachten", "kosten_usd"]
TRACKED = {"WebSearch", "WebFetch", "Agent", "Task"}

def text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(text_len(b.get("text", "") if isinstance(b, dict) else b) for b in content)
    return len(json.dumps(content, ensure_ascii=False)) if content else 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", required=True, type=Path)
    ap.add_argument("--json", required=True, type=Path)
    ap.add_argument("--csv", type=Path, default=ROOT / "logs" / "tokens.csv")
    ap.add_argument("--run-datum", default=dt.date.today().isoformat())
    args = ap.parse_args()

    events = []
    for line in args.stream.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    usage, calls_per_msg, calls, results, sub_usage = {}, {}, [], {}, {}
    for e in events:
        t = e.get("type")
        if t == "assistant":
            m = e.get("message", {})
            mid = m.get("id")
            usage[mid] = m.get("usage") or {}
            for b in m.get("content", []):
                if b.get("type") == "tool_use" and b.get("name") in TRACKED:
                    if b["id"] in {c["id"] for c in calls}:
                        continue
                    calls_per_msg[mid] = calls_per_msg.get(mid, 0) + 1
                    inp = b.get("input") or {}
                    calls.append({"id": b["id"], "msg": mid, "tool": b["name"],
                                  "invoer": inp.get("query") or inp.get("url") or inp.get("description") or "",
                                  "agent": "sub" if e.get("parent_tool_use_id") else "hoofd",
                                  "subtype": inp.get("subagent_type", "")})
        elif t == "user":
            content = e.get("message", {}).get("content")
            extra = e.get("tool_use_result") if isinstance(e.get("tool_use_result"), dict) else {}
            for b in content if isinstance(content, list) else []:
                if b.get("type") == "tool_result":
                    results[b["tool_use_id"]] = {"len": text_len(b.get("content")), "fout": bool(b.get("is_error")), "extra": extra}
        elif t == "system" and e.get("subtype") == "task_progress" and e.get("tool_use_id"):
            sub_usage[e["tool_use_id"]] = (e.get("usage") or {}).get("total_tokens", "")

    final = next((e for e in reversed(events) if e.get("type") == "result"), None)
    args.json.write_text(json.dumps(final if final else {"fout": "geen resultaat in de stream"}, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for n, c in enumerate(calls, 1):
        u, r = usage.get(c["msg"], {}), results.get(c["id"], {})
        extra = r.get("extra") or {}
        dur = extra.get("durationSeconds") or (extra.get("totalDurationMs", 0) / 1000 if extra.get("totalDurationMs") else "")
        rows.append({
            "run_datum": args.run_datum, "nr": n,
            "tool": c["tool"] + (f":{c['subtype']}" if c["subtype"] else ""),
            "invoer": c["invoer"][:300], "agent": c["agent"],
            "bericht_invoer": u.get("input_tokens", ""), "bericht_cache_schrijven": u.get("cache_creation_input_tokens", ""),
            "bericht_cache_lezen": u.get("cache_read_input_tokens", ""), "bericht_uitvoer": u.get("output_tokens", ""),
            "gedeeld_door": calls_per_msg.get(c["msg"], 1),
            "resultaat_tekens": r.get("len", ""), "resultaat_tokens": round(r["len"] / 4) if r.get("len") else "",
            "subagent_tokens": extra.get("totalTokens") or sub_usage.get(c["id"], ""),
            "duur_s": round(dur, 1) if dur != "" else "", "fout": "ja" if r.get("fout") else ("" if r else "geen resultaat"),
            "zoekopdrachten": extra.get("searchCount", ""), "kosten_usd": "",
        })
    for model, mu in ((final or {}).get("modelUsage") or {}).items():
        rows.append({"run_datum": args.run_datum, "nr": "", "tool": "totaal", "invoer": model, "agent": "",
                     "bericht_invoer": mu.get("inputTokens", ""), "bericht_cache_schrijven": mu.get("cacheCreationInputTokens", ""),
                     "bericht_cache_lezen": mu.get("cacheReadInputTokens", ""), "bericht_uitvoer": mu.get("outputTokens", ""),
                     "zoekopdrachten": mu.get("webSearchRequests", ""), "kosten_usd": round(mu.get("costUSD", 0), 4)})

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    new = not args.csv.exists()
    with args.csv.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)

    searches = [r for r in rows if r["tool"] != "totaal"]
    cost = (final or {}).get("total_cost_usd")
    print(f"Tokens: {len(searches)} zoek-/ophaalacties gelogd in {args.csv.name}"
          + (f"; totale kosten ${cost:.2f}" if isinstance(cost, (int, float)) else "; geen eindresultaat gevonden"))
    return 0 if final else 1

if __name__ == "__main__":
    sys.exit(main())
