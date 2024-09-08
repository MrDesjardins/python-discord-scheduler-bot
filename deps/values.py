from deps.models import TimeLabel 
days_of_week = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday', 'Sunday']

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
