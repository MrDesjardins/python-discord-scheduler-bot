""" Constants used in the bot. """

DATE_FORMAT = "%A, %B %d, %Y"

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

## Schedule
COMMAND_SCHEDULE_ADD = "addschedule"
COMMAND_SCHEDULE_REMOVE = "removeschedule"
COMMAND_SCHEDULE_SEE = "seeschedule"

## Timezone
COMMAND_SET_USER_TIME_ZONE = "setmytimezone"
COMMAND_GET_USER_TIME_ZONE = "getusertimezone"
COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL = "gettimezones"

## Rank/Role
COMMAND_ADJUST_RANK = "adjustrank"

# -----------------------
# Moderator's commands

## Schedule
COMMAND_SCHEDULE_ADD_USER = "modadduserschedule"
COMMAND_SCHEDULE_REFRESH_FROM_REACTION = "modrefreshschedule"
COMMAND_FORCE_SEND = "modforcesendschedule"
COMMAND_SCHEDULE_APPLY = "modapplyschedule"

## Timezone
COMMAND_SET_USER_TIME_ZONE_OTHER_USER = "modsetusertimezone"

## Channels
COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL = "modtextschedulechannel"
COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL = "modseeschedulechannel"
COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL = "modtextusernamechannel"
COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL = "modseesusernamechannel"
COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL = "modvoicechannel"
COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION = "modseevoicechannels"
COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION = "modresetvoicechannel"

## Bot Behaviors
COMMAND_GUILD_ENABLE_BOT_VOICE = "modenablebotvoice"

## Analytics
COMMAND_SHOW_COMMUNITY = "modshowcommunity"
COMMAND_VERSION = "modversion"

# -----------------------
# Guild owner's commands
COMMAND_RESET_CACHE = "modresetcache"
