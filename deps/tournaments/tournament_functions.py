"""Functions usesd in the tournament module"""

from datetime import datetime, timezone
from collections import deque
import random
from typing import Dict, List, Optional, Union
from deps.bet.bet_functions import (
    distribute_gain_on_recent_ended_game,
    system_generate_game_odd,
)
from deps.data_access_data_class import UserInfo
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.tournaments.tournament_models import TournamentNode, TournamentResult
from deps.tournaments.tournament_data_access import (
    data_access_create_bracket,
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    get_people_registered_for_tournament,
    register_user_for_tournament,
    register_user_teammate_to_leader,
    save_tournament,
    save_tournament_games,
)
from deps.models import Reason
from deps.tournaments.tournament_mapper import map_tournament_node_to_tournament_game


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


async def start_tournament(tournament: Tournament) -> tuple[List[UserInfo], List[UserInfo]]:
    """
    Start a specific tournament
    Create the bracket
    """
    if tournament.id is None:
        return ([], [])
    # Get list of people ID who registered
    people: List[UserInfo] = get_people_registered_for_tournament(tournament.id)

    # Get the number of team. If solo (1v1), then the number of team is the number of people.
    team_count = len(people) // tournament.team_size  # Floor

    # Ensure we have enough people to fill two teams
    if team_count < 2:
        raise ValueError("Not enough players for a tournament. At least 2 teams are required or two people for 1v1.")

    # Reduce the list of people with few users that won't be part of the tournament
    people_in, people_out = find_people_in_and_out(people, tournament.team_size)

    # Resize to the closest power of 2
    tournament.max_players = resize_tournament(tournament.max_players, team_count)

    # Create the games (all brackets)
    data_access_create_bracket(tournament.id, tournament.max_players)

    # All games in the bracket
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament.id)

    # Assign people to tournament games
    if tournament.team_size == 1:
        leaders = people_in
        teammates = []
    else:
        # Randomly select team_count people to lead the team
        leaders = random.sample(people_in, team_count)
        # Others are teammates that will be assigned later
        teammates = [p for p in people_in if p not in leaders]

    node_to_save: List[TournamentGame] = assign_people_to_games(tournament, tournament_games, leaders)

    # Auto assign user as a winner if there is no possible opponent in the other side of the bracket
    node_to_save2: List[TournamentGame] = auto_assign_winner(tournament_games)

    # Save the nodes that was determined as auto in
    save_tournament_games(node_to_save + node_to_save2)

    # Save teammates to the first game of the tournament
    if len(teammates) > 0:
        for leader in leaders:
            for _teammate_i in range(0, tournament.team_size - 1):  # -1 because of the leader
                # Select a random teammate in the teammates list and remove it from the list
                teammate = random.choice(teammates)
                teammates.remove(teammate)
                register_user_teammate_to_leader(tournament.id, leader.id, teammate.id)

    # Tournament status
    tournament.has_started = True
    save_tournament(tournament)

    # Generate bet_game
    await system_generate_game_odd(tournament.id)

    return (people_in, people_out)


def has_node_without_user(dict_nodes: dict[int, TournamentGame], node: TournamentGame) -> bool:
    """
    Determine if a node has all its underlying branches without users even if maybe has games.
    """
    # We reached the end of a branch, check the user
    if node.next_game1_id is None and node.next_game2_id is None:
        return node.user1_id is None and node.user2_id is None

    # Dive into the children
    left_side_result = node.next_game1_id is not None and has_node_without_user(
        dict_nodes, dict_nodes[node.next_game1_id]
    )
    right_side_result = node.next_game2_id is not None and has_node_without_user(
        dict_nodes, dict_nodes[node.next_game2_id]
    )

    return left_side_result and right_side_result


