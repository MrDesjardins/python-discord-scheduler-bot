"""Unit tests for the bot-level reductions of R6 Tracker requests"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from deps import bot_common_actions
from deps.bot_common_actions import (
    R6_TRACKER_FETCH_MEMORY_SECONDS,
    download_full_matches_remembering_ranks,
    persist_siege_matches_cross_guilds,
    post_queued_user_stats,
    refresh_current_rank_roles_cross_guilds,
)
from deps.models import UserQueueForStats, UserWithUserMatchInfo
from deps.mybot import MyBot
from tests.mock_model import mock_user1, mock_user2


def _recent_match(rank_points: int, rank_name: str):
    return SimpleNamespace(
        match_timestamp=datetime.now(timezone.utc) - timedelta(minutes=20),
        is_rollback=False,
        rank_points=rank_points,
        rank_name=rank_name,
    )


async def test_queue_is_held_without_fetching_while_tracker_blocks():
    queued = UserQueueForStats(mock_user1, 100, datetime.now(timezone.utc) - timedelta(minutes=10))
    with (
        patch.object(bot_common_actions, "data_access_get_list_member_stats", AsyncMock(return_value=[queued])),
        patch.object(bot_common_actions, "tracker_block_remaining_seconds", return_value=1800.0),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock()) as download,
        patch.object(bot_common_actions, "data_access_increment_member_stats_attempts", AsyncMock()) as attempts,
    ):
        await post_queued_user_stats()

    download.assert_not_awaited()
    attempts.assert_not_awaited()


async def test_queue_waits_without_burning_attempts_while_the_browser_is_busy():
    """The daily collection can hold the browser for many minutes; queued users must not be dropped"""
    queued = UserQueueForStats(mock_user1, 100, datetime.now(timezone.utc) - timedelta(minutes=10))
    with (
        patch.object(bot_common_actions, "data_access_get_list_member_stats", AsyncMock(return_value=[queued])),
        patch.object(bot_common_actions, "is_browser_busy", return_value=True),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock()) as download,
        patch.object(bot_common_actions, "data_access_increment_member_stats_attempts", AsyncMock()) as attempts,
    ):
        await post_queued_user_stats()

    download.assert_not_awaited()
    attempts.assert_not_awaited()


async def test_match_download_remembers_the_rank_it_shows():
    queued = UserQueueForStats(mock_user1, 100, datetime.now(timezone.utc))
    fetched = [UserWithUserMatchInfo(queued, [_recent_match(3120, "EMERALD V")])]
    with (
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock(return_value=fetched)),
        patch.object(bot_common_actions, "data_access_set_r6tracker_current_season_rank") as set_rank,
    ):
        assert await download_full_matches_remembering_ranks([queued]) == fetched

    set_rank.assert_called_once_with(
        mock_user1.ubisoft_username_active, ("Emerald", 3120), R6_TRACKER_FETCH_MEMORY_SECONDS
    )


async def test_periodic_persist_skips_users_fetched_when_they_left_voice():
    now = datetime.now(timezone.utc)
    with (
        patch.object(bot_common_actions, "get_active_user_info", return_value=[mock_user1, mock_user2]),
        patch.object(
            bot_common_actions,
            "data_access_were_r6tracker_matches_fetched",
            AsyncMock(side_effect=lambda user_id: user_id == mock_user1.id),
        ),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock(return_value=[])) as download,
    ):
        await persist_siege_matches_cross_guilds(now - timedelta(hours=4), now, skip_recently_fetched=True)

    assert [entry.user_info.id for entry in download.await_args.args[0]] == [mock_user2.id]


async def test_periodic_persist_with_everyone_fetched_makes_no_request():
    now = datetime.now(timezone.utc)
    with (
        patch.object(bot_common_actions, "get_active_user_info", return_value=[mock_user1]),
        patch.object(bot_common_actions, "data_access_were_r6tracker_matches_fetched", AsyncMock(return_value=True)),
        patch.object(bot_common_actions, "download_full_matches_async", AsyncMock()) as download,
    ):
        await persist_siege_matches_cross_guilds(now - timedelta(hours=4), now, skip_recently_fetched=True)

    download.assert_not_awaited()


async def test_rank_refresh_without_fetching_only_uses_known_ranks():
    bot = Mock(spec=MyBot)
    bot.guilds = []
    now = datetime.now(timezone.utc)
    with (
        patch.object(bot_common_actions, "get_active_user_info", return_value=[mock_user1, mock_user2]),
        patch.object(
            bot_common_actions,
            "data_access_has_cached_r6tracker_current_season_rank",
            AsyncMock(side_effect=lambda name: name == mock_user1.ubisoft_username_active),
        ),
        patch.object(
            bot_common_actions, "data_access_prefetch_r6tracker_current_season_ranks", AsyncMock()
        ) as prefetch,
        patch.object(
            bot_common_actions, "fetch_current_season_rank_for_account", AsyncMock(return_value=("Gold", 2600))
        ),
        patch.object(bot_common_actions, "post_rank_change_notifications", AsyncMock()),
    ):
        summary = await refresh_current_rank_roles_cross_guilds(
            now - timedelta(hours=4), now, bot, include_connected_voice=False, fetch_missing_ranks=False
        )

    assert summary.candidates == 1
    prefetch.assert_awaited_once_with([mock_user1.ubisoft_username_active])


async def test_daily_profile_refresh_is_skipped_when_statscc_is_primary(monkeypatch):
    """The Tracker profile/operator refresh must not run when stats.cc rebuilds the snapshot."""
    monkeypatch.delenv("MATCH_STATS_PROVIDER", raising=False)
    now = datetime.now(timezone.utc)
    with (
        patch.object(bot_common_actions, "download_full_user_information_async", AsyncMock()) as download,
        patch.object(bot_common_actions, "fetch_and_persist_operator_stats", AsyncMock()) as operators,
        patch.object(bot_common_actions, "get_active_user_info") as active,
    ):
        await bot_common_actions.persist_user_full_information_cross_guilds(now - timedelta(days=1), now)

    download.assert_not_awaited()
    operators.assert_not_awaited()
    active.assert_not_called()


async def test_daily_profile_refresh_still_runs_under_tracker_mode(monkeypatch):
    monkeypatch.setenv("MATCH_STATS_PROVIDER", "tracker")
    now = datetime.now(timezone.utc)
    with (
        patch.object(bot_common_actions, "get_active_user_info", return_value=[]),
        patch.object(
            bot_common_actions, "download_full_user_information_async", AsyncMock(return_value=[])
        ) as download,
        patch.object(bot_common_actions, "fetch_and_persist_operator_stats", AsyncMock()) as operators,
    ):
        await bot_common_actions.persist_user_full_information_cross_guilds(now - timedelta(days=1), now)

    download.assert_awaited_once()
    operators.assert_awaited_once()
