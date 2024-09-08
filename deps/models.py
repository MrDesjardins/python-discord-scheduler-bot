from enum import Enum


class DayOfWeek(Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


days_of_week = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday', 'Sunday']


class TimeLabel:
    def __init__(self, value, label, description):
        self.value = value
        self.label = label
        self.description = description


supported_times = [
    TimeLabel('4', '4 pm', "4 pm Eastern Time"),
    TimeLabel('5', '5 pm', "5 pm Eastern Time"),
    TimeLabel('6', '6 pm', "6 pm Eastern Time"),
    TimeLabel('7', '7 pm', "7 pm Eastern Time"),
    TimeLabel('8', '8 pm', "8 pm Eastern Time"),
    TimeLabel('9', '9 pm', "9 pm Eastern Time"),
    TimeLabel('10', '10 pm', "10 pm Eastern Time"),
    TimeLabel('11', '11 pm', "11 pm Eastern Time"),
    TimeLabel('12', '12 pm', "12 pm Eastern Time"),
    TimeLabel('1', '1 am', "1 am Eastern Time"),
    TimeLabel('2', '2 am', "2 am Eastern Time"),
    TimeLabel('3', '3 am', "3 am Eastern Time")
]


def get_empty_votes():
    return {
        '4pm': [],
        '5pm': [],
        '6pm': [],
        '7pm': [],
        '8pm': [],
        '9pm': [],
        '10pm': [],
        '11pm': [],
        '12pm': [],
        '1am': [],
        '2am': [],
        '3am': [],
    }


emoji_to_time = {
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
    '3️⃣': '3am'
}


class SimpleUser:
    def __init__(self, user_id, display_name, rank_emoji):
        self.user_id = user_id
        self.display_name = display_name
        self.rank_emoji = rank_emoji

    def __str__(self):
        return f"User ID: {self.user_id}, Display Name: {self.display_name}"


class SimpleUserHour:
    def __init__(self, user: SimpleUser, hour):
        self.simpleUser = user
        self.hour = hour
