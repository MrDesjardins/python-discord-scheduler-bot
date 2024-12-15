""" Functions usesd in the tournament module """

import random
from typing import Dict, List, Optional
from deps.data_access_data_class import UserInfo
from deps.tournament_data_class import TournamentGame
from deps.tournament_models import TournamentNode
from deps.tournament_data_access import (block_registration_today_tournament_start, fetch_tournament_games_by_tournament_id, 
                                         get_people_registered_for_tournament,
                                        get_tournaments_starting_today, save_tournament_games)

def start_tournaments() -> None:
    """
    Every day, check if the tournament start date is the current date to block registration and
    assign people to tournament games.
    """
    
    # Get the list of tournaments that are starting today from all guilds
    block_registration_today_tournament_start()
    tournaments = get_tournaments_starting_today()
    for tournament in tournaments:
        # Get list of people ID who registered
        people:List[UserInfo] = get_people_registered_for_tournament(tournament.id)

        # All games in the bracket
        tournament_games = fetch_tournament_games_by_tournament_id(tournament.id)

        # Assign people to tournament games
        games_to_save = assign_people_to_games(tournament, tournament_games, people)

        # Save the games
        save_tournament_games(games_to_save)


def build_tournament_tree(tournament: List[TournamentGame]) -> Optional[TournamentNode]:
    """
    Builds a tree structure from a list of TournamentGame objects.

    Args:
        tournament (List[TournamentGame]): A list of TournamentGame objects.

    Returns:
        Optional[TournamentNode]: The root node of the tournament tree.
    """
    if not tournament or len(tournament) == 0:
        return None

    # Map to hold nodes by their ID
    nodes: Dict[int, TournamentNode] = {}

    # Step 1: Create a node for each game
    for game in tournament:
        nodes[game.id] = TournamentNode(
            id=game.id,
            tournament_id=game.tournament_id,
            user1_id=game.user1_id,
            user2_id=game.user2_id,
            user_winner_id=game.user_winner_id,
            timestamp=game.timestamp,
        )

    # Step 2: Connect the tree
    root = None
    for game in tournament:
        node = nodes[game.id]

        # Link child nodes if next_game1_id or next_game2_id are present
        if game.next_game1_id:
            node.next_game1 = nodes.get(game.next_game1_id)
        if game.next_game2_id:
            node.next_game2 = nodes.get(game.next_game2_id)

        # If a node has no children (not referenced by any other next_game1_id or next_game2_id), it is the root
        if not any(game.id in (t.next_game1_id, t.next_game2_id) for t in tournament):
            root = node

    return root

def assign_people_to_games(tournament: TournamentNode, tournament_games: List[TournamentGame], people: List[UserInfo]) -> List[TournamentNode]:
    """
    Assign people to tournament games.

    Args:
        tournament (TournamentNode): The root node of the tournament tree.
        tournament_games (List[TournamentGame]): A list of tournament games.
        people (List[UserInfo]): A list of people to assign to the games.
    """
    if not tournament or not tournament_games or not people:
        return
    
    # Assign people to games randomly on the last level of the tree
    leaf_nodes = [node for node in tournament_games if not node.next_game1_id and not node.next_game2_id]

    # Sort the list of leaf nodes by ID
    leaf_nodes.sort(key=lambda x: x.id)
    
    # Reduce the list for the number of people
    if len(leaf_nodes) > len(people):
        leaf_nodes = leaf_nodes[:len(people)]

    # Randomize the list of people
    random.shuffle(people)

    # Assign people to games by taking two persons sequentially and assigned them to a leaf node
    for i in range(0, len(leaf_nodes), 2):
        if i + 1 < len(people):
            leaf_nodes[i].user1_id = people[i].id
            leaf_nodes[i].user2_id = people[i + 1].id

    return leaf_nodes
    