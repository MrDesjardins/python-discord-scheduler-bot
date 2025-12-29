import datetime
from deps.system_database import database_manager


def save_following_user(user_id_who_want_follow_id: int, user_to_follow_id: int, time: datetime.datetime) -> None:
    """
    Persist the following relationship in the database
    """

    database_manager.get_cursor().execute(
        """
    INSERT INTO user_following(user_id_who_want_follow_id, user_to_follow_id, follow_datetime)
      VALUES(:user_id_who_want_follow_id, :user_to_follow_id, :time)
      ON CONFLICT(user_id_who_want_follow_id, user_to_follow_id) DO UPDATE SET
        follow_datetime = :time
      WHERE user_id_who_want_follow_id = :user_id_who_want_follow_id AND user_to_follow_id = :user_to_follow_id;
    """,
        {
            "user_id_who_want_follow_id": user_id_who_want_follow_id,
            "user_to_follow_id": user_to_follow_id,
            "time": time,
        },
    )
    database_manager.get_conn().commit()


def remove_following_user(user_id_who_want_unfollow_id: int, user_to_unfollow_id: int) -> None:
    """
    Remove the following relationship in the database
    """

    database_manager.get_cursor().execute(
        """
    DELETE FROM user_following
      WHERE user_id_who_want_follow_id = :user_id_who_want_unfollow_id AND user_to_follow_id = :user_to_unfollow_id;
    """,
        {"user_id_who_want_unfollow_id": user_id_who_want_unfollow_id, "user_to_unfollow_id": user_to_unfollow_id},
    )
    database_manager.get_conn().commit()


def fetch_all_followed_users_by_user_id(user_id_who_follow_id: int) -> list[int]:
    """
    Fetch all the user ids followed by the given user id
    """
    cursor = database_manager.get_cursor()
    cursor.execute(
        """
    SELECT user_to_follow_id FROM user_following
      WHERE user_id_who_want_follow_id = :user_id_who_follow_id;
    """,
        {"user_id_who_follow_id": user_id_who_follow_id},
    )
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def fetch_all_followers_of_user_id(user_id_being_followed: int) -> list[int]:
    """
    Fetch all the user ids who follow the given user id
    """
    cursor = database_manager.get_cursor()
    cursor.execute(
        """
    SELECT user_id_who_want_follow_id FROM user_following
      WHERE user_to_follow_id = :user_id_being_followed;
    """,
        {"user_id_being_followed": user_id_being_followed},
    )
    rows = cursor.fetchall()
    return [row[0] for row in rows]
