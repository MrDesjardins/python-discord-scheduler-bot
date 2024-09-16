days_of_week = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday', 'Sunday']

emoji_to_time = {
    '3️⃣': '3pm',
    '4️⃣': '4pm',
    '5️⃣': '5pm',
    '6️⃣': '6pm',
    '7️⃣': '7pm',
    '8️⃣': '8pm',
    '9️⃣': '9pm',
    '🔟': '10pm',
    '🕚': '11pm',
    '🕛': '12pm',
    '1️⃣': '1am',
    '2️⃣': '2am',
}

supported_times_str = set(emoji_to_time.values())

COMMAND_SCHEDULE_ADD = "addschedule"
COMMAND_SCHEDULE_REMOVE = "removeschedule"
COMMAND_SCHEDULE_SEE = "seeschedule"
COMMAND_SCHEDULE_ADD_USER = "adduserschedule"
COMMAND_SCHEDULE_CHANNEL_SELECTION = "channel"
COMMAND_SCHEDULE_REFRESH_FROM_REACTION = "refreshschedule"
COMMAND_RESET_CACHE = "resetcache"
COMMAND_SCHEDULE_CHANNEL_VOICE_SELECTION = "voicechannel"
