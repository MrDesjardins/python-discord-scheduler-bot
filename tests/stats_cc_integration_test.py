"""Verify provider records round-trip through SQLite and share duplicate protection."""

import json
from pathlib import Path

from deps import analytic_match_data_access
from deps.data_access_data_class import UserInfo
from deps.stats_cc import parse_match
from deps.system_database import DatabaseManager


def test_statscc_match_persistence_and_duplicate_protection(tmp_path, monkeypatch):
    database = DatabaseManager(str(tmp_path / "statscc_test.db"))
    monkeypatch.setattr(analytic_match_data_access, "database_manager", database)
    try:
        recorded = json.loads(Path("tests/tests_assets/stats_cc_match.json").read_text(encoding="utf-8"))
        user = UserInfo(
            123, "Player", "noSleep_rb6", "noSleep_rb6", recorded["match"]["player_summary"]["profile_id"], "UTC", 0
        )
        database.get_cursor().execute(
            "INSERT INTO user_info (id, display_name) VALUES (?, ?)", (user.id, user.display_name)
        )
        database.get_conn().commit()
        match = parse_match(recorded["match"], recorded["detail"], recorded["config"], user)
        analytic_match_data_access.insert_if_nonexistant_full_match_info(user, [match])
        analytic_match_data_access.insert_if_nonexistant_full_match_info(user, [match])
        stored = analytic_match_data_access.data_access_fetch_user_full_match_info(user.id)
        assert len(stored) == 1
        assert {k: v for k, v in vars(stored[0]).items() if k != "id"} == {
            k: v for k, v in vars(match).items() if k != "id"
        }
    finally:
        database.get_conn().close()
