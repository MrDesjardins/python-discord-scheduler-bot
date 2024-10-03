"""
Create Fake Data for Testing Analytics
"""

from datetime import datetime


# pylint: disable=import-error
# pylint: disable=wrong-import-position
from deps.analytic import set_database_name
from deps.analytic_gatherer import (
    EVENT_CONNECT,
    EVENT_DISCONNECT,
    compute_users_weights,
    delete_all_tables,
    fetch_user_activity,
    log_activity,
)
from deps.analytic_visualizer import (
    display_graph_cluster_people,
    display_graph_cluster_people_3d_animated,
)

# set_database_name("user_activity.test.db")
# GENERATE_FAKE_DATA = True
set_database_name("user_activity.db")
GENERATE_FAKE_DATA = False

if GENERATE_FAKE_DATA:
    CHANNEL1_ID = 100
    CHANNEL2_ID = 200
    GUILD_ID = 1000
    delete_all_tables()

    # log_activity(
    #     1,
    #     "user_1",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_CONNECT,
    #     datetime(2024, 9, 20, 13, 18, 0, 6318),
    # )
    log_activity(
        10,
        "user_10",
        CHANNEL2_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 6318),
    )
    log_activity(
        11,
        "user_11",
        CHANNEL2_ID,
        GUILD_ID,
        EVENT_CONNECT,
        datetime(2024, 9, 20, 13, 20, 0, 6318),
    )
    # log_activity(
    #     2,
    #     "user_2",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_CONNECT,
    #     datetime(2024, 9, 20, 13, 20, 0, 6318),
    # )
    # log_activity(
    #     3,
    #     "user_3",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_CONNECT,
    #     datetime(2024, 9, 20, 13, 21, 0, 6318),
    # )

    # log_activity(
    #     2,
    #     "user_2",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_DISCONNECT,
    #     datetime(2024, 9, 20, 13, 30, 0, 6318),
    # )
    # log_activity(
    #     4,
    #     "user_4",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_CONNECT,
    #     datetime(2024, 9, 20, 13, 31, 0, 6318),
    # )
    # log_activity(
    #     3,
    #     "user_3",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_DISCONNECT,
    #     datetime(2024, 9, 20, 13, 32, 0, 6318),
    # )
    # log_activity(
    #     4,
    #     "user_4",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_DISCONNECT,
    #     datetime(2024, 9, 20, 13, 33, 0, 6318),
    # )
    # log_activity(
    #     1,
    #     "user_1",
    #     CHANNEL1_ID,
    #     GUILD_ID,
    #     EVENT_DISCONNECT,
    #     datetime(2024, 9, 20, 13, 38, 0, 6318),
    # )

    # log_activity(
    #     1,
    #     "user_1",
    #     CHANNEL2_ID,
    #     GUILD_ID,
    #     EVENT_CONNECT,
    #     datetime(2024, 9, 20, 13, 45, 0, 6318),
    # )
    log_activity(
        10,
        "user_10",
        CHANNEL2_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 50, 0, 6318),
    )
    log_activity(
        11,
        "user_11",
        CHANNEL2_ID,
        GUILD_ID,
        EVENT_DISCONNECT,
        datetime(2024, 9, 20, 13, 50, 0, 6318),
    )
    # log_activity(
    #     1,
    #     "user_1",
    #     CHANNEL2_ID,
    #     GUILD_ID,
    #     EVENT_DISCONNECT,
    #     datetime(2024, 9, 20, 13, 50, 0, 6318),
    # )

activity_data = fetch_user_activity()
activity_data = filter(lambda x: x.user_id in (357551747146842124, 755175712268353599), activity_data) # Pat, Joe
[print(d) for d in activity_data]
user_weights = compute_users_weights(activity_data)
print(user_weights)


# Expected output:
# User 1 and user 2 spent 10 minutes together: 600 seconds
# User 1 and user 3 spent 11 minutes together: 660 seconds
# User 1 and user 4 spent 2 minutes together: 120 seconds
# User 2 and user 3 spent 9 minutes together: 540 seconds
# User 2 and user 4 spent 0 minutes together: 0 seconds
# User 3 and user 4 spent 1 minutes together: 60 seconds

# Redo with the database:
# calculate_time_spent_from_db(6000, 0)
# display_graph_network_relationship()

# display_graph_cluster_people()
# display_graph_cluster_people_3d_animated()
