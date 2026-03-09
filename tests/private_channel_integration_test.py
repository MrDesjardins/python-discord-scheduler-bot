"""
Integration tests for private channel data access functions.
Uses the real cache layer — no Discord, no database.
"""

import pytest

from deps.cache import remove_cache
from deps.data_access import (
    KEY_GUILD_ACTIVE_PRIVATE_CHANNEL,
    KEY_GUILD_PRIVATE_CHANNEL_CATEGORY,
    data_access_get_guild_active_private_channels,
    data_access_get_guild_private_channel_category_id,
    data_access_remove_guild_active_private_channel,
    data_access_set_guild_active_private_channel,
    data_access_set_guild_private_channel_category_id,
)

GUILD_A = 9001
GUILD_B = 9002
CATEGORY_ID = 100
CHANNEL_ID = 200
CHANNEL_ID_2 = 201
CREATOR_ID = 300
CREATOR_ID_2 = 301


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
# Active private channels (many at once)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_channels_get_returns_empty_when_not_set():
    """Getting active channels before anything is set returns empty dict."""
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {}


@pytest.mark.asyncio
async def test_active_channel_set_then_get_returns_entry():
    """Setting a channel and getting it returns the correct entry."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {CHANNEL_ID: (CREATOR_ID, True)}


@pytest.mark.asyncio
async def test_active_channel_remove_then_get_returns_empty():
    """Removing the only channel makes get return empty dict."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    await data_access_remove_guild_active_private_channel(GUILD_A, CHANNEL_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {}


@pytest.mark.asyncio
async def test_active_channel_guild_isolation():
    """Active channel set for guild A does not affect guild B."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_B)
    assert result == {}


@pytest.mark.asyncio
async def test_active_channel_remove_when_not_set_does_not_raise():
    """Removing when nothing was set should not raise any error."""
    await data_access_remove_guild_active_private_channel(GUILD_A, CHANNEL_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {}


@pytest.mark.asyncio
async def test_two_channels_same_guild_stored_independently():
    """Two private channels in the same guild are stored as separate entries."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID_2, CREATOR_ID_2)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {
        CHANNEL_ID: (CREATOR_ID, True),
        CHANNEL_ID_2: (CREATOR_ID_2, True),
    }


@pytest.mark.asyncio
async def test_remove_one_channel_leaves_other_intact():
    """Removing one channel from a guild does not affect the other."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID_2, CREATOR_ID_2)
    await data_access_remove_guild_active_private_channel(GUILD_A, CHANNEL_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {CHANNEL_ID_2: (CREATOR_ID_2, True)}


@pytest.mark.asyncio
async def test_active_channel_two_guilds_are_independent():
    """Two guilds can each have their own active private channels independently."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    await data_access_set_guild_active_private_channel(GUILD_B, CHANNEL_ID_2, CREATOR_ID_2)

    result_a = await data_access_get_guild_active_private_channels(GUILD_A)
    result_b = await data_access_get_guild_active_private_channels(GUILD_B)

    assert result_a == {CHANNEL_ID: (CREATOR_ID, True)}
    assert result_b == {CHANNEL_ID_2: (CREATOR_ID_2, True)}


@pytest.mark.asyncio
async def test_remove_guild_a_channel_does_not_affect_guild_b():
    """Removing guild A's channel does not remove guild B's channel."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    await data_access_set_guild_active_private_channel(GUILD_B, CHANNEL_ID_2, CREATOR_ID_2)
    await data_access_remove_guild_active_private_channel(GUILD_A, CHANNEL_ID)

    result_a = await data_access_get_guild_active_private_channels(GUILD_A)
    result_b = await data_access_get_guild_active_private_channels(GUILD_B)

    assert result_a == {}
    assert result_b == {CHANNEL_ID_2: (CREATOR_ID_2, True)}


@pytest.mark.asyncio
async def test_active_channel_track_false_stored_and_retrieved():
    """Setting track=False is persisted and returned correctly."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID, track=False)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {CHANNEL_ID: (CREATOR_ID, False)}


@pytest.mark.asyncio
async def test_active_channel_track_defaults_to_true():
    """Omitting track defaults to True."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result[CHANNEL_ID][1] is True


@pytest.mark.asyncio
async def test_mixed_track_values_in_same_guild():
    """A guild can have one tracked and one untracked private channel simultaneously."""
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID, CREATOR_ID, track=True)
    await data_access_set_guild_active_private_channel(GUILD_A, CHANNEL_ID_2, CREATOR_ID_2, track=False)
    result = await data_access_get_guild_active_private_channels(GUILD_A)
    assert result == {
        CHANNEL_ID: (CREATOR_ID, True),
        CHANNEL_ID_2: (CREATOR_ID_2, False),
    }
