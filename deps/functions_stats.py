"""
Functions that compute statistics on the data and return the results to a message
"""

import io
from typing import Optional, Sequence, Union
from datetime import date, datetime, timedelta, timezone
import discord
from deps.functions_date import get_now_eastern
from deps.analytic_visualizer import display_user_top_operators
from deps.analytic_functions import compute_users_voice_channel_time_sec, computer_users_voice_in_out
from deps.analytic_data_access import (
    data_access_fetch_ace_4k_3k,
    data_access_fetch_avg_kill_match,
    data_access_fetch_best_duo,
    data_access_fetch_best_trio,
    data_access_fetch_best_worse_map,
    data_access_fetch_clutch_round_rate,
    data_access_fetch_clutch_win_rate,
    data_access_fetch_first_death,
    data_access_fetch_first_kill,
    data_access_fetch_kd_by_user,
    data_access_fetch_match_played_count_by_user,
    data_access_fetch_rollback_positive_count_by_user,
    data_access_fetch_rollback_negative_count_by_user,
    data_access_fetch_success_fragging,
    data_access_fetch_tk_count_by_user,
    fetch_all_user_activities,
    fetch_user_info,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_main_text_channel_id,
)
from deps.functions import (
    get_rotated_number_from_current_day,
)
from deps.log import print_error_log, print_log


