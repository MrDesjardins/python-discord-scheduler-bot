"""
Functions that compute statistics on the data and return the results to a message
"""

import io
import discord
from datetime import date, datetime, timedelta, timezone
from deps.functions_date import get_now_eastern
from deps.analytic_visualizer import display_user_top_operators
from deps.analytic_functions import compute_users_voice_channel_time_sec, computer_users_voice_in_out
from deps.analytic_data_access import (
    data_access_fetch_ace_4k_3k,
    data_access_fetch_avg_kill_match,
    data_access_fetch_best_duo,
    data_access_fetch_best_trio,
    data_access_fetch_clutch_win_rate,
    data_access_fetch_first_death,
    data_access_fetch_first_kill,
    data_access_fetch_kd_by_user,
    data_access_fetch_match_played_count_by_user,
    data_access_fetch_rollback_count_by_user,
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


async def send_daily_stats_to_a_guild(guild: discord.Guild):
    """
    Send the daily schedule stats to a specific guild
    """
    guild_id = guild.id
    DAY_7 = 7
    DAY_14 = 14
    DAY_30 = 30
    DAY_60 = 60
    channel_id = await data_access_get_main_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_daily_stats_to_a_guild: Channel id (main text) not found for guild {guild.name}. Skipping."
        )
        return
    today = get_now_eastern().date()
    last_7_days = today - timedelta(days=DAY_7)
    last_14_days = today - timedelta(days=DAY_14)
    last_30_days = today - timedelta(days=DAY_30)
    last_60_days = today - timedelta(days=DAY_60)
    first_day_current_year = datetime(today.year, 1, 1, tzinfo=timezone.utc)

    function_number = get_rotated_number_from_current_day(14)
    if function_number == 0:
        msg = stats_rank_match_count(DAY_14, last_14_days)
    elif function_number == 1:
        msg = stats_kd(DAY_14, last_14_days)
    elif function_number == 2:
        msg = stats_first_death(DAY_30, last_30_days)
    elif function_number == 3:
        msg = stats_first_kill(DAY_30, last_30_days)
    elif function_number == 2:
        msg = stats_ratio_first_kill_death(DAY_30, last_30_days)
    elif function_number == 5:
        msg = stats_user_best_trio(DAY_30, last_30_days)
    elif function_number == 6:
        msg = stats_rollback(DAY_14, last_14_days)
    elif function_number == 7:
        msg = stats_ratio_clutch(DAY_60, last_60_days)
    elif function_number == 8:
        msg = stats_tk_count(first_day_current_year)
    elif function_number == 9:
        msg = stats_average_kill_match(DAY_14, last_14_days)
    elif function_number == 10:
        msg = stats_user_time_voice_channel(DAY_7)
    elif function_number == 11:
        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        if channel is None:
            print_error_log(f"\t⚠️ send_daily_stats_to_a_guild: Channel not found for guild {guild.name}. Skipping.")
            return
        msg, file = await stats_ops_by_members(last_14_days)
        await channel.send(file=file, content=msg)
        return
    elif function_number == 12:
        msg = stats_user_best_duo(DAY_30, last_30_days)
    elif function_number == 13:
        msg = stats_ace_count(DAY_60, last_60_days)
    else:
        print_log("send_daily_stats_to_a_guild: No stats to show for random number {random_number}")
        return
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"\t⚠️ send_daily_stats_to_a_guild: Channel not found for guild {guild.name}. Skipping.")
        return
    await channel.send(content=msg)


def stats_rank_match_count(day: int, last_7_days: date) -> str:
    """Create a message that show the total amount of rank match played"""
    stats = data_access_fetch_match_played_count_by_user(last_7_days)
    msg = build_msg_stats_key_value_decimal("rank matches", f"in the last {day} days", stats)
    return msg


def stats_kd(day: int, last_7_days: date) -> str:
    """Create a message that show the total amount of k/d"""
    stats = data_access_fetch_kd_by_user(last_7_days)
    if len(stats) == 0:
        print_log("No kd stats to show")
        return
    stats = [(tk[0], tk[1], round(tk[2], 2)) for tk in stats]
    msg = build_msg_stats_key_value_decimal("K/D", f"in the last {day} days", stats)
    return msg


def stats_rollback(day: int, last_7_days: date) -> str:
    """The count of rollback in the last 7 days"""
    stats = data_access_fetch_rollback_count_by_user(last_7_days)
    if len(stats) == 0:
        print_log("No rollback stats to show")
        return
    msg = build_msg_stats_key_value_decimal("rollbacks", f"in the last {day} days", stats, False)
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
    data_user_activity = fetch_all_user_activities(7, 0)
    data_user_id_name = fetch_user_info()
    auser_in_outs = computer_users_voice_in_out(data_user_activity)
    user_times = compute_users_voice_channel_time_sec(auser_in_outs)

    # Convert seconds to hours for all users
    user_times_in_hours = {user: time_sec / 3600 for user, time_sec in user_times.items()}

    # Sort users by total time in descending order and select the top N
    sorted_users = sorted(user_times_in_hours.items(), key=lambda x: x[1], reverse=True)[:10]

    # Get the display name of the user to create a list of tuple with id, username and time
    stats = [(user_id, data_user_id_name[user_id].display_name, round(time, 2)) for user_id, time in sorted_users]
    msg = build_msg_stats_key_value_decimal("hours in voice channels", f"in the last {day} days", stats)
    return msg


def stats_tk_count(last_date: datetime) -> str:
    """Amount of TK since the beginning of the year"""

    stats = data_access_fetch_tk_count_by_user(last_date)
    if len(stats) == 0:
        print_log("No tk stats to show")
        return
    msg = build_msg_stats_key_value_decimal("TK", f"since the beginning of {last_date.year}", stats)
    return msg


