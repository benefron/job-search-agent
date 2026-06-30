"""
Interactive CLI to curate labs.json: review labs one by one and mark them
as keep / discard / already-known, and add notes or labels.

Usage:
    python scripts/labs_curate.py [--location Amsterdam] [--topic spiking]

Controls:
    k / Enter   → keep (relevant)
    d           → discard (irrelevant — writes to labs_discarded.json)
    n           → add a note then keep
    s           → skip (decide later)
    o           → open OpenAlex profile in browser
    g           → open Google search in browser
    q           → quit and save progress
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
LABS_JSON = DATA_DIR / "labs.json"
CURATION_JSON = DATA_DIR / "labs_curation.json"
DISCARDED_JSON = DATA_DIR / "labs_discarded.json"


def load_labs() -> list[dict]:
    data = json.loads(LABS_JSON.read_text())
    return data.get("labs", []) if isinstance(data, dict) else data


def load_curation() -> dict:
    if CURATION_JSON.exists():
        return json.loads(CURATION_JSON.read_text())
    return {}


def save_curation(curation: dict) -> None:
    CURATION_JSON.write_text(json.dumps(curation, indent=2, ensure_ascii=False))


def load_discarded() -> list:
    if DISCARDED_JSON.exists():
        return json.loads(DISCARDED_JSON.read_text())
    return []


def save_discarded(discarded: list) -> None:
    DISCARDED_JSON.write_text(json.dumps(discarded, indent=2, ensure_ascii=False))


def print_lab(lab: dict, idx: int, total: int, status: str | None) -> None:
    bar = f"[{idx}/{total}]"
    prev = f" ({status})" if status else ""
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"{bar}{prev}  {lab.get('name', '?')}")
    print(f"  Institution : {lab.get('lab', '?')}")
    print(f"  Location    : {lab.get('location', '?')}")
    print(f"  Topic       : {lab.get('topic', '?')}")
    print(f"  Papers      : {lab.get('works_count', '?')}")
    if lab.get("orcid_url"):
        print(f"  ORCID       : {lab['orcid_url']}")
    print(f"  OpenAlex    : {lab.get('url', '?')}")
    if lab.get("website"):
        print(f"  Website     : {lab['website']}")
    if lab.get("notes"):
        print(f"  Notes       : {lab['notes']}")
    print(f"{sep}")
    print("  [k] keep  [d] discard  [n] note+keep  [s] skip  [o] OpenAlex  [g] Google  [q] quit")


def run(args: argparse.Namespace) -> None:
    labs = load_labs()
    curation = load_curation()
    discarded_list = load_discarded()
    discarded_ids = {d["id"] for d in discarded_list}

    # Filter by CLI args
    if args.location:
        labs = [l for l in labs if args.location.lower() in l.get("location", "").lower()]
    if args.topic:
        labs = [l for l in labs if args.topic.lower() in l.get("topic", "").lower()]
    # Put un-decided labs first
    pending = [l for l in labs if l["id"] not in curation and l["id"] not in discarded_ids]
    reviewed = [l for l in labs if l["id"] in curation or l["id"] in discarded_ids]
    ordered = pending + reviewed

    print(f"\nLabs to review: {len(pending)} pending, {len(reviewed)} already reviewed")
    print(f"Total shown: {len(ordered)}")

    changes = 0
    for idx, lab in enumerate(ordered, 1):
        lab_id = lab["id"]
        current_status = "discarded" if lab_id in discarded_ids else curation.get(lab_id, {}).get("status")
        print_lab(lab, idx, len(ordered), current_status)

        while True:
            try:
                raw = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                raw = "q"

            if raw in ("", "k"):
                curation[lab_id] = {**curation.get(lab_id, {}), "status": "keep", "name": lab["name"], "lab": lab["lab"]}
                # remove from discarded if re-reviewing
                discarded_list = [d for d in discarded_list if d["id"] != lab_id]
                discarded_ids.discard(lab_id)
                changes += 1
                break
            elif raw == "d":
                discarded_list.append({**lab, "discard_reason": ""})
                discarded_ids.add(lab_id)
                curation.pop(lab_id, None)
                changes += 1
                break
            elif raw == "n":
                note = input("  Note: ").strip()
                curation[lab_id] = {**curation.get(lab_id, {}), "status": "keep", "name": lab["name"], "lab": lab["lab"], "notes": note}
                discarded_list = [d for d in discarded_list if d["id"] != lab_id]
                discarded_ids.discard(lab_id)
                changes += 1
                break
            elif raw == "s":
                break
            elif raw == "o":
                webbrowser.open(lab.get("url", ""))
            elif raw == "g":
                webbrowser.open(lab.get("google_url", f"https://www.google.com/search?q={lab.get('name','')} {lab.get('lab','')}"))
            elif raw == "q":
                save_curation(curation)
                save_discarded(discarded_list)
                print(f"\nSaved. {changes} changes made.")
                return
            else:
                print("  Unknown command. k/d/n/s/o/g/q")

    save_curation(curation)
    save_discarded(discarded_list)

    kept = sum(1 for v in curation.values() if v.get("status") == "keep")
    print(f"\nDone! Kept: {kept}  Discarded: {len(discarded_list)}  Changes: {changes}")
    print(f"Curation saved to {CURATION_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate labs.json interactively")
    parser.add_argument("--location", help="Filter by location (e.g. Amsterdam)")
    parser.add_argument("--topic", help="Filter by topic keyword")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
