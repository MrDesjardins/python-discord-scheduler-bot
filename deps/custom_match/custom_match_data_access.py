
from datetime import datetime
from deps.system_database import database_manager
from deps.models import Reason

def subscribe_custom_game(user_id: int, guild_id: int, date_subscribe: datetime ) -> Reason:
    """Subscribe a user to custom games in the specified guild."""
    query = """
        INSERT OR IGNORE INTO custom_game_user_subscription (user_id, guild_id, follow_datetime)
        VALUES (:user_id, :guild_id, :follow_datetime);
        """
    database_manager.get_cursor().execute(
        query=query,
        params={
            "user_id": user_id,
            "guild_id": guild_id,
            "follow_datetime":date_subscribe
        }
    )
    database_manager.commit()
    return Reason(True)

def fetch_user_subscription_for_guild(guild_id: int) -> list[int]:
    """Fetch all user IDs subscribed to custom games in the specified guild."""

    query = """
        SELECT user_id FROM custom_game_user_subscription
        WHERE guild_id = :guild_id;
        """
    result = database_manager.get_cursor().execute(
        query=query,
        params={"guild_id": guild_id}
    ).fetchall()
    return [row[0] for row in result]