#!/usr/bin/env python3
"""One-shot: convert the Slack user cache CSV into seed/people.json, the people directory seed.py loads.

    python3 seed/csv_to_people.py [path-to-csv]

The CSV has slack_user_id, display_name, cached_at (empty, ignored) and email, utf-8 with a BOM.
The path defaults to "refdocs/slack user cache.csv". Output rows are
{id, displayName, email, slackUserId, teamId: null}, in CSV order. Rows without a Slack ID or
email are skipped, and a repeated Slack ID or email keeps its first row.

The output is real names and emails: seed/people.json is gitignored. Whether it is ever
committed is decided at commit time, not here.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "seed" / "people.json"
DEFAULT_CSV = ROOT / "refdocs" / "slack user cache.csv"


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV)
    if not src.exists():
        print(f"CSV not found: {src}\nPass its path as the first argument.", file=sys.stderr)
        return 1
    people, ids, emails = [], set(), set()
    with src.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            slack, email = (r.get("slack_user_id") or "").strip(), (r.get("email") or "").strip().lower()
            if not slack or not email or slack in ids or email in emails:
                continue
            ids.add(slack)
            emails.add(email)
            people.append({
                "id": f"p-{slack}", "displayName": (r.get("display_name") or "").strip() or email,
                "email": email, "slackUserId": slack, "teamId": None,
            })
    if not people:
        print(f"No usable rows in {src} (need slack_user_id and email columns).", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(people, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"people: {len(people)} rows -> {OUT.relative_to(ROOT)} (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
