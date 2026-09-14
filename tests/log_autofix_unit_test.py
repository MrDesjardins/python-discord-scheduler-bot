"""Unit tests for the disabled-by-default app.log automation guardrails."""

from scripts.log_autofix import (
    LogState,
    dedup_key,
    fingerprint,
    is_test_path,
    message_prefix,
    normalize_message,
    parse_log_lines,
    patch_paths,
    scrub,
    update_occurrences,
)


def test_scrub_redacts_credentials_and_personal_data() -> None:
    value = scrub({"email": "owner@example.com", "Authorization": "Bearer abc", "message": "hello"})
    assert value == {"email": "[redacted-email]", "Authorization": "[redacted]", "message": "hello"}


def test_parse_log_lines_ignores_non_matching_lines() -> None:
    text = (
        "2026-09-13 04:50:21,807 - ERROR - functions_r6_tracker: boom for user 12345\n"
        "not a log line\n"
        "2026-09-13 04:50:22,000 - INFO - all good\n"
    )
    records = parse_log_lines(text)
    assert len(records) == 2
    assert records[0].level == "ERROR"
    assert records[0].message == "functions_r6_tracker: boom for user 12345"
    assert records[1].level == "INFO"


def test_normalize_message_collapses_variable_data() -> None:
    first = normalize_message("Failed to send DM to user 12345 for user 67890")
    second = normalize_message("Failed to send DM to user 99999 for user 11111")
    assert first == second
    assert "<n>" in first


def test_fingerprint_is_stable_across_variable_ids() -> None:
    assert fingerprint("func: failed for user 111") == fingerprint("func: failed for user 222")
    assert fingerprint("func: failed for user 111") != fingerprint("other: failed for user 111")


def test_message_prefix_extracts_leading_function_name() -> None:
    assert message_prefix("functions_r6_tracker: boom") == "functions_r6_tracker"
    assert message_prefix("no prefix here") == ""


def test_dedup_key_is_stable_and_release_sensitive() -> None:
    first = dedup_key(repository="owner/repo", fp="fp", release="abc123")
    assert first == dedup_key(repository="owner/repo", fp="fp", release="abc123")
    assert first != dedup_key(repository="owner/repo", fp="fp", release="def456")


def test_update_occurrences_counts_per_release_and_resets_on_new_release() -> None:
    state = LogState(checkpoint_inode=None, checkpoint_offset=0, fingerprints={})
    records = parse_log_lines(
        "2026-09-13 04:50:21,807 - ERROR - func: boom for user 111\n"
        "2026-09-13 04:50:22,807 - ERROR - func: boom for user 222\n"
    )
    fingerprints = update_occurrences(state, records, release="abc123")
    fp = fingerprint("func: boom for user 111")
    assert fingerprints[fp]["count"] == 2
    assert fingerprints[fp]["release"] == "abc123"

    more_records = parse_log_lines("2026-09-13 04:50:23,807 - ERROR - func: boom for user 333\n")
    update_occurrences(state, more_records, release="def456")
    assert state.fingerprints[fp]["count"] == 1
    assert state.fingerprints[fp]["release"] == "def456"


def test_patch_paths_reject_escape_and_new_files() -> None:
    assert patch_paths("diff --git a/deps/example.py b/deps/example.py\n") == {"deps/example.py"}
    for invalid in (
        "diff --git a/../../secret b/../../secret\n",
        "diff --git a/deps/new.py b/deps/new.py\nnew file mode 100644\n",
        "diff --git a/scripts/log_autofix.py b/scripts/log_autofix.py\n",
        "diff --git a/frontend/app.js b/frontend/app.js\n",
    ):
        try:
            patch_paths(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError("unsafe patch should be rejected")


def test_every_patch_must_include_a_test_path() -> None:
    assert is_test_path("tests/functions_r6_tracker_unit_test.py")
    assert not is_test_path("deps/functions_r6_tracker.py")
