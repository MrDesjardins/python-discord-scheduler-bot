# Experimental stats.cc match provider

Set `MATCH_STATS_PROVIDER=statscc` in the bot environment and restart to opt in.
The default remains `tracker`. This switches match-history collection only;
profile and operator aggregate requests still use Tracker.

The client uses `https://api.stats.cc/siege/v2/profiles/{ubisoft-profile-id}/matches?playlist=ranked`,
`/matches/{match-id}`, and `/config`. These are undocumented website endpoints,
verified during the November 9, 2026 investigation. They may change.

Stored `r6_tracker_active_id` values are Ubisoft profile IDs and work here too.
Players without an ID, empty telemetry, or unsupported responses fall back to
Tracker. A failed HTTP request stops further stats.cc HTTP traffic for that batch.
Requests are serialized at least three seconds apart, with a 20 second timeout.
Each history is bounded to 20 matches; detail is fetched once per match per batch
to include operators and single-kill rounds.

Match IDs and end timestamps matched existing Tracker records in the production
comparison. The existing `(match_uuid, user_id)` duplicate protection is reused.
The recorded contract test covers a real match and the integration test verifies
all mapped fields survive SQLite insertion and retrieval.

## Coverage limits before making this the default

- stats.cc match telemetry can be absent or stale even when its Ubisoft profile
  is current. A nonempty history does not establish complete coverage. Compare
  recent playing sessions before enabling this broadly.
- Tracker's synthetic rollback records are not available as stats.cc matches.
  The adapter does not fabricate rollback entries.
- Surrender/forfeit flags come from explicit player outcomes in match detail.
  It does not infer surrender from a low score. Tracker can report disconnect
  counts differently around surrenders.
- Rankless placements stay `Unknown` with zero points so rank refresh cannot
  remove an existing role using an unranked placement record.
- Operators are deduplicated in round order; order may differ from Tracker.

This is an additional provider option, not a complete historical backfill tool.
To revert, unset `MATCH_STATS_PROVIDER` or set it to `tracker` and restart.
