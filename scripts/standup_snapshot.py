"""Copy the standup app's SQLite database to a plain file that Workboard's API container can read.

    python3 scripts/standup_snapshot.py /opt/standup-bot/standup.db /opt/workboard/standup-snapshot

The standup app keeps its database in WAL mode, and a reader of a WAL database must be able to create the `-shm` and
`-wal` side files next to it. The API container mounts its folder read only and runs as another user, so it cannot, and
SQLite answers "unable to open database file". This script reads the live file with SQLite's own backup call (a
consistent copy, taken while the standup app keeps working), switches the copy to the ordinary rollback journal, checks
it, and moves it into place in one step, so a reader never sees a half-written file. The live file is only read.

Run it from cron as the user that owns the standup database, every few minutes (see docs/DEPLOYMENT.md). It needs only
the Python standard library.
"""
import os
import sqlite3
import sys


def snapshot(source: str, dest_dir: str) -> str:
    """Write a plain copy of `source` into `dest_dir` under the same file name and return its path. If anything fails the
    previous copy is left as it was."""
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, os.path.basename(source))
    tmp = final + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        live = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            copy = sqlite3.connect(tmp)
            try:
                live.backup(copy)
                copy.execute("PRAGMA journal_mode=DELETE")  # the copy needs no side files, so a read only mount can open it
                verdict = copy.execute("PRAGMA quick_check").fetchone()[0]
                if verdict != "ok":
                    raise sqlite3.DatabaseError(f"the copy failed its check: {verdict}")
            finally:
                copy.close()
        finally:
            live.close()
        os.chmod(tmp, 0o644)  # the container's user is not the owner
        os.replace(tmp, final)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return final


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    try:
        path = snapshot(argv[1], argv[2])
    except (sqlite3.Error, OSError) as err:
        print(f"Snapshot failed, the previous copy was kept: {err}", file=sys.stderr)
        return 1
    print(f"Snapshot written: {path} ({os.path.getsize(path)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