async def send_daily_stats_to_a_guild(guild: discord.Guild, stats_number: Optional[int] = None):
    """
    Send the daily schedule stats to a specific guild
    """
    guild_id = guild.id
    day_14 = 14
    day_30 = 30
    day_60 = 60
    channel_id = await data_access_get_main_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_daily_stats_to_a_guild: Channel id (main text) not found for guild {guild.name}. Skipping."
        )
        return
    channel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"\t⚠️ send_daily_stats_to_a_guild: Channel not found for guild {guild.name}. Skipping.")
        return
    today = get_now_eastern().date()
    last_14_days = today - timedelta(days=day_14)
    last_30_days = today - timedelta(days=day_30)
    last_60_days = today - timedelta(days=day_60)
    first_day_current_year = datetime(today.year, 1, 1, tzinfo=timezone.utc)
    msg_intruction: Optional[str] = None
    if stats_number is not None:
        function_number = stats_number
    else:
        function_number = get_rotated_number_from_current_day(16)
    if function_number == 0:
        msg = stats_rank_match_count(day_14, last_14_days)
    elif function_number == 1:
        msg = stats_kd(day_14, last_14_days)
        msg_intruction = """The K/D are for matches played in or not on that server. However, it might not contain all your matches if you are not active.
The bot tracks on a daily basis the matches played by fetching the last 20 matches stats on days you visited this server. If you are playing actively elsewhere and not on this server, the stats might not be accurate.
If you are joining a voice channel about every 20 ranks matches, the stats should be accurate."""
    elif function_number == 2:
        msg = stats_first_death(day_30, last_30_days)
        msg_intruction = """The ratio means the rate of time you left your time into a 4v5 situation.
A number approachin 0.10 is normal since Siege is a 10 men game.
Above 0.10 means you are dying more often than the 9 other players.
A high number means you are taking more risk but this number should be balanced with the first kill ratio (stats we will provide another day).
As long as your first kill and first death ratio is above 0.5, you are doing a good job."""
    elif function_number == 3:
        msg = stats_first_kill(day_30, last_30_days)
    elif function_number == 4:
        msg = stats_ratio_first_kill_death(day_30, last_30_days)
        msg_intruction = """The ratio of the stats means is the rate between first kill and first death. The formula is : first kill count/(first death count + first kill count). 
So, the maximum you can have is 1.0. For example, someone got 10 first kill, 0 first death.
Someone with a ratio of 0.5 means you let your team in a 5v4 almost the same amount that you left your team in a 5v4. 
Under 0.5 means you left your team more often in a numerical disadvantage (4v5). 
Above 0.5 means you are setting your team in a advantageous position (5v4)."""
    elif function_number == 5:
        msg = stats_user_best_trio(day_30, last_30_days)
    elif function_number == 6:
        msg = stats_rollback_positive(day_14, last_14_days)
        msg_intruction = """The rollbacks stats contains only the number of rollbacks that gave you back points.
Receiving points back means you played against a cheater.
The rollbacks that removed points are not counted in this stats and will be shown another day."""
    elif function_number == 7:
        msg = stats_ratio_clutch(day_60, last_60_days)
    elif function_number == 8:
        msg = stats_tk_count(first_day_current_year)
    elif function_number == 9:
        msg = stats_average_kill_match(day_14, last_14_days)
    elif function_number == 10:
        msg = stats_user_time_voice_channel(day_14)
    elif function_number == 11:
        msg, file = await stats_ops_by_members(day_14, last_14_days)
        if file is not None:
            await channel.send(file=file, content=msg)
            return  # Needed because we have a special case where we loop channel.send a file here
    elif function_number == 12:
        msg = stats_user_best_duo(day_30, last_30_days)
    elif function_number == 13:
        msg = stats_ace_count(day_60, last_60_days)
    elif function_number == 14:
        index: Union[int, None] = 0
        safe_guard = 0
        maximum_msg_safe_guard = 4  # Max msg to send
        while index is not None and safe_guard < maximum_msg_safe_guard:
            (msg, index) = stats_best_worse_map(day_60, last_60_days, index)
            await channel.send(content=msg)
            safe_guard += 1
        if safe_guard >= maximum_msg_safe_guard:
            print_error_log(
                f"send_daily_stats_to_a_guild: Error in stats_best_worse_map with safe_guard at {safe_guard}"
            )
        return  # Needed because we have a special case where we loop channel.send
    elif function_number == 15:
        msg = stats_clutch_round_rate(day_60, last_60_days)
        msg_intruction = """The clutch rate shows the number of time a user is in a 1vX situation.
A rate around 0.1 is normal since Siege is a 5v5 game. A rate above 0.1 might mean you are more passive and a rate lower than 0.1 might indicate you are more aggressive and taking more risk."""
    elif function_number == 16:
        msg = stats_rollback_negative(day_14, last_14_days)
        msg_intruction = """The rollbacks stats contains only the number of rollbacks that you lost point points.
Losing points means you played with a cheater and the system removes the gained point from your account.
The rollbacks that added points are not counted in this stats and will be shown another day."""
    else:
        print_error_log(f"send_daily_stats_to_a_guild: No stats to show for random number {function_number}")
        return

    msg_len = len(msg)
    print_log(f"send_daily_stats_to_a_guild: Sending stats {function_number} to {guild.name} total size {msg_len}")
    await channel.send(content=msg[:1999])
    if msg_intruction is not None:
        await channel.send(content=msg_intruction)


def stats_rank_match_count(day: int, last_7_days: date) -> str:
    """Create a message that show the total amount of rank match played"""
    stats = data_access_fetch_match_played_count_by_user(last_7_days)
    msg = build_msg_stats_key_value_decimal("rank matches", f"in the last {day} days", stats, False)
    return msg


def stats_kd(day: int, last_7_days: date) -> str:
    """Create a message that show the total amount of k/d"""
    stats = data_access_fetch_kd_by_user(last_7_days)
    if len(stats) == 0:
        print_log("stats_kd: No kd stats to show")
        return "No kd stats to show"
    stats = [(tk[0], tk[1], round(tk[2], 2)) for tk in stats]
    msg = build_msg_stats_key_value_decimal("K/D", f"in the last {day} days", stats)
    return msg


def stats_rollback_positive(day: int, last_7_days: date) -> str:
    """The count of rollback in the last 7 days"""
    stats = data_access_fetch_rollback_positive_count_by_user(last_7_days)
    if len(stats) == 0:
        print_log("stats_rollback: No rollback stats to show")
        return "No rollback stats to show"
    msg = build_msg_stats_rollback("rollbacks that gave back points", f"in the last {day} days", stats)
    return msg