async def stats_ops_by_members(last_7_days: date) -> tuple[str, discord.File]:
    """
    Return a msg and an image of a matrix of the user and operatoors
    """
    img_bytes = display_user_top_operators(last_7_days, False)
    msg = "📊 **Stats of the day: Top Operators**\nHere is the top 10 operators in the last 7 days"
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


def build_msg_stats_key_value_decimal(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[int, str, int]], decimal_precision: bool = True
) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 20
    COL_WIDTH = 24
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    previous_value = -1
    msg += f"{columnize('#', 3)}"f"{columnize('Name', COL_WIDTH)}"f"{columnize('Count', COL_WIDTH)}\n"
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if previous_value != stat[2]:
            rank += 1
            previous_value = stat[2]

        value = f"{stat[2]:.3f}" if decimal_precision else stat[2]
        msg += f"{columnize(rank,3)}{columnize(stat[1], COL_WIDTH)}{columnize(value, COL_WIDTH)}\n"
    msg += "```"
    return msg


def columnize(ssss: str, width: int) -> str:
    """Ensure the returned string is of the width"""
    return str(ssss).ljust(width)[:width]


def build_msg_stats_duo(stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, str, int, int, int]]) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 15
    COL_WIDTH = 12
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Game Count', COL_WIDTH)}"
        f"{columnize('Win Count', COL_WIDTH)}"
        f"{columnize('Win Rate', COL_WIDTH)}\n"
    )
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if win_rate != stat[4]:
            rank += 1
            win_rate = stat[4]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(stat[1], COL_WIDTH)}{columnize(stat[2], COL_WIDTH)}{columnize(stat[3],COL_WIDTH)}{columnize(f'{stat[4]:.3f}', COL_WIDTH)}\n"
    msg += "```"
    return msg


def build_msg_stats_trio(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, str, str, int, int, int]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 15
    COL_WIDTH = 12
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Game Count', COL_WIDTH)}"
        f"{columnize('Win Count', COL_WIDTH)}"  # Fixed: added COL_WIDTH
        f"{columnize('Win Rate', COL_WIDTH)}\n"
    )
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if win_rate != stat[5]:
            rank += 1
            win_rate = stat[5]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(stat[1], COL_WIDTH)}{columnize(stat[2], COL_WIDTH)}{columnize(stat[3],COL_WIDTH)}{columnize(stat[4],COL_WIDTH)}{columnize(f'{stat[5]:.3f}', COL_WIDTH)}\n"
    msg += "```"
    return msg


def build_msg_stats_two_counts_rate(
    stats_name: str, rate_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 20
    COL_WIDTH = 12
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    win_rate = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize(f'Count {rate_name}', COL_WIDTH)}"
        f"{columnize('Count Round', COL_WIDTH)}"
        f"{columnize('Rate', COL_WIDTH)}\n"
    )
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if win_rate != stat[3]:
            rank += 1
            win_rate = stat[3]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(stat[1], COL_WIDTH)}{columnize(stat[2], COL_WIDTH)}{columnize(f'{stat[3]:.3f}', COL_WIDTH)}\n"
    msg += "```"
    return msg


def build_msg_stats_name_percentage(stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, float]]) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 20
    COL_WIDTH = 16
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate = -1
    msg += f"{columnize('#', 3)}"f"{columnize('Name', COL_WIDTH)}"f"{columnize('Rate', COL_WIDTH)}\n"
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if last_rate != stat[1]:
            rank += 1
            last_rate = stat[1]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(f'{stat[1]:.3f}', COL_WIDTH)}\n"
    msg += "```"
    return msg


def build_msg_count_ratio_stats(
    stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, float]]
) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 20
    COL_WIDTH = 16
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('Win', COL_WIDTH)}"
        f"{columnize('Loss', COL_WIDTH)}"
        f"{columnize('Rate', COL_WIDTH)}\n"
    )
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if last_rate != stat[3]:
            rank += 1
            last_rate = stat[3]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(stat[1], COL_WIDTH)}{columnize(stat[2], COL_WIDTH)}{columnize(f'{stat[3]:.3f}', COL_WIDTH)}\n"
    msg += "```"
    return msg


def build_msg_4_counts(stats_name: str, info_time_str: str, stats_tuple: list[tuple[str, int, int, int, int]]) -> str:
    """Build a message that can be resused between the stats msg"""
    TOP = 20
    COL_WIDTH = 16
    msg = f"📊 **Stats of the day: {stats_name}**\nHere is the top {TOP} {stats_name} {info_time_str}\n```"
    rank = 0
    last_rate = -1
    msg += (
        f"{columnize('#', 3)}"
        f"{columnize('Name', COL_WIDTH)}"
        f"{columnize('5k (Ace)', COL_WIDTH)}"
        f"{columnize('4k', COL_WIDTH)}"
        f"{columnize('3k', COL_WIDTH)}"
        f"{columnize('Total', COL_WIDTH)}\n"
    )
    for stat in stats_tuple:
        if rank >= TOP:
            break
        if last_rate != stat[4]:
            rank += 1
            last_rate = stat[4]
        msg += f"{columnize(rank,3)}{columnize(stat[0], COL_WIDTH)}{columnize(stat[1], COL_WIDTH)}{columnize(stat[2], COL_WIDTH)}{columnize(f'{stat[3]}', COL_WIDTH)}{columnize(f'{stat[4]}', COL_WIDTH)}\n"
    msg += "```"
    return msg