def auto_assign_winner(tournament_games: List[TournamentGame]) -> List[TournamentGame]:
    """
    Find all nodes with user1_id set to None or user2_id set to None
    Then, check if any of the children node have a node with user1_id set to None AND user2_id set to None
    If yes, then we need to assign the win on the  node to the user1_id or user2_id (whichever is not None) and
    Assign the user1_id or user2_id of the parent node to the user_winner_id of the child node
    """
    # Find all nodes with user1_id set to None or user2_id set to None
    dict_nodes: dict[int, TournamentGame] = {node.id: node for node in tournament_games if node.id is not None}
    node_to_save: dict[int, TournamentGame] = {}
    tree = build_tournament_tree(tournament_games)
    if tree is None:
        return []

    def traverse(node: TournamentNode):

        if node.next_game1 is not None:
            auto_winner_id = traverse(node.next_game1)
            if auto_winner_id is not None:
                if node.user1_id is None:
                    node.user1_id = auto_winner_id
                    dict_nodes[node.id].user1_id = auto_winner_id
                else:
                    node.user2_id = auto_winner_id
                    dict_nodes[node.id].user2_id = auto_winner_id
                node_to_save[node.id] = dict_nodes[node.id]
        if node.next_game2 is not None:
            auto_winner_id = traverse(node.next_game2)
            if auto_winner_id is not None:
                if node.user1_id is None:
                    node.user1_id = auto_winner_id
                    dict_nodes[node.id].user1_id = auto_winner_id
                else:
                    node.user2_id = auto_winner_id
                    dict_nodes[node.id].user2_id = auto_winner_id
                node_to_save[node.id] = dict_nodes[node.id]

        if node.user1_id is None and node.user2_id is None:
            # No user need to be promoted as winner, the node has no user
            return None
        elif (node.user1_id is None) ^ (node.user2_id is None):
            # One of the two user is None, we need to check if one side has no children at all
            left_side = (
                has_node_without_user(dict_nodes, dict_nodes[node.next_game1.id])
                if node.next_game1 is not None
                else True
            )
            right_side = (
                has_node_without_user(dict_nodes, dict_nodes[node.next_game2.id])
                if node.next_game2 is not None
                else True
            )
            if left_side or right_side:
                if node.user_winner_id is None:
                    # Mark it in the Tree
                    node.user_winner_id = node.user1_id if node.user1_id is not None else node.user2_id
                    # Mark it in the list
                    dict_nodes[node.id].user_winner_id = node.user_winner_id
                    node_to_save[node.id] = dict_nodes[node.id]  # Will need to save in database later
                    # Need to set the user to the parent for its next match
                    return node.user_winner_id
            return
        else:
            # Both user are set, we can go to the next node
            return None

    traverse(tree)
    return list(node_to_save.values())


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


def find_people_in_and_out(list_people: List[UserInfo], team_size: int) -> tuple[List[UserInfo], List[UserInfo]]:
    """
    Find the people in and out of the tournament based on the team size.

    Args:
        list_people (List[UserInfo]): The list of people registered for the tournament.
        team_size (int): The size of the team.

    Returns:
        tuple[List[UserInfo], List[UserInfo]]: A tuple containing two lists:
            - The first list contains the people who are in the tournament.
            - The second list contains the people who are out of the tournament.
    """
    team_count = len(list_people) // team_size  # Floor division
    return list_people[: team_count * team_size], list_people[team_count * team_size :]


def build_tournament_tree(tournament: List[TournamentGame]) -> Optional[TournamentNode]:
    """
    Builds a tree structure from a list of TournamentGame objects.

    Args:
        tournament (List[TournamentGame]): A list of TournamentGame objects.

    Returns:
        Optional[TournamentNode]: The root node of the tournament tree.
    """
    if len(tournament) == 0:
        return None

    # Map to hold nodes by their ID
    nodes: Dict[int, TournamentNode] = {}

    # Step 1: Create a node for each game
    for game in tournament:
        if game.id is not None:
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
        if game.id is not None:
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
    tournament: Tournament, tournament_games: List[TournamentGame], people: List[UserInfo]
) -> List[TournamentGame]:
    """
    Assign people to tournament games. Assign to the last level of the tree but if the tree is not full, assign to the
    first level.

    Args:
        tournament (TournamentNode): The root node of the tournament tree.
        tournament_games (List[TournamentGame]): A list of tournament games.
        people (List[UserInfo]): A list of people to assign to the games.

    Returns: Node to save

    """

    # Assign people to games randomly on the last level of the tree
    leaf_nodes = [node for node in tournament_games if not node.next_game1_id and not node.next_game2_id]

    # Sort the list of leaf nodes by ID
    leaf_nodes.sort(key=lambda x: x.id if x.id is not None else 0)

    # Reduce the list for the number of people
    if len(leaf_nodes) > len(people):
        leaf_nodes = leaf_nodes[: len(people)]

    # Randomize the list of people
    random.shuffle(people)

    # Assign people to games by taking two persons sequentially and assigned them to a leaf node
    i_leaf = 0
    i_person = 0
    while i_leaf < len(leaf_nodes) and i_person < len(people):
        if i_person < len(people):
            leaf_nodes[i_leaf].user1_id = people[i_person].id
            i_person += 1
        if i_person < len(people):
            leaf_nodes[i_leaf].user2_id = people[i_person].id
            i_person += 1
            leaf_nodes[i_leaf].map = random.choice(tournament.maps.split(","))  # Only if 2 people
        i_leaf += 1

    # Mark the node as a winner if there is only one person
    assign_to_parent: List[TournamentGame] = []
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
        if len(parent) > 0:
            p = parent[0]
            p.user2_id = node.user_winner_id
            leaf_nodes.append(parent[0])

    return leaf_nodes


