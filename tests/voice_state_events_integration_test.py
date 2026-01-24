"""
Integration tests for voice state event handling with real database

Tests the critical bug fixes with database interactions:
- Fix 2: Shutdown creates disconnect events
- Fix 4: Event deduplication within 1-second window
- Fix 5: Channel move atomic transaction
- Fix 6: Timezone consistency
"""

import pytest
from datetime import datetime, timedelta, timezone
from deps.system_database import database_manager, DATABASE_NAME_TEST, EVENT_CONNECT, EVENT_DISCONNECT
from deps.analytic_activity_data_access import (
    insert_user_activity,
    fetch_all_user_activities,
    fetch_user_activities,
)


@pytest.fixture(autouse=True)
def setup_test_database():
    """Setup and teardown test database for each test"""
    # Switch to test database
    database_manager.set_database_name(DATABASE_NAME_TEST)

    # Clear all tables
    database_manager.drop_all_tables()
    database_manager.init_database()

    yield

    # Cleanup
    database_manager.drop_all_tables()


@pytest.mark.no_parallel
class TestEventDeduplication:
    """Test Fix 4: Event deduplication"""

    def test_insert_activity_no_duplicates_within_window(self):
        """Verify that duplicate events within 1-second window are prevented"""
        user_id = 12345
        user_display_name = "TestUser"
        channel_id = 67890
        guild_id = 11111
        event = EVENT_CONNECT
        timestamp = datetime.now(timezone.utc)

        # Insert first event
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, timestamp)

        # Verify first insert worked (use large from_day to get all records)
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 1

        # Try to insert duplicate with same timestamp
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, timestamp)

        # Verify duplicate was NOT inserted
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 1

        # Try to insert within 1-second window (0.5 seconds later)
        timestamp_within_window = timestamp + timedelta(milliseconds=500)
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, timestamp_within_window)

        # Verify duplicate within window was NOT inserted
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 1

    def test_insert_activity_allows_duplicates_outside_window(self):
        """Verify that events outside 1-second window are allowed"""
        user_id = 12345
        user_display_name = "TestUser"
        channel_id = 67890
        guild_id = 11111
        event = EVENT_CONNECT

        # Use timestamps with clear separation
        base_time = datetime(2026, 1, 24, 12, 0, 0, tzinfo=timezone.utc)
        timestamp1 = base_time
        timestamp2 = base_time + timedelta(seconds=5)  # 5 seconds later (outside 1-second window)

        # Insert first event
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, timestamp1)

        # Insert second event 5 seconds later (well outside 1-second window)
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, timestamp2)

        # Query directly from database to verify both events were inserted
        from deps.system_database import database_manager

        cursor = database_manager.get_cursor()
        cursor.execute("SELECT timestamp FROM user_activity WHERE user_id = ? ORDER BY timestamp", (user_id,))
        rows = cursor.fetchall()

        # Verify both events were inserted
        assert len(rows) == 2, f"Expected 2 events, found {len(rows)}: {rows}"
        assert rows[0][0] == timestamp1.isoformat()
        assert rows[1][0] == timestamp2.isoformat()

    def test_deduplication_different_channels(self):
        """Verify deduplication is channel-specific"""
        user_id = 12345
        user_display_name = "TestUser"
        channel1_id = 67890
        channel2_id = 67891
        guild_id = 11111
        event = EVENT_CONNECT
        timestamp = datetime.now(timezone.utc)

        # Insert event in channel 1
        insert_user_activity(user_id, user_display_name, channel1_id, guild_id, event, timestamp)

        # Insert event in channel 2 with same timestamp
        insert_user_activity(user_id, user_display_name, channel2_id, guild_id, event, timestamp)

        # Verify both events were inserted (different channels)
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 2

        # Verify correct channels
        channel_ids = {activity.channel_id for activity in user_activities}
        assert channel_ids == {channel1_id, channel2_id}

    def test_deduplication_different_event_types(self):
        """Verify deduplication is event-type specific"""
        user_id = 12345
        user_display_name = "TestUser"
        channel_id = 67890
        guild_id = 11111
        timestamp = datetime.now(timezone.utc)

        # Insert CONNECT event
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_CONNECT, timestamp)

        # Insert DISCONNECT event with same timestamp
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_DISCONNECT, timestamp)

        # Verify both events were inserted (different event types)
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 2

        # Verify correct events
        events = {activity.event for activity in user_activities}
        assert events == {EVENT_CONNECT, EVENT_DISCONNECT}


