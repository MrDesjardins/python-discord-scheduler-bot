"""
Siege functions logics
"""

from types import SimpleNamespace
from typing import Union
from unittest.mock import Mock, patch

from deps.models import ActivityTransition
from deps.siege import (
    get_adjacent_rank_names,
    get_aggregation_siege_activity,
    format_lfg_message,
    get_guild_rank_emoji,
    get_lfg_rank_role_mentions,
    get_lfg_user_mentions,
    get_user_rank_siege,
)


def test_get_aggregation_siege_activity_no_data() -> None:
    """
    Test the case where there isn't any data
    """
    dict_users_activities: dict[int, ActivityTransition] = {}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_user_rank_siege_prefers_highest_rank_role() -> None:
    """When Unranked is kept alongside a competitive rank, use the competitive rank."""
    unranked_role = SimpleNamespace(name="Unranked")
    bronze_role = SimpleNamespace(name="Bronze")
    member = Mock(bot=False, roles=[unranked_role, bronze_role])

    assert get_user_rank_siege(member) == "Bronze"


def test_get_guild_rank_emoji_uses_unranked_icon() -> None:
    """Unranked rank displays the Unranked guild emoji."""
    guild_emoji = {"Unranked": "1234567890"}
    assert get_guild_rank_emoji(guild_emoji, "Unranked") == "<:Unranked:1234567890>"


def test_get_lfg_rank_role_mentions_unranked_only() -> None:
    """Unranked LFG pings only the Unranked role."""
    guild = Mock()
    guild.roles = [
        SimpleNamespace(name="Copper", mention="<@&Copper>"),
        SimpleNamespace(name="Unranked", mention="<@&Unranked>"),
    ]
    member = Mock(bot=False, roles=[guild.roles[1]])

    assert get_lfg_rank_role_mentions(guild, [member]) == "<@&Unranked>"


def test_get_adjacent_rank_names_uses_ranked_queue_compatibility_table() -> None:
    """LFG rank mentions follow the ranked queue compatibility table."""
    assert get_adjacent_rank_names("Copper") == ["Copper", "Bronze", "Silver", "Gold"]
    assert get_adjacent_rank_names("Bronze") == ["Copper", "Bronze", "Silver", "Gold", "Platinum"]
    assert get_adjacent_rank_names("Silver") == ["Copper", "Bronze", "Silver", "Gold", "Platinum", "Emerald"]
    assert get_adjacent_rank_names("Gold") == [
        "Copper",
        "Bronze",
        "Silver",
        "Gold",
        "Platinum",
        "Emerald",
        "Diamond",
    ]
    assert get_adjacent_rank_names("Platinum") == [
        "Bronze",
        "Silver",
        "Gold",
        "Platinum",
        "Emerald",
        "Diamond",
        "Champion",
    ]
    assert get_adjacent_rank_names("Emerald") == ["Silver", "Gold", "Platinum", "Emerald", "Diamond", "Champion"]
    assert get_adjacent_rank_names("Diamond") == ["Gold", "Platinum", "Emerald", "Diamond", "Champion"]
    assert get_adjacent_rank_names("Champion") == ["Platinum", "Emerald", "Diamond", "Champion"]


def test_get_adjacent_rank_names_boundaries() -> None:
    """Boundary ranks only include available neighbors."""
    assert get_adjacent_rank_names("Unranked") == ["Unranked"]


def test_get_lfg_rank_role_mentions_uses_group_compatibility_intersection() -> None:
    """Mixed-rank groups ping ranks compatible with every current voice member."""
    role_names = ["Champion", "Diamond", "Emerald", "Platinum", "Gold", "Silver", "Bronze", "Copper", "Unranked"]
    guild = Mock()
    guild.roles = [SimpleNamespace(name=role_name, mention=f"<@&{role_name}>") for role_name in role_names]

    diamond_role = SimpleNamespace(name="Diamond")
    platinum_role = SimpleNamespace(name="Platinum")
    member_1 = Mock(bot=False, roles=[diamond_role])
    member_2 = Mock(bot=False, roles=[platinum_role])

    assert get_lfg_rank_role_mentions(guild, [member_1]) == (
        "<@&Gold> <@&Platinum> <@&Emerald> <@&Diamond> <@&Champion>"
    )
    assert get_lfg_rank_role_mentions(guild, [member_1, member_2]) == (
        "<@&Gold> <@&Platinum> <@&Emerald> <@&Diamond> <@&Champion>"
    )


