""" Test Functions """

import unittest
from deps.functions import most_common


class TestMostCommon(unittest.TestCase):
    """Unit test for who play at which day of the week function"""

    def test_most_common_no_tie(self):
        """Return the most frequent element"""
        list1 = [1, 2, 2]
        result = most_common(list1)
        self.assertEqual(result, 2)

    def test_most_common_tie(self):
        """Return the first most common"""
        list1 = [2, 2, 3, 3]
        result = most_common(list1)
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
