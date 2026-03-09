"""
Integration tests for private channel data access functions.
Uses the real cache layer — no Discord, no database.
"""

import pytest

from deps.cache import remove_cache
from deps.data_access import (
    KEY_GUILD_ACTIVE_PRIVATE_CHANNEL,
    KEY_GUILD_PRIVATE_CHANNEL_CATEGORY,
    data_access_get_guild_active_private_channel,
    data_access_get_guild_private_channel_category_id,
    data_access_remove_guild_active_private_channel,
    data_access_set_guild_active_private_channel,
    data_access_set_guild_private_channel_category_id,
)

GUILD_A = 9001
GUILD_B = 9002
CATEGORY_ID = 100
CHANNEL_ID = 200
CREATOR_ID = 300


@pytest.fixture(autouse=True)
def clean_cache():
    """Remove relevant cache keys before and after each test."""
    for guild_id in [GUILD_A, GUILD_B]:
        remove_cache(False, f"{KEY_GUILD_PRIVATE_CHANNEL_CATEGORY}:{guild_id}")
        remove_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}")
    yield
    for guild_id in [GUILD_A, GUILD_B]:
        remove_cache(False, f"{KEY_GUILD_PRIVATE_CHANNEL_CATEGORY}:{guild_id}")
        remove_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}")


# ---------------------------------------------------------------------------
# Private channel category config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_category_get_returns_none_when_not_set():
    """Getting a category that was never set returns None."""
    result = await data_access_get_guild_private_channel_category_id(GUILD_A)
    assert result is None


@pytest.mark.asyncio
async def test_category_set_then_get_returns_id():
    """Setting a category id and then getting it returns the same id."""
    data_access_set_guild_private_channel_category_id(GUILD_A, CATEGORY_ID)
    result = await data_access_get_guild_private_channel_category_id(GUILD_A)
    assert result == CATEGORY_ID


@pytest.mark.asyncio
async def test_category_guild_isolation():
    """Category set for guild A does not affect guild B."""
    data_access_set_guild_private_channel_category_id(GUILD_A, CATEGORY_ID)
    result = await data_access_get_guild_private_channel_category_id(GUILD_B)
    assert result is None


@pytest.mark.asyncio
async def test_category_overwrite_replaces_previous_value():
    """Setting the category a second time replaces the previous value."""
    data_access_set_guild_private_channel_category_id(GUILD_A, CATEGORY_ID)
    data_access_set_guild_private_channel_category_id(GUILD_A, 999)
    result = await data_access_get_guild_private_channel_category_id(GUILD_A)
    assert result == 999


# ---------------------------------------------------------------------------
# Active private channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_channel_get_returns_none_when_not_set():
    """Getting the active channel before anything is set returns None."""
    result = await data_access_get_guild_active_private_channel(GUILD_A)
    assert result is None


@pytest.mark.asyncio
async def test_active_channel_set_then_get_returns_tuple():
    """Setting the active channel and getting it returns (channel_id, creator_id)."""
    data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    result = await data_access_get_guild_active_private_channel(GUILD_A)
    assert result == (CHANNEL_ID, CREATOR_ID)


@pytest.mark.asyncio
async def test_active_channel_remove_then_get_returns_none():
    """Removing the active channel record makes get return None."""
    data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    data_access_remove_guild_active_private_channel(GUILD_A)
    result = await data_access_get_guild_active_private_channel(GUILD_A)
    assert result is None


@pytest.mark.asyncio
async def test_active_channel_guild_isolation():
    """Active channel set for guild A does not affect guild B."""
    data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    result = await data_access_get_guild_active_private_channel(GUILD_B)
    assert result is None


@pytest.mark.asyncio
async def test_active_channel_remove_when_not_set_does_not_raise():
    """Removing when nothing was set should not raise any error."""
    data_access_remove_guild_active_private_channel(GUILD_A)
    result = await data_access_get_guild_active_private_channel(GUILD_A)
    assert result is None


@pytest.mark.asyncio
async def test_active_channel_two_guilds_are_independent():
    """Two guilds can each have their own active private channel independently."""
    data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    data_access_set_guild_active_private_channel(GUILD_B, 201, 301)

    result_a = await data_access_get_guild_active_private_channel(GUILD_A)
    result_b = await data_access_get_guild_active_private_channel(GUILD_B)

    assert result_a == (CHANNEL_ID, CREATOR_ID)
    assert result_b == (201, 301)


@pytest.mark.asyncio
async def test_active_channel_remove_one_guild_does_not_affect_other():
    """Removing guild A's channel does not remove guild B's channel."""
    data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    data_access_set_guild_active_private_channel(GUILD_B, 201, 301)

    data_access_remove_guild_active_private_channel(GUILD_A)

    result_a = await data_access_get_guild_active_private_channel(GUILD_A)
    result_b = await data_access_get_guild_active_private_channel(GUILD_B)

    assert result_a is None
    assert result_b == (201, 301)
