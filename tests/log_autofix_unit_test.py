"""Unit tests for the disabled-by-default app.log automation guardrails."""

import subprocess
from pathlib import Path
from typing import cast
from unittest.mock import patch

from scripts.log_autofix import (
    Config,
    LogState,
    chat_completion_output,
    create_worktree,
    dedup_key,
    fingerprint,
    github_paginate,
    is_test_path,
    message_prefix,
    normalize_message,
    parse_log_lines,
    patch_paths,
    read_new_log_records,
    remove_worktree,
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


def test_chat_completion_output_reports_finish_reason_when_content_is_null() -> None:
    truncated = {"choices": [{"finish_reason": "length", "message": {"content": None}}]}
    text, finish_reason = chat_completion_output(truncated)
    assert text == ""
    assert finish_reason == "length"

    complete = {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}]}
    text, finish_reason = chat_completion_output(complete)
    assert text == '{"ok": true}'
    assert finish_reason == "stop"


def test_github_paginate_follows_pages_until_a_short_page() -> None:
    page_one = [{"id": i} for i in range(100)]
    page_two = [{"id": 100}]
    with patch("scripts.log_autofix.github_request", side_effect=[page_one, page_two]) as mocked:
        results = github_paginate(cast(Config, object()), "/repos/owner/repo/pulls?state=all&per_page=100")
    assert len(results) == 101
    assert mocked.call_count == 2


def test_github_paginate_stops_at_max_pages() -> None:
    full_page = [{"id": i} for i in range(100)]
    with patch("scripts.log_autofix.github_request", return_value=full_page):
        results = github_paginate(cast(Config, object()), "/repos/owner/repo/pulls", max_pages=2)
    assert len(results) == 200


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "main")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "marker.txt").write_text("main content\n", encoding="utf-8")
    _run_git(repo, "add", "marker.txt")
    _run_git(repo, "commit", "-q", "-m", "initial")


def test_create_worktree_never_touches_the_live_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    original_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    worktree = create_worktree(repo, "automation/log-autofix/test123")
    try:
        assert worktree.exists()
        assert (worktree / "marker.txt").read_text(encoding="utf-8") == "main content\n"

        # repo_root must be completely unaffected: same branch, same HEAD, no dirty files.
        branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        assert branch == "main"
        assert head == original_head
        assert status == ""

        # Editing/committing inside the worktree must not touch repo_root's file.
        (worktree / "marker.txt").write_text("patched content\n", encoding="utf-8")
        _run_git(worktree, "add", "marker.txt")
        _run_git(worktree, "commit", "-q", "-m", "patch")
        assert (repo / "marker.txt").read_text(encoding="utf-8") == "main content\n"
    finally:
        remove_worktree(repo, worktree, "automation/log-autofix/test123")

    assert not worktree.exists()
    branches = subprocess.run(
        ["git", "branch", "--list", "automation/log-autofix/test123"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branches == ""


def test_read_new_log_records_recovers_across_two_rotations(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    backup_one = tmp_path / "app.log.1"
    backup_two = tmp_path / "app.log.2"

    # First run: only the live file exists.
    log_path.write_text("2026-09-13 00:00:00,000 - ERROR - a: first\n", encoding="utf-8")
    state = LogState(checkpoint_inode=None, checkpoint_offset=0, fingerprints={})
    first_records = read_new_log_records(log_path, state)
    assert [r.message for r in first_records] == ["a: first"]

    # Two rotations happen before the next run: the old live file becomes .2,
    # a newer file becomes .1, and a fresh (empty-of-new-errors) file takes over.
    backup_two.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")
    backup_one.write_text("2026-09-13 00:01:00,000 - ERROR - a: second\n", encoding="utf-8")
    log_path.write_text("2026-09-13 00:02:00,000 - ERROR - a: third\n", encoding="utf-8")

    # Force the checkpoint to point at backup_two's real inode, as it would
    # have if backup_two truly were the file read on the first run.
    state.checkpoint_inode = backup_two.stat().st_ino

    second_records = read_new_log_records(log_path, state)
    assert [r.message for r in second_records] == ["a: second", "a: third"]
