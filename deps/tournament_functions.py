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
    save_tournament,
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

        # Resize to the closest power of 2
        tournament.max_players = resize_tournament(tournament.max_players, len(people))

        # All games in the bracket
        tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament.id)

        # Assign people to tournament games
        games_to_save: List[TournamentNode] = assign_people_to_games(tournament, tournament_games, people)

        # Save the games
        save_tournament_games(games_to_save)
        save_tournament(tournament)


def next_power_of_two(n):
    """
    The next power of two is useful to get the smallest balanced tree for the tournament bracket.
    """
    if n <= 0:
        return 1  # Smallest power of 2 is 1
    # If n is already a power of 2, return it
    if (n & (n - 1)) == 0:
        return n
    # Find the next power of 2
    power = 1
    while power < n:
        power *= 2
    return power


def resize_tournament(tournament_max_player: int, number_of_people: int) -> int:
    """
    Resize the tournament to the closest power of 2.

    Args:
        tournament (Tournament): The tournament object.
        number_of_people (int): The number of people registered for the tournament.

    Returns:
        int: The new size of the tournament.
    """
    # Calculate the closest power of 2
    if tournament_max_player == number_of_people:
        return tournament_max_player

    # If the closest power of 2 is greater than the max_players, return the max_players
    return next_power_of_two(number_of_people)


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
    Assign people to tournament games. Assign to the last level of the tree but if the tree is not full, assign to the
    first level.

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

    # Mark the node as a winner if there is only one person
    assign_to_parent: List[TournamentNode] = []
    for node in leaf_nodes:
        if node.user1_id and not node.user2_id:
            # If only one user is assigned, mark the node as N/A
            node.user_winner_id = node.user1_id
            node.score = "N/A"
            node.timestamp = datetime.now(timezone.utc)
            assign_to_parent.append(node)
        elif node.user2_id and not node.user1_id:
            # If only one user is assigned, mark the node as N/A
            node.user_winner_id = node.user2_id
            node.score = "N/A"
            node.timestamp = datetime.now(timezone.utc)
            assign_to_parent.append(node)
        elif not node.user1_id and not node.user2_id:
            # If no user is assigned, mark the node as N/A
            node.user_winner_id = None
            node.score = "N/A"
            node.timestamp = datetime.now(timezone.utc)

    # Auto assign user as a winner if no user to be against
    for node in assign_to_parent:
        parent = [n for n in tournament_games if n.next_game1_id == node.id or n.next_game2_id == node.id]
        if len(parent) == 0:
            parent[0].user2_id = node.user_winner_id

    # Still might have nodes without 1 user or 2 users who has been marked as no winner

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

    # Find the parent node and assign the user
    node_parent = find_parent_of_node(tournament_tree, node.id)
    if node_parent is not None:
        # None might mean root
        # Set the winner to the parent node on the right side (user 1 if user 1 was winner, user 2 if user 2 was winner)
        if node.user1_id != user_id:
            node_parent.user1_id = node.user_winner_id
        else:
            node_parent.user2_id = node.user_winner_id

    # Save the updated tournament games
    save_tournament_games([node])
    return Reason(True)


def find_parent_of_node(tree: TournamentNode, child_id: int) -> Optional[TournamentNode]:
    """
    Perform a breadth-first search to find the parent node of the given child node.
    """
    queue = deque([tree])  # Initialize the queue with the root node

    while queue:
        current_node = queue.popleft()  # Get the next node in the queue

        # Check if the child node is a direct child of the current node
        if current_node.next_game1 and current_node.next_game1.id == child_id:
            return current_node
        if current_node.next_game2 and current_node.next_game2.id == child_id:
            return current_node

        # Add child nodes to the queue
        if current_node.next_game1:
            queue.append(current_node.next_game1)
        if current_node.next_game2:
            queue.append(current_node.next_game2)

    return None  # Return None if no parent node is found


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
