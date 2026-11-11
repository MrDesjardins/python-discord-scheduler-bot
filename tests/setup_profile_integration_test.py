"""Resolved stats.cc identity survives profile creation and account changes."""

from deps import analytic_settings_data_access
from deps.system_database import DatabaseManager


def test_setup_profile_persists_active_identity(tmp_path, monkeypatch):
    database = DatabaseManager(str(tmp_path / "profile.db"))
    monkeypatch.setattr(analytic_settings_data_access, "database_manager", database)
    try:
        for account, profile_id in [("First", "first-id"), ("Second", "second-id")]:
            analytic_settings_data_access.upsert_user_info(123, "Player", "Peak", account, profile_id, "UTC", 4500)
            row = (
                database.get_cursor()
                .execute(
                    "SELECT ubisoft_username_active, r6_tracker_active_id, time_zone, max_mmr FROM user_info WHERE id = 123"
                )
                .fetchone()
            )
            assert tuple(row) == (account, profile_id, "UTC", 4500)
    finally:
        database.get_conn().close()
