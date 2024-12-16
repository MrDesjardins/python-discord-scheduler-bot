""" Functions usesd in the tournament module """

from datetime import date, datetime, timezone
from collections import deque
import random
from typing import Dict, List, Optional
from deps.data_access_data_class import UserInfo
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_models import TournamentNode
from deps.tournament_data_access import (
    block_registration_today_tournament_start,
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    get_people_registered_for_tournament,
    get_tournaments_starting_today,
    register_user_for_tournament,
    save_tournament_games,
)
from deps.models import Reason


def can_register_to_tournament(tournament_id: int, user_id: int) -> Reason:
    """Check if a user can register for a tournament."""
    tournament: Optional[Tournament] = fetch_tournament_by_id(tournament_id)
    if not tournament:
        return Reason(False, "The tournament does not exist.")

    if tournament.has_started:
        return Reason(False, "The tournament has already started.")

    current_date = datetime.now(timezone.utc)
    if current_date < tournament.registration_date:
        return Reason(False, "Registration is not open yet.")

    if current_date > tournament.start_date:
        return Reason(False, "Registration is closed.")

    max_participants = tournament.max_players
    participants: List[UserInfo] = get_people_registered_for_tournament(tournament_id)

    # Check if the tournament is full
    if len(participants) >= max_participants:
        return Reason(False, "The tournament is full.")

    # Check if the user is already registered for the tournament
    for participant in participants:
        if participant.id == user_id:
            return Reason(False, "You are already registered for the tournament.")

    return Reason(True)


def register_for_tournament(tournament_id: int, user_id: int) -> Reason:
    """
    Register a user for a tournament.

    Args:
        tournament_id (int): The ID of the tournament.
        user_id (int): The ID of the user.
    """
    current_date = datetime.now(timezone.utc)
    # Check if the user is already registered for the tournament
    reason = can_register_to_tournament(tournament_id, user_id)
    if reason.is_successful:
        # Register the user for the tournament
        register_user_for_tournament(tournament_id, user_id, current_date)
        return Reason(True)
    else:
        return reason


def start_tournaments(starting_date: date) -> None:
    """
    Every day, check if the tournament start date is the current date to block registration and
    assign people to tournament games.
    """

    # Get the list of tournaments that are starting today from all guilds
    block_registration_today_tournament_start(starting_date)
    tournaments = get_tournaments_starting_today(starting_date)
    for tournament in tournaments:
        # Get list of people ID who registered
        people: List[UserInfo] = get_people_registered_for_tournament(tournament.id)

        # All games in the bracket
        tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament.id)

        # Assign people to tournament games
        games_to_save: List[TournamentNode] = assign_people_to_games(tournament, tournament_games, people)

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
            map=game.map,
            score=game.score,
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


def assign_people_to_games(
    tournament: TournamentNode, tournament_games: List[TournamentGame], people: List[UserInfo]
) -> List[TournamentNode]:
    """
    Assign people to tournament games.

    Args:
        tournament (TournamentNode): The root node of the tournament tree.
        tournament_games (List[TournamentGame]): A list of tournament games.
        people (List[UserInfo]): A list of people to assign to the games.
    """

    # Assign people to games randomly on the last level of the tree
    leaf_nodes = [node for node in tournament_games if not node.next_game1_id and not node.next_game2_id]

    # Sort the list of leaf nodes by ID
    leaf_nodes.sort(key=lambda x: x.id)

    # Reduce the list for the number of people
    if len(leaf_nodes) > len(people):
        leaf_nodes = leaf_nodes[: len(people)]

    # Randomize the list of people
    random.shuffle(people)

    # Assign people to games by taking two persons sequentially and assigned them to a leaf node
    for i, _node in enumerate(leaf_nodes):
        if i * 2 + 1 < len(people):
            leaf_nodes[i].user1_id = people[i * 2].id
            leaf_nodes[i].user2_id = people[i * 2 + 1].id
            leaf_nodes[i].map = random.choice(tournament.maps.split(","))
    return leaf_nodes


def report_lost_tournament(tournament_id: int, user_id: int) -> Reason:
    """
    Report a user as lost in the tournament.

    Args:
        tournament_id (int): The ID of the tournament.
        user_id (int): The ID of the user.
    """
    # Get the tournament games
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

    # Get the tournament tree
    tournament_tree = build_tournament_tree(tournament_games)

    # Find the node where the user is present
    node = find_first_node_of_user_not_done(tournament_tree, user_id)

    # If the user is not found in the tournament tree, return
    if node is None:
        return Reason(False, "User not found in the tournament.")

    # Update the user_winner_id in the node
    node.user_winner_id = node.user1_id if node.user1_id != user_id else node.user2_id

    # Save the updated tournament games
    save_tournament_games([node])
    return Reason(True)


def find_first_node_of_user_not_done(tree: TournamentNode, user_id: int) -> Optional[TournamentNode]:
    """
    Perform a breadth-first search to find the first node where:
    - user_id matches either user1_id or user2_id
    - user_winner_id is None
    """
    queue = deque([tree])  # Initialize the queue with the root node

    while queue:
        current_node = queue.popleft()  # Get the next node in the queue

        # Check if the predicate matches
        if (
            current_node.user1_id == user_id or current_node.user2_id == user_id
        ) and current_node.user_winner_id is None:
            return current_node

        # Add child nodes to the queue
        if current_node.next_game1:
            queue.append(current_node.next_game1)
        if current_node.next_game2:
            queue.append(current_node.next_game2)

    return None  # Return None if no matching node is found
