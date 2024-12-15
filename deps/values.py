""" Constants used in the bot. """

DATE_FORMAT = "%A, %B %d, %Y"

""" Stats from how long in the past """
STATS_HOURS_WINDOW_IN_PAST = 12

""" Timezone options for the bot. """
valid_time_zone_options = [
    "US/Pacific",
    "US/Central",
    "US/Eastern",
]

""" Values used in the bot. """
DAYS_OF_WEEK = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

EMOJI_TO_TIME = {
    "3️⃣": "3pm",
    "4️⃣": "4pm",
    "5️⃣": "5pm",
    "6️⃣": "6pm",
    "7️⃣": "7pm",
    "8️⃣": "8pm",
    "9️⃣": "9pm",
    "🔟": "10pm",
    "🕚": "11pm",
    "🕛": "12am",
    "1️⃣": "1am",
    "2️⃣": "2am",
}

SUPPORTED_TIMES_STR = set(EMOJI_TO_TIME.values())
MSG_UNIQUE_STRING = "What time will you play"

# -----------------------
# User's commands
## Initialization, Setup
COMMAND_INIT_USER = "setupprofile"

## Schedule
COMMAND_SCHEDULE_ADD = "addschedule"
COMMAND_SCHEDULE_REMOVE = "removeschedule"
COMMAND_SCHEDULE_SEE = "seeschedule"

## Timezone
COMMAND_SET_USER_TIME_ZONE = "setmytimezone"
COMMAND_GET_USER_TIME_ZONE = "getusertimezone"
COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL = "gettimezones"

## Game
COMMAND_LFG = "lfg"

## Rank/Role
COMMAND_MAX_RANK_USER_ACCOUNT = "setmymaxrankaccount"  # For rank
COMMAND_ACTIVE_RANK_USER_ACCOUNT = "setmyactiveaccount"  # For checking stats


# -----------------------
# Moderator's commands

## Schedule
COMMAND_SCHEDULE_ADD_USER = "modadduserschedule"
COMMAND_SCHEDULE_REFRESH_FROM_REACTION = "modrefreshschedule"
COMMAND_FORCE_SEND = "modforcesendschedule"
COMMAND_SCHEDULE_APPLY = "modapplyschedule"
COMMAND_TEST_JOIN = "modtestjoin"

## Timezone & Rank/Role
COMMAND_SET_USER_TIME_ZONE_OTHER_USER = "modsetusertimezone"
COMMAND_SET_USER_MAX_RANK_ACCOUNT_OTHER_USER = "modsetusermaxrankaccount"
COMMAND_SET_USER_ACTIVE_ACCOUNT_OTHER_USER = "modsetuseractiveaccount"

## Channels
COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL = "modtextschedulechannel"
COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL = "modseeschedulechannel"
COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL = "modtextusernamechannel"
COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL = "modseesusernamechannel"
COMMAND_SET_GAMING_SESSION_CHANNEL = "modtextgamingsessionchannel"
COMMAND_SEE_GAMING_SESSION_CHANNEL = "modseesgamingsessionchannel"
COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL = "modvoicechannel"
COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION = "modseevoicechannels"
COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION = "modresetvoicechannel"
COMMAND_SET_NEW_USER_CHANNEL = "modtextnewuserchannel"
COMMAND_SEE_NEW_USER_CHANNEL = "modseesnewuserchannel"

## Analytics
COMMAND_SHOW_COMMUNITY = "modshowcommunity"

# -----------------------
# Basic commands
COMMAND_GUILD_ENABLE_BOT_VOICE = "modenablebotvoice"  # Acts like a feature flag
COMMAND_VERSION = "modversion"
COMMAND_RESET_CACHE = "modresetcache"  # Only owner of the server can execute that one
COMMAND_STATS_MATCHES = "modstatsmatches"

# URL from TRN (third-party)
URL_TRN_PROFILE_MAIN = "https://r6.tracker.network/r6siege/profile/uplay/{account_name}"
URL_TRN_PROFILE_OVERVIEW = "https://r6.tracker.network/r6siege/profile/uplay/{account_name}/overview"
URL_TRN_RANKED_PAGE = "https://r6.tracker.network/r6siege/profile/uplay/{account_name}/matches?playlist=ranked"
URL_TRN_API_RANKED_MATCHES = (
    "https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/{account_name}?gamemode=pvp_ranked"
)


# Tournament
COMMAND_TOURNAMENT_CHANNEL_SET_CHANNEL = "modtexttournamentchannel"
COMMAND_TOURNAMENT_CHANNEL_GET_CHANNEL = "modseestournamentchannel"
COMMAND_TOURNAMENT_CREATE_TOURNAMENT = "createtournament"
COMMAND_TOURNAMENT_REGISTER_TOURNAMENT = "registertournament"
COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT = "sendscoretournament"
COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT = "seebrackettournament"
