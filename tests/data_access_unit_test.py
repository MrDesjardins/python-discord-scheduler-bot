"""Unit tests for data access helpers."""

from unittest.mock import ANY, AsyncMock, patch

from deps.data_access import data_access_get_r6tracker_current_season_rank


async def test_current_season_rank_uses_persistent_cache() -> None:
    """Current-season rank lookups use the DB-backed cache so deploys can reuse recent results."""
    with (
        patch("deps.data_access.remove_cache") as mock_remove_cache,
        patch("deps.data_access.get_cache", new_callable=AsyncMock, return_value=("Gold", 3123)) as mock_get_cache,
        patch("deps.data_access._download_current_season_rank_sync") as mock_download,
    ):
        result = await data_access_get_r6tracker_current_season_rank(" Player.Name ", force_fetch=False)

    assert result == ("Gold", 3123)
    mock_remove_cache.assert_not_called()
    mock_download.assert_not_called()
    mock_get_cache.assert_awaited_once_with(
        False,
        "R6TrackerCurrentSeasonRank:player.name",
        ANY,
        ttl_in_seconds=7200,
    )


async def test_current_season_rank_force_fetch_clears_persistent_cache() -> None:
    """Explicit current-rank refreshes clear the persistent cache before fetching."""
    with (
        patch("deps.data_access.remove_cache") as mock_remove_cache,
        patch("deps.data_access.get_cache", new_callable=AsyncMock, return_value=("Emerald", 3839)) as mock_get_cache,
    ):
        result = await data_access_get_r6tracker_current_season_rank("Player.Name", force_fetch=True)

    assert result == ("Emerald", 3839)
    mock_remove_cache.assert_called_once_with(False, "R6TrackerCurrentSeasonRank:player.name")
    mock_get_cache.assert_awaited_once_with(
        False,
        "R6TrackerCurrentSeasonRank:player.name",
        ANY,
        ttl_in_seconds=7200,
    )
