"""
Map models
"""

from deps.tournaments.tournament_data_class import TournamentGame
from deps.tournaments.tournament_models import TournamentNode


def map_tournament_node_to_tournament_game(tournament_node: TournamentNode) -> TournamentGame:
    """
    Map a TournamentNode to a TournamentGame
    """
    return TournamentGame(
        id=tournament_node.id,
        tournament_id=tournament_node.tournament_id,
        user1_id=tournament_node.user1_id,
        user2_id=tournament_node.user2_id,
        user_winner_id=tournament_node.user_winner_id,
        score=tournament_node.score,
        map=tournament_node.map,
        timestamp=tournament_node.timestamp,
    )
