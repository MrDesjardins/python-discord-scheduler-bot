# stats.cc match provider

The default match-history provider is now stats.cc. Set `MATCH_STATS_PROVIDER=tracker`
to temporarily opt out and use Tracker for match history.

stats.cc per-round operator classifications are also persisted and used for the
breacher and entry-fragger leaderboards. This removes those leaderboards' dependency
on Tracker's unreliable profile playstyle counters. The exact Tracker playstyle
values are not available from stats.cc, so these leaderboards use the corresponding
stats.cc playstyle rounds.

The existing daily profile snapshot still runs for unrelated legacy metrics while
those metrics are migrated to match telemetry. This prevents unrelated leaderboards
from becoming stale during the provider migration.

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

This is an incremental migration, not a complete historical backfill tool. Existing
Tracker history remains available for other features and as a fallback while stats.cc
coverage accumulates. To revert, set `MATCH_STATS_PROVIDER=tracker` and restart.

The playstyle table starts empty on an existing installation; it fills as users' new
stats.cc match histories are collected. The first fetch is intentionally limited to
the provider's recent history, so older rounds are not reconstructed retroactively.
