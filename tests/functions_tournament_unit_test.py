"""
Tournament Unit Tests using pytest
"""

import asyncio
from datetime import datetime, timezone
import pytest
from deps.tournament_functions import build_tournament_tree
from deps.tournament_data_class import TournamentGame

lock = asyncio.Lock()


def test_build_tournament_tree_full_first_round():
    """Test to generate the tree from a list"""
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, now_date),
        TournamentGame(2, 1, 3, 4, None, now_date),
        TournamentGame(3, 1, 5, 6, None, now_date),
        TournamentGame(4, 1, 7, 8, None, now_date),
        TournamentGame(5, 1, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, now_date, 5, 6),
    ]
    tree = build_tournament_tree(list_tournament_games)
    assert tree is not None
    assert tree.id == 7  # Root node
    assert tree.next_game1.id == 5
    assert tree.next_game2.id == 6
    assert tree.next_game1.next_game1.id == 1
    assert tree.next_game1.next_game2.id == 2
    assert tree.next_game2.next_game1.id == 3
    assert tree.next_game2.next_game2.id == 4
    assert tree.next_game1.next_game1.next_game1 is None
    assert tree.next_game1.next_game1.next_game2 is None
    assert tree.next_game1.next_game2.next_game1 is None
    assert tree.next_game1.next_game2.next_game2 is None
    assert tree.next_game2.next_game1.next_game1 is None
    assert tree.next_game2.next_game1.next_game2 is None
    assert tree.next_game2.next_game2.next_game1 is None
    assert tree.next_game2.next_game2.next_game2 is None
    