def stats_rollback_negative(day: int, last_7_days: date) -> str:
    """The count of rollback in the last 7 days"""
    stats = data_access_fetch_rollback_negative_count_by_user(last_7_days)
    if len(stats) == 0:
        print_log("stats_rollback: No rollback stats to show")
        return "No rollback stats to show"
    msg = build_msg_stats_rollback("rollbacks that gave removed points", f"in the last {day} days", stats)
    return msg


def stats_average_kill_match(day: int, last_7_days: date) -> str:
    """The average kill per match in the last 7 days"""
    stats = data_access_fetch_avg_kill_match(last_7_days)
    stats = [(tk[0], tk[1], round(tk[2], 2)) for tk in stats]
    msg = build_msg_stats_key_value_decimal("average kills/match ", f"in the last {day} days", stats)
    return msg


def stats_user_time_voice_channel(
    day: int,
):
    """The amount of time spent in voice channel in the last 7 days"""
    data_user_activity = fetch_all_user_activities(day, 0)
    data_user_id_name = fetch_user_info()
    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = compute_users_voice_channel_time_sec(auser_in_outs)

    # Convert seconds to hours for all users
    user_times_in_hours = {user: time_sec / 3600 for user, time_sec in user_times.items()}

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times_in_hours.items(), key=lambda x: x[1], reverse=True)[:10]

    # Get the display name of the user to create a list of tuple with id, username and time
    stats = [(user_id, data_user_id_name[user_id].display_name, round(time, 2)) for user_id, time in sorted_users]
    msg = build_msg_stats_key_value_decimal("amount of hours in voice channels", f"in the last {day} days", stats)
    return msg


def stats_tk_count(last_date: datetime) -> str:
    """Amount of TK since the beginning of the year"""

    stats = data_access_fetch_tk_count_by_user(last_date)
    if len(stats) == 0:
        print_log("stats_tk_count: No tk stats to show")
        return "No tk stats to show"
    msg = build_msg_stats_key_value_decimal("TK", f"since the beginning of {last_date.year}", stats, False)
    return msg


async def stats_ops_by_members(day: int, from_date: date) -> tuple[str, Union[discord.File, None]]:
    """
    Return a msg and an image of a matrix of the user and operatoors
    """
    img_bytes = display_user_top_operators(from_date, False)
    msg = f"📊 **Stats of the day: top Operators**\nHere is the top 10 operators in the last {day} days"
    if img_bytes is None:
        return (msg, None)
    bytesio = io.BytesIO(img_bytes)
    bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
    file = discord.File(fp=bytesio, filename="plot.png")
    return (msg, file)


def stats_user_best_duo(day: int, last_30_days: date) -> str:
    """The best duo in the last x days"""
    stats_duo = data_access_fetch_best_duo(last_30_days)
    msg = build_msg_stats_duo("best winning duo", f"in the last {day} days", stats_duo)
    return msg


def stats_user_best_trio(day: int, last_30_days: date) -> str:
    """The best trip in the last x days"""
    stats_duo = data_access_fetch_best_trio(last_30_days)
    msg = build_msg_stats_trio("best winning trio", f"in the last {day} days", stats_duo)
    return msg


def stats_first_death(day: int, last_x_day: date) -> str:
    """The first death in the last x days"""
    stats = data_access_fetch_first_death(last_x_day)
    msg = build_msg_stats_two_counts_rate("first death per round", "death", f"in the last {day} days", stats)
    return msg


def stats_first_kill(day: int, last_x_day: date) -> str:
    """The first kill in the last x days"""
    stats = data_access_fetch_first_kill(last_x_day)
    msg = build_msg_stats_two_counts_rate("first kill per round", "kill", f"in the last {day} days", stats)
    return msg


def stats_ratio_first_kill_death(day: int, last_x_day: date) -> str:
    """
    Stats that check the ratio of success frag (kill vs death)
    """
    stats = data_access_fetch_success_fragging(last_x_day)
    msg = build_msg_stats_name_percentage("first kill vs first death ratio", f"in the last {day} days", stats)
    return msg


