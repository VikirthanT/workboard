"""The standup snapshot script: a plain, readable copy of a WAL database, swapped in whole or not at all."""
import importlib.util
import os
import sqlite3
import stat
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "standup_snapshot.py"
spec = importlib.util.spec_from_file_location("standup_snapshot", SCRIPT)
standup_snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standup_snapshot)


@pytest.fixture
def live(tmp_path):
    """A WAL-mode database with a row that is still only in the -wal file, and a writer that stays connected, as the
    standup app's is."""
    path = tmp_path / "bot" / "standup.db"
    path.parent.mkdir()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE channels (slack_channel_id TEXT, name TEXT)")
    conn.execute("INSERT INTO channels VALUES ('C1', 'standup-npi')")
    conn.commit()
    yield path
    conn.close()


def header_mode(path) -> bytes:
    return Path(path).read_bytes()[18:20]  # b"\x02\x02" is WAL, b"\x01\x01" the ordinary journal


def test_the_copy_holds_the_data_and_is_not_in_wal_mode(live, tmp_path):
    assert header_mode(live) == b"\x02\x02"

    out = standup_snapshot.snapshot(str(live), str(tmp_path / "snap"))

    assert out == str(tmp_path / "snap" / "standup.db")
    assert header_mode(out) == b"\x01\x01"
    assert sqlite3.connect(out).execute("SELECT name FROM channels").fetchall() == [("standup-npi",)]
    assert os.listdir(tmp_path / "snap") == ["standup.db"]  # no temporary file left behind


def test_the_copy_opens_from_a_folder_nobody_can_write_to(live, tmp_path):
    folder = tmp_path / "snap"
    out = standup_snapshot.snapshot(str(live), str(folder))
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)  # the API's read only mount, as the reader sees it
    try:
        conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
        assert conn.execute("SELECT count(*) FROM channels").fetchone() == (1,)
        conn.close()
        assert sorted(os.listdir(folder)) == ["standup.db"]  # reading created no side files
    finally:
        folder.chmod(stat.S_IRWXU)


def test_a_later_run_replaces_the_copy_with_the_newer_data(live, tmp_path):
    standup_snapshot.snapshot(str(live), str(tmp_path / "snap"))
    writer = sqlite3.connect(live)
    writer.execute("INSERT INTO channels VALUES ('C2', 'standup-qa')")
    writer.commit()
    writer.close()

    out = standup_snapshot.snapshot(str(live), str(tmp_path / "snap"))

    assert sqlite3.connect(out).execute("SELECT count(*) FROM channels").fetchone() == (2,)


def test_a_failed_run_keeps_the_previous_copy(live, tmp_path):
    out = standup_snapshot.snapshot(str(live), str(tmp_path / "snap"))
    before = Path(out).read_bytes()

    with pytest.raises(sqlite3.Error):
        standup_snapshot.snapshot(str(tmp_path / "bot" / "missing.db"), str(tmp_path / "snap"))

    assert Path(out).read_bytes() == before
    assert os.listdir(tmp_path / "snap") == ["standup.db"]


def test_the_command_line_reports_success_and_failure(live, tmp_path, capsys):
    assert standup_snapshot.main(["x", str(live), str(tmp_path / "snap")]) == 0
    assert "Snapshot written:" in capsys.readouterr().out

    assert standup_snapshot.main(["x", str(tmp_path / "nope.db"), str(tmp_path / "snap")]) == 1
    assert "previous copy was kept" in capsys.readouterr().err

    assert standup_snapshot.main(["x"]) == 2
