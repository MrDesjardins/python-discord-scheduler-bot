"""
Integration Test Functions

Performs tests that are more complex and take more time. For example,
tests that involve database access, network access, or more than one class.
"""

import pytest
from deps.functions_r6_tracker import get_r6tracker_max_rank


class TestR6Tracker:
    """Test about downloading data from r6tracker"""

    @pytest.mark.asyncio
    async def test_highest_rank_diamond(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("noSleep_rb6")
        assert rank == "Diamond"

    @pytest.mark.asyncio
    async def test_highest_rank_platinum(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("LebronsCock")
        assert rank == "Platinum"

    @pytest.mark.asyncio
    async def test_highest_rank_user_not_found(self):
        """Test the highest rank of a user that exist"""
        # with pytest.raises(Exception):
        #     await get_r6tracker_max_rank("DoesNotExist123000Name")
        rank = await get_r6tracker_max_rank("DoesNotExist123000Name")
        assert rank == "Copper"

    @pytest.mark.asyncio
    async def test_highest_rank_champion(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("Funkyshmug")
        assert rank == "Champion"

    @pytest.mark.asyncio
    async def test_highest_rank_emerald(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("Adahdf.")
        assert rank == "Emerald"

    @pytest.mark.asyncio
    async def test_highest_rank_gold(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("J0hn_Th1cc")
        assert rank == "Gold"

    @pytest.mark.asyncio
    async def test_highest_rank_emerald_2(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("Samtbs2")
        assert rank == "Emerald"