def stats_ratio_clutch(day: int, last_x_day: date) -> str:
    """
    Stats that check the ratio of clutch success
    """
    stats = data_access_fetch_clutch_win_rate(last_x_day)
    msg = build_msg_count_ratio_stats("clutch success rate", f"in the last {day} days", stats)
    return msg


def stats_ace_count(day: int, last_x_day: date) -> str:
    """
    Stats that check the count of ace, 4k, 3k
    """
    stats = data_access_fetch_ace_4k_3k(last_x_day)
    msg = build_msg_4_counts("5k (Ace), 4k, 3k rounds", f"in the last {day} days", stats)
    return msg


def stats_clutch_round_rate(day: int, last_x_day: date) -> str:
    """
    Stats that check the count of ace, 4k, 3k
    """
    stats = data_access_fetch_clutch_round_rate(last_x_day)
    msg = build_msg_4_counts_2(
        "Clutch win, lost, total round, ratio in clutch position", f"in the last {day} days", stats
    )
    return msg


def stats_best_worse_map(day: int, last_x_day: date, index: int = 0) -> tuple[str, Union[int, None]]:
    """
    Stats to know the best and worse map of each user who has at least one match different map
    """
    stats = data_access_fetch_best_worse_map(last_x_day)
    return build_msg_2_stats_count(
        "best and worse map",
        f"in the last {day} days",
        ["User", "Most won map", "Wins", "Most lost map", "Losses"],
        stats,
        index,
    )


def build_msg_stats_rollback(
    stats_name: str, info_time_str: str, stats_tuple: Sequence[tuple[int, str, int, int]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 5
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    previous_value: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Count', col_width_data)}"
        f"{columnize('RP', col_width_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if previous_value != stat[2]:
            rank += 1
            previous_value = stat[2]

        msg += (
            f"{columnize(rank,3)}"
            f"{columnize(stat[1], col_width)}"
            f"{columnize(stat[2], col_width_data)}"
            f"{columnize(stat[3], col_width_data)}\n"
        )
    msg += "```"
    return msg


def build_msg_stats_key_value_decimal(
    stats_name: str,
    info_time_str: str,
    stats_tuple: Sequence[tuple[int, str, Union[int, float]]],
    decimal_precision: bool = True,
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 5
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    previous_value: Union[int, float] = -1
    msg += f"{columnize('#', 3)}" f"{columnize('Name', col_width)}" f"{columnize('Count', col_width_data)}\n"
    for stat in stats_tuple:
        if rank >= top:
            break
        if previous_value != stat[2]:
            rank += 1
            previous_value = stat[2]

        value = f"{stat[2]:.3f}" if decimal_precision else int(stat[2])
        msg += f"{columnize(rank,3)}{columnize(stat[1], col_width)}{columnize(value, col_width_data)}\n"
    msg += "```"
    return msg


def columnize(ssss: Union[str, int, float], width: int) -> str:
    """Ensure the returned string is of the width"""
    return str(ssss).ljust(width)[:width]


def build_msg_stats_duo(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 15
    col_width = 12
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Game Count', col_width)}"
        f"{columnize('Win Count', col_width)}"
        f"{columnize('Win Rate', col_width)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if win_rate != stat[4]:
            rank += 1
            win_rate = stat[4]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width)}{columnize(stat[2], col_width)}{columnize(stat[3],col_width)}{columnize(f'{stat[4]:.3f}', col_width)}\n"
    msg += "```"
    return msg


def build_msg_stats_trio(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, str, str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 15
    col_width = 12
    col_data = 7
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('# Game', col_data)}"
        f"{columnize('# Win', col_data)}"
        f"{columnize('Rate', col_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if win_rate != stat[5]:
            rank += 1
            win_rate = stat[5]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width)}{columnize(stat[2], col_width)}{columnize(stat[3],col_data)}{columnize(stat[4],col_data)}{columnize(f'{stat[5]:.3f}', col_data)}\n"
    msg += "```"
    return msg