def test_get_lfg_rank_role_mentions_returns_empty_when_group_has_no_compatible_rank() -> None:
    """If current voice members cannot rank-queue together, no rank role should be pinged."""
    role_names = ["Champion", "Diamond", "Emerald", "Platinum", "Gold", "Silver", "Bronze", "Copper", "Unranked"]
    guild = Mock()
    guild.roles = [SimpleNamespace(name=role_name, mention=f"<@&{role_name}>") for role_name in role_names]

    copper_role = SimpleNamespace(name="Copper")
    champion_role = SimpleNamespace(name="Champion")
    copper_member = Mock(bot=False, roles=[copper_role])
    champion_member = Mock(bot=False, roles=[champion_role])

    assert get_lfg_rank_role_mentions(guild, [copper_member, champion_member]) == ""


def test_format_lfg_message_lists_users_before_rank_mentions() -> None:
    """LFG messages mention players first, then compatible rank roles."""
    assert (
        format_lfg_message("@Alice, @Bob", "<@&Gold> <@&Platinum>", "are looking for 2 teammates to play in <#123>")
        == "@Alice, @Bob <@&Gold> <@&Platinum> are looking for 2 teammates to play in <#123>"
    )
    assert format_lfg_message("@Alice", "", "is in the voice channel: <#123> and need 4 more people.") == (
        "@Alice is in the voice channel: <#123> and need 4 more people."
    )


def test_get_lfg_user_mentions_skips_bots_and_includes_rank_emoji() -> None:
    """LFG user lists exclude bots and show each member's rank emoji."""
    human = Mock(bot=False, mention="<@111>", roles=[])
    bot_member = Mock(bot=True, mention="<@999>", roles=[])
    bot = Mock(guild_emoji={1: {}})
    with patch("deps.siege.get_user_rank_emoji", return_value=":Bronze:"):
        assert get_lfg_user_mentions(bot, [human, bot_member], 1) == ":Bronze: <@111>"


def test_get_aggregation_siege_activity_none_entry() -> None:
    """
    Test the case where a None is part of the dictionary
    """
    dict_users_activities: dict[int, Union[ActivityTransition, None]] = {1: None}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_no_after() -> None:
    """
    Test the case where before activity is none and after is not
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, None)}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 1
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_in_menu() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_playing_map_training() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "Playing Map Training")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_playing_shooting_range() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "Playing SHOOTING RANGE")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_arcade() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "ARCADE match 1 of 2")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_no_before_after_ai() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition(None, "VERSUS AI match 1 of 2")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_no_after() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", None)}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 1
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_1() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Playing SHOOTING RANGE", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_2() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("Playing Map Training", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_3() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("ARCADE Match ...", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_4() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("VERSUS AI ...", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 1
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_5() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("RANKED match", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 1
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_6() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("STANDARD match", "in MENU")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 1
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 1
    assert result.playing_rank == 0
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_7() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", "RANKED match")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 1
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_before_but_after_in_menu_8() -> None:
    """
    Test the case where before activity is none and after is defined
    """
    dict_users_activities: dict[int, ActivityTransition] = {1: ActivityTransition("in Menu", "STANDARD match")}
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 0
    assert result.playing_standard == 1
    assert result.looking_ranked_match == 0


def test_get_aggregation_siege_activity_looking_for_ranked_match() -> None:
    """
    Test the case where a user transitions from Looking for RANKED match to RANKED match (match starts)
    """
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Looking for RANKED match", "RANKED match")
    }
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 0
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 1  # Now in ranked match
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 1  # Match just started


def test_get_aggregation_siege_activity_looking_for_ranked_match_multiple_users() -> None:
    """
    Test the case where multiple users just started a ranked match
    """
    dict_users_activities: dict[int, ActivityTransition] = {
        1: ActivityTransition("Looking for RANKED match", "RANKED match"),
        2: ActivityTransition("Looking for RANKED match", "RANKED match"),
        3: ActivityTransition("in MENU", "Playing Map Training"),
    }
    result = get_aggregation_siege_activity(dict_users_activities)
    assert result.count_in_menu == 0
    assert result.game_not_started == 0
    assert result.user_leaving == 0
    assert result.warming_up == 1
    assert result.done_warming_up_waiting_in_menu == 0
    assert result.done_match_waiting_in_menu == 0
    assert result.playing_rank == 2  # Two users now in ranked match
    assert result.playing_standard == 0
    assert result.looking_ranked_match == 2  # Two matches just started
