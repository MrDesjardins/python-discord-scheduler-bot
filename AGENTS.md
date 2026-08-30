# AGENTS.md

Guidance for AI agents (Claude Code, Codex, Cursor, …) working in this repo.
The full architecture guide lives in [CLAUDE.md](CLAUDE.md); read it first.
Project rules live in `.claude/rules/`.

## Always document the reason for algorithm changes

Several algorithms in this codebase (ranked match-start detection, stats.cc
score parsing / `is_match_complete`, the match-start GIF + TribeMarkets message
handoff, the delayed TribeMarkets reconciliation, the player-value jobs) look
simple but encode hard-won decisions from real production incidents. Changing
them "to clean up" has repeatedly reintroduced old bugs.

Whenever you change one of these algorithms — or any non-obvious heuristic,
threshold, or ordering — you MUST record **why**:

1. A commit message that states the observed problem, the root cause, and why
   the new behaviour is correct (not just *what* changed).
2. A code comment at the decision point naming the failure it prevents. When it
   fixes a specific past regression, reference the earlier commit hash.
3. If the change reverses or narrows a previous deliberate decision, say so
   explicitly and explain what new information justifies it.

Before editing such an algorithm, check `git log -p` / `git blame` on the lines
and the surrounding comments for the prior rationale. If you cannot find a
documented reason for the current behaviour, add one as part of your change.