def build_msg_stats_two_counts_rate(
    stats_name: str, rate_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 8
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize(f'# {rate_name}', col_width_data)}"
        f"{columnize('# Round', col_width_data)}"
        f"{columnize('Rate', col_width_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if win_rate != stat[3]:
            rank += 1
            win_rate = stat[3]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width_data)}{columnize(stat[2], col_width_data)}{columnize(f'{stat[3]:.3f}', col_width_data)}\n"
    msg += "```"
    return msg


def build_msg_stats_name_percentage(stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, float]]) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate: Union[int, float] = -1
    msg += f"{columnize('#', 3)}" f"{columnize('Name', col_width)}" f"{columnize('Rate', col_width)}\n"
    for stat in stats_tuple:
        if rank >= top:
            break
        if last_rate != stat[1]:
            rank += 1
            last_rate = stat[1]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(f'{stat[1]:.3f}', col_width)}\n"
    msg += "```"
    return msg


def build_msg_count_ratio_stats(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 7
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Win', col_width_data)}"
        f"{columnize('Loss', col_width_data)}"
        f"{columnize('Rate', col_width_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if last_rate != stat[3]:
            rank += 1
            last_rate = stat[3]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width_data)}{columnize(stat[2], col_width_data)}{columnize(f'{stat[3]:.3f}', col_width_data)}\n"
    msg += "```"
    return msg


def build_msg_4_counts(stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, int, int]]) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 5
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('5k', col_width_data)}"
        f"{columnize('4k', col_width_data)}"
        f"{columnize('3k', col_width_data)}"
        f"{columnize('Total', col_width_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if last_rate != stat[4]:
            rank += 1
            last_rate = stat[4]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width_data)}{columnize(stat[2], col_width_data)}{columnize(f'{stat[3]}', col_width_data)}{columnize(f'{stat[4]}', col_width_data)}\n"
    msg += "```"
    return msg


def build_msg_4_counts_2(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    top = 30
    col_width = 16
    col_width_data = 6
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate: Union[int, float] = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', col_width)}"
        f"{columnize('Win', col_width_data)}"
        f"{columnize('Loss', col_width_data)}"
        f"{columnize('Round', col_width_data)}"
        f"{columnize('Rate', col_width_data)}\n"
    )
    for stat in stats_tuple:
        if rank >= top:
            break
        if last_rate != stat[4]:
            rank += 1
            last_rate = stat[4]
        msg += f"{columnize(rank,3)}{columnize(stat[0], col_width)}{columnize(stat[1], col_width_data)}{columnize(stat[2], col_width_data)}{columnize(f'{stat[3]}', col_width_data)}{columnize(f'{stat[4]:.3f}', col_width_data)}\n"
    msg += "```"
    return msg


def build_msg_2_stats_count(
    stats_name: str,
    info_time_str: str,
    cols_name: list[str],
    stats_tuple: list[tuple[str, str, int, str, int]],
    start_index: int = 0,
) -> tuple[str, Union[int, None]]:
    """Build a message that has the user name, stats name, stats count, stats name, stats count"""
    top = 20
    col_name = 16
    col_width_text = 40
    col_width_count = 6
    length = 0
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {top} {stats_name} {info_time_str}\n```"
    msg += (
        f"{columnize(cols_name[0], col_name)}"
        f"{columnize(cols_name[1], col_width_text)}"
        f"{columnize(cols_name[2], col_width_count)}"
        f"{columnize(cols_name[3], col_width_text)}"
        f"{columnize(cols_name[4], col_width_count)}\n"
    )
    length += len(msg)
    for i in range(start_index, len(stats_tuple)):
        stat = stats_tuple[i]
        new_line = (
            f"{columnize(stat[0], col_name)}"
            f"{columnize(stat[1], col_width_text)}"
            f"{columnize(stat[2], col_width_count)}"
            f"{columnize(f'{stat[3]}', col_width_text)}"
            f"{columnize(f'{stat[4]}', col_width_count)}\n"
        )
        length = len(msg) + len(new_line)
        if length > 1900:  # Discord as a 4000 char limit
            msg += "```"
            return (msg, i)
        msg += new_line

    msg += "```"
    return (msg, None)
