""" 
Integration Test Functions 

Performs tests that are more complex and take more time. For example, 
tests that involve database access, network access, or more than one class.
"""

import unittest
from deps.functions_r6_tracker import get_r6tracker_max_rank


class TrackerTest(unittest.TestCase):
    """Test about downloading data from r6tracker"""

    async def test_highest_rank_diamond(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("noSleep_rb6")
        self.assertEqual(rank, "Diamond")

    async def test_highest_rank_platinum(self):
        """Test the highest rank of a user that exist"""
        rank = await get_r6tracker_max_rank("LebronsCock")
        self.assertEqual(rank, "Platinum")

    async def test_highest_rank_user_not_found(self):
        """Test the highest rank of a user that exist"""
        with self.assertRaises(Exception):
            await get_r6tracker_max_rank("noSleep_rb6")