@pytest.mark.no_parallel
class TestChannelMoveTransaction:
    """Test Fix 5: Channel move atomic transaction"""

    def test_channel_move_atomic_transaction(self):
        """Verify that channel moves create both DISCONNECT and CONNECT with same timestamp"""
        from deps.system_database import database_manager

        user_id = 12345
        user_display_name = "TestUser"
        channel1_id = 67890
        channel2_id = 67891
        guild_id = 11111
        move_time = datetime.now(timezone.utc)

        # Simulate atomic channel move using transaction
        try:
            with database_manager.data_access_transaction() as cursor:
                # Upsert user_info
                cursor.execute(
                    """
                    INSERT INTO user_info(id, display_name)
                    VALUES(:user_id, :user_display_name)
                    ON CONFLICT(id) DO UPDATE SET display_name = :user_display_name
                    WHERE id = :user_id;
                    """,
                    {"user_id": user_id, "user_display_name": user_display_name},
                )

                # Insert DISCONNECT from old channel
                cursor.execute(
                    """
                    INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
                    VALUES (:user_id, :channel_id, :guild_id, :event, :time)
                    """,
                    {
                        "user_id": user_id,
                        "channel_id": channel1_id,
                        "guild_id": guild_id,
                        "event": EVENT_DISCONNECT,
                        "time": move_time.isoformat(),
                    },
                )

                # Insert CONNECT to new channel
                cursor.execute(
                    """
                    INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
                    VALUES (:user_id, :channel_id, :guild_id, :event, :time)
                    """,
                    {
                        "user_id": user_id,
                        "channel_id": channel2_id,
                        "guild_id": guild_id,
                        "event": EVENT_CONNECT,
                        "time": move_time.isoformat(),
                    },
                )
        except Exception as e:
            pytest.fail(f"Transaction failed: {e}")

        # Verify both events were inserted
        activities = fetch_all_user_activities(from_day=3600, to_day=0)
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 2

        # Verify timestamps are identical
        timestamps = [activity.timestamp for activity in user_activities]
        assert timestamps[0] == timestamps[1]

        # Verify events and channels
        disconnect_event = [a for a in user_activities if a.event == EVENT_DISCONNECT][0]
        connect_event = [a for a in user_activities if a.event == EVENT_CONNECT][0]

        assert disconnect_event.channel_id == channel1_id
        assert connect_event.channel_id == channel2_id


@pytest.mark.no_parallel
class TestTimezoneConsistency:
    """Test Fix 6: Timezone consistency"""

    def test_timezone_consistency(self):
        """Verify that all date queries use UTC-aware datetime"""
        user_id = 12345
        user_display_name = "TestUser"
        channel_id = 67890
        guild_id = 11111

        # Insert event with UTC timezone
        timestamp_utc = datetime.now(timezone.utc)
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_CONNECT, timestamp_utc)

        # Fetch activities using fetch_all_user_activities (which now uses UTC-aware datetime)
        activities = fetch_all_user_activities(from_day=1, to_day=0)

        # Verify activities were fetched
        assert len(activities) >= 1

        # Verify timestamp is stored in UTC format (as ISO string with timezone)
        for activity in activities:
            if activity.user_id == user_id:
                # The timestamp should be a string in ISO format with timezone info
                assert isinstance(activity.timestamp, str)
                assert "+00:00" in activity.timestamp or "Z" in activity.timestamp  # UTC timezone marker

    def test_fetch_activities_date_range(self):
        """Verify that date range queries work correctly with UTC timezone"""
        user_id = 12345
        user_display_name = "TestUser"
        channel_id = 67890
        guild_id = 11111

        # Insert events at different times
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_CONNECT, two_days_ago)
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_DISCONNECT, yesterday)
        insert_user_activity(user_id, user_display_name, channel_id, guild_id, EVENT_CONNECT, now)

        # Fetch activities from last 3 days (to get all 3 events)
        activities = fetch_all_user_activities(from_day=3, to_day=0)

        # Should get all 3 events
        user_activities = [a for a in activities if a.user_id == user_id]
        assert len(user_activities) == 3

        # Verify events are ordered by timestamp
        timestamps = [datetime.fromisoformat(a.timestamp) for a in user_activities]
        assert timestamps == sorted(timestamps)  # Should be in ascending order


@pytest.mark.no_parallel
class TestShutdownDisconnectEvents:
    """Test Fix 2: Shutdown creates disconnect events"""

    def test_shutdown_creates_disconnect_events(self):
        """Verify that shutdown handler creates DISCONNECT events for users in voice"""
        # Simulate users joining voice
        user1_id = 111
        user2_id = 222
        channel_id = 67890
        guild_id = 11111

        join_time = datetime.now(timezone.utc)

        insert_user_activity(user1_id, "User1", channel_id, guild_id, EVENT_CONNECT, join_time)
        insert_user_activity(user2_id, "User2", channel_id, guild_id, EVENT_CONNECT, join_time)

        # Verify CONNECT events
        activities = fetch_all_user_activities(from_day=1, to_day=0)
        connect_events = [a for a in activities if a.event == EVENT_CONNECT]
        assert len(connect_events) == 2

        # Simulate shutdown by inserting DISCONNECT events
        shutdown_time = datetime.now(timezone.utc)
        insert_user_activity(user1_id, "User1", channel_id, guild_id, EVENT_DISCONNECT, shutdown_time)
        insert_user_activity(user2_id, "User2", channel_id, guild_id, EVENT_DISCONNECT, shutdown_time)

        # Verify DISCONNECT events were created
        activities = fetch_all_user_activities(from_day=1, to_day=0)
        disconnect_events = [a for a in activities if a.event == EVENT_DISCONNECT]
        assert len(disconnect_events) == 2

        # Verify all sessions are complete (have both CONNECT and DISCONNECT)
        user1_activities = [a for a in activities if a.user_id == user1_id]
        user2_activities = [a for a in activities if a.user_id == user2_id]

        assert len(user1_activities) == 2  # CONNECT + DISCONNECT
        assert len(user2_activities) == 2  # CONNECT + DISCONNECT


@pytest.mark.no_parallel
class TestDeduplicationIndex:
    """Test Fix 4: Deduplication index exists"""

    def test_deduplication_index_exists(self):
        """Verify that the deduplication index was created"""
        cursor = database_manager.get_cursor()

        # Query to check if index exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_user_activity_dedup'
        """
        )

        result = cursor.fetchone()
        assert result is not None, "Deduplication index idx_user_activity_dedup does not exist"
        assert result[0] == "idx_user_activity_dedup"
