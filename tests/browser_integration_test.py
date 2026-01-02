"""
Integration test to check if the matches information is downloaded correctly
This is an integration test (slow) and perform HTTP requests. The goal is to ensure the system can download
the information from the API.
"""

import asyncio
from unittest.mock import patch
from datetime import datetime, timezone
import pytest
from deps.data_access_data_class import UserInfo
from deps.browser_context_manager import BrowserContextManager
from deps.models import UserQueueForStats
import deps.log
DELAY_SECOND = 5 # Delay to avoid rate limiting

@patch.object(deps.log, deps.log.print_error_log.__name__)
async def test_matches(mock_error_log):
    """Test to check if the matches information is downloaded correctly"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager() as context:
        user = UserInfo(357551747146842124, "Patrick", "noSleep_rb6", "isleep_rb6", None, "east", 0)
        user_queue = UserQueueForStats(user, "1", datetime.now(timezone.utc))
        context.download_full_matches(user_queue)
    assert mock_error_log.call_count == 0


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_diamond(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("noSleep_rb6") as context:
        rank = context.download_max_rank("noSleep_rb6")
    assert rank[0] == "Diamond"
    assert rank[1] == 4343


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_platinum(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("LebronsCock") as context:
        rank = context.download_max_rank("LebronsCock")
    assert rank[0] == "Platinum"
    assert rank[1] == 3211


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_user_not_found(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("DoesNotExist123000Name") as context:
        rank = context.download_max_rank("DoesNotExist123000Name")
    assert rank[0] == "Copper"
    assert rank[1] == 0


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_champion(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("Funkyshmug") as context:
        rank = context.download_max_rank("Funkyshmug")
    assert rank[0] == "Champion"
    assert rank[1] == 4561


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_emerald(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("Adahdf.") as context:
        rank = context.download_max_rank("Adahdf.")
    assert rank[0] == "Emerald"
    assert rank[1] == 4343


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_gold(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("J0hn_Th1cc") as context:
        rank = context.download_max_rank("J0hn_Th1cc")
    assert rank[0] == "Gold"
    assert rank[1] == 4343


@patch.object(deps.log, deps.log.print_error_log.__name__)
@pytest.mark.no_parallel
@pytest.mark.asyncio
async def test_highest_rank_emerald_2(mock_error_log):
    """Test the highest rank of a user that exist"""
    mock_error_log.return_value = None
    # Sleep to avoid rate limiting
    await asyncio.sleep(DELAY_SECOND)
    with BrowserContextManager("Yuuka_Kazami") as context:
        rank = context.download_max_rank("Yuuka_Kazami")
    assert rank[0] == "Emerald"
    assert rank[1] == 3787
