"""Unit test for mapping"""

from datetime import datetime
from deps.tournaments.tournament_models import TournamentNode
from deps.tournaments.tournament_mapper import map_tournament_node_to_tournament_game


def test_map_tournament_game() -> None:
    """
    Test Node to Game mapping
    """
    tournament_node: TournamentNode = TournamentNode(
        id=1,
        tournament_id=11,
        user1_id=1,
        user2_id=2,
        user_winner_id=1,
        score="2-1",
        map="map",
        timestamp=datetime(2021, 1, 1),
    )
    tournament_game = map_tournament_node_to_tournament_game(tournament_node)
    assert tournament_game.id == 1
    assert tournament_game.tournament_id == 11
    assert tournament_game.user1_id == 1
    assert tournament_game.user2_id == 2
    assert tournament_game.user_winner_id == 1
    assert tournament_game.score == "2-1"
    assert tournament_game.map == "map"
    assert tournament_game.timestamp == datetime(2021, 1, 1)