async def report_lost_tournament(tournament_id: int, user_id: int, score: str) -> Reason:
    """
    Report a user as lost in the tournament.

    Args:
        tournament_id (int): The ID of the tournament.
        user_id (int): The ID of the user.
    """
    # Get the tournament
    tournament = fetch_tournament_by_id(tournament_id)

    if tournament is None:
        return Reason(False, "The tournament does not exist.")

    # Get the list of users registered for the tournament
    participants: List[UserInfo] = get_people_registered_for_tournament(tournament_id)
    if not any(user.id == user_id for user in participants):
        return Reason(False, "User is not registered for the tournament.")

    # Get the tournament games
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

    # Get the tournament tree
    tournament_tree = build_tournament_tree(tournament_games)

    if tournament_tree is None:
        return Reason(False, "The tournament tree is empty.")

    # Find the node where the user is present
    node = find_first_node_of_user_not_done(tournament_tree, user_id)

    # If the user is already eleminated or not found in the tournament
    if node is None:
        return Reason(False, "User cannot report a lost because already eliminated.")

    if node.user1_id is None or node.user2_id is None:
        return Reason(
            False,
            "User cannot report a lost because the game is not ready: one participant is not yet determine by the system.",
        )

    # Update the user_winner_id in the node
    node.user_winner_id = node.user1_id if node.user1_id != user_id else node.user2_id

    # Update the score
    node.score = score

    # Find the parent node and assign the user
    node_parent = find_parent_of_node(tournament_tree, node.id)
    if node_parent is not None:
        # None might mean root
        # Set the winner to the parent node on an available slot
        if node_parent.user1_id is None:
            node_parent.user1_id = node.user_winner_id
        else:
            node_parent.user2_id = node.user_winner_id
        # Asign the map when both are defined
        if node_parent.user1_id is not None and node_parent.user2_id is not None:
            node_parent.map = random.choice(tournament.maps.split(","))
        # Save the updated tournament games
        save_tournament_games(
            [map_tournament_node_to_tournament_game(node), map_tournament_node_to_tournament_game(node_parent)]
        )
    else:
        save_tournament_games([map_tournament_node_to_tournament_game(node)])

    # Auto assign user as a winner if there is no possible opponent in the other side of the bracket
    # Refetch to make sure we have all the latest
    refetch_tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    node_to_save2: List[TournamentGame] = auto_assign_winner(refetch_tournament_games)
    save_tournament_games(node_to_save2)

    # Close bets of the games (mostly the one reported)
    distribute_gain_on_recent_ended_game(tournament_id)

    # Generate bet_game
    await system_generate_game_odd(tournament_id)
    return Reason(True, None, node)


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


def get_node_by_levels(root: TournamentNode) -> List[List[TournamentNode]]:
    """
    Each level are part of the visual, level 0 (is the leaves) is the most left side of the
    bracket
    """
    levels: List[List[TournamentNode]] = []
    max_depth = 0

    def traverse(node: Union[TournamentNode, None], depth: int):
        nonlocal max_depth

        if node is None:
            return

        max_depth = max(max_depth, depth)

        # Traverse left and right child nodes to determine their positions
        traverse(node.next_game1, depth + 1)
        traverse(node.next_game2, depth + 1)
        level_position = max_depth - depth
        if len(levels) <= level_position:
            levels.append([node])
        else:
            levels[max_depth - depth].append(node)

    traverse(root, depth=0)
    return levels


def get_tournament_final_result_positions(root: TournamentNode) -> Optional[TournamentResult]:
    """
    Get the final result of the tournament.
    First position, then the second position and the two third positions
    """
    levels = get_node_by_levels(root)
    if len(levels) == 0:
        return None

    final_level = levels[-1]
    if len(final_level) == 0:
        return None

    # The final node is the winner
    final_game = final_level[0]
    if final_game.user_winner_id is None:
        return None  # The tournament is not yet finished

    first_position = final_game.user_winner_id

    # The second node is the loser of the final
    second_position = final_game.user1_id if final_game.user2_id == final_game.user_winner_id else final_game.user2_id

    # The third nodes are the losers of the semi-final
    semi_finals = levels[-2]
    if len(semi_finals) != 2:
        return None

    if semi_finals[0].user_winner_id is None or semi_finals[1].user_winner_id is None:
        return None
    third_position_1 = (
        semi_finals[0].user1_id if semi_finals[0].user2_id == semi_finals[0].user_winner_id else semi_finals[0].user2_id
    )
    third_position_2 = (
        semi_finals[1].user1_id if semi_finals[1].user2_id == semi_finals[1].user_winner_id else semi_finals[1].user2_id
    )

    # Should never happen but in the case there isn't at least 4 people, we set to zero the id of the winners
    second_position = second_position if second_position is not None else 0
    third_position_1 = third_position_1 if third_position_1 is not None else 0
    third_position_2 = third_position_2 if third_position_2 is not None else 0

    return TournamentResult(
        first_place_user_id=first_position,
        second_place_user_id=second_position,
        third_place_user_id_1=third_position_1,
        third_place_user_id_2=third_position_2,
    )


def clean_maps_input(raw_maps: str) -> str:
    """
    Clean the input of maps by removing the spaces and making the string lowercase
    """
    return ",".join(map(lambda x: x.strip().lower(), raw_maps.split(",")))
