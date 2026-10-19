#!/usr/bin/env python3
"""Run the repo's tests and print one summary.   (make test, make client-test, make server-test)

    python3 scripts/test_all.py [frontend] [server]      (no argument: both)

Every test prints its name, PASSED / FAILED and how far through its suite it is. The table at the end gives
passed, failed and skipped with the percentage that passed, per suite and overall, and lists what failed.
The exit code is 1 if any test failed or a suite could not run at all (for example no database).

To add a suite (Playwright, say), add an entry to SUITES that returns a Result.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
COLOR = sys.stdout.isatty()
MAX_LISTED = 25  # a dead database fails every test; the summary names the first few, not hundreds


def paint(text: str, code: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if COLOR else text


@dataclass
class Result:
    name: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0  # collection or setup errors, and a runner that never started
    failures: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.total > 0


def banner(title: str) -> None:
    print(f"\n{paint('═' * 78, '2')}\n{paint(title, '1')}\n{paint('═' * 78, '2')}", flush=True)


def frontend(tmp: Path) -> Result:
    """vitest, with the progress reporter in client/vitest.reporter.ts."""
    client = ROOT / "client"
    summary = tmp / "frontend.json"
    listing = subprocess.run(["npx", "vitest", "list", "--json"], cwd=client, capture_output=True, text=True)
    try:
        total = len(json.loads(listing.stdout))
    except ValueError:
        total = 0  # the percentage is then left off; the counts still come from the reporter
    env = {**os.environ, "WB_TEST_TOTAL": str(total), "WB_TEST_SUMMARY": str(summary)}
    code = subprocess.run(["npx", "vitest", "run", "--reporter=./vitest.reporter.ts"], cwd=client, env=env).returncode

    result = Result("Frontend (vitest)")
    if summary.exists():
        data = json.loads(summary.read_text())
        result.passed, result.failed, result.skipped = data["passed"], data["failed"], data["skipped"]
        result.errors, result.failures = data["errors"], data["failures"]
    if code != 0 and result.failed == 0 and result.errors == 0:
        result.errors = 1  # vitest failed without reporting a failing test
    return result


def server(tmp: Path) -> Result:
    """pytest -v, which already prints the name, PASSED / FAILED and the percentage on each line."""
    junit = tmp / "server.xml"
    pytest = ROOT / "server" / ".venv" / "bin" / "pytest"
    code = subprocess.run([str(pytest), "-v", f"--junitxml={junit}"], cwd=ROOT / "server").returncode

    result = Result("Backend (pytest)")
    if not junit.exists():
        result.errors = 1  # pytest stopped before it could write anything, e.g. DATABASE_URL is not set
        return result
    for suite in ElementTree.parse(junit).getroot().iter("testsuite"):
        result.failed += int(suite.get("failures", 0))
        result.errors += int(suite.get("errors", 0))
        result.skipped += int(suite.get("skipped", 0))
        result.passed += int(suite.get("tests", 0)) - int(suite.get("failures", 0)) - int(suite.get("errors", 0)) - int(suite.get("skipped", 0))
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                result.failures.append(f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}")
    if code != 0 and result.failed == 0 and result.errors == 0:
        result.errors = 1
    return result


DEV_ONLY_STRINGS = ["Sign in as", "Sign in with real Google", "/dev/accounts", "X-Dev-User-Email", "Choose an account"]


def bundle(tmp: Path) -> Result:
    """Builds the production frontend and fails if any development-only sign-in text or call is still inside it."""
    out = tmp / "bundle"
    build = subprocess.run(["npx", "vite", "build", "--outDir", str(out), "--emptyOutDir"], cwd=ROOT / "client", capture_output=True, text=True)
    result = Result("Other (prod bundle)")
    if build.returncode != 0:
        result.errors = 1
        result.failures.append("vite build failed:\n" + build.stderr[-500:])
        return result
    text = "".join(p.read_text(errors="ignore") for p in out.rglob("*") if p.suffix in (".js", ".html"))
    for needle in DEV_ONLY_STRINGS:
        if needle in text:
            result.failed += 1
            result.failures.append(f"production bundle contains {needle!r}")
        else:
            result.passed += 1
    return result


SUITES = {"frontend": frontend, "server": server, "bundle": bundle}


def percent(part: int, whole: int) -> str:
    return f"{part / whole * 100:5.1f}%" if whole else "  n/a"


def summary(results: list[Result]) -> None:
    banner("RESULTS")
    print(f"{'Suite':<22}{'Total':>7}{'Passed':>8}{'Failed':>8}{'Errors':>8}{'Skipped':>9}{'Passed %':>11}")
    for r in results + ([total_of(results)] if len(results) > 1 else []):
        line = f"{r.name:<22}{r.total:>7}{r.passed:>8}{r.failed:>8}{r.errors:>8}{r.skipped:>9}{percent(r.passed, r.total):>11}"
        print(paint(line, "32" if r.ok else "31"))
    failures = [(r.name, f) for r in results for f in r.failures]
    if failures:
        print(f"\n{paint('Failed tests:', '31;1')}")
        for suite, name in failures[:MAX_LISTED]:
            print(f"  {suite}: {name}")
        if len(failures) > MAX_LISTED:
            print(f"  ... and {len(failures) - MAX_LISTED} more (see the run above)")


def total_of(results: list[Result]) -> Result:
    everything = Result("All")
    for r in results:
        everything.passed += r.passed
        everything.failed += r.failed
        everything.skipped += r.skipped
        everything.errors += r.errors
    return everything


def main(argv: list[str]) -> int:
    wanted = argv or list(SUITES)
    unknown = [w for w in wanted if w not in SUITES]
    if unknown:
        print(f"Unknown suite: {', '.join(unknown)}. Choose from: {', '.join(SUITES)}.", file=sys.stderr)
        return 2
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for key in wanted:
            banner({"frontend": "FRONTEND TESTS (vitest)", "server": "SERVER TESTS (pytest)"}.get(key, key.upper()))
            results.append(SUITES[key](Path(tmp)))
    summary(results)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
