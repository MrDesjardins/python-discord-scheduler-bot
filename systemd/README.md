# systemd units

## gametimescheduler.service

The bot process itself. Installed automatically by `deployment/update.sh`.

## gametimescheduler-log-autofix.service / .timer

Guarded app.log triage: reads `app.log` for recurring `ERROR` lines, and —
only once a fingerprint repeats (`AUTO_FIX_MIN_OCCURRENCES`, default 2) —
opens one durable GitHub issue. If `AUTO_FIX_ENABLED=true`, it may additionally
ask an NVIDIA-hosted model for a fix plan and, only for a high-confidence,
low-risk, test-carrying patch that passes `black --check` / `mypy` /
`make unit-test` locally, push a branch and open a **draft** PR referencing
the issue. It never merges or deploys. See `scripts/log_autofix.py` for the
full guardrails (same shape as `privatepredictionmarket`'s
`scripts/bugsink_autofix.py`).

Patch validation (branch checkout, `make unit-test`, etc.) never touches this
live checkout — it runs in a disposable `git worktree` under `/tmp`, built
from the exact commit currently deployed, so a slow validation run can't leave
the running bot's on-disk code pointed at an unmerged candidate patch. A file
lock (also outside the repo) prevents an overlapping manual run from racing
the timer.

**Not installed by `deployment/update.sh` on its own** — `update.sh` only
keeps these two unit files in sync *after* they already exist under
`/etc/systemd/system/`, since enabling this requires secrets on the box.

### One-time setup

1. Add to the production `.env` (same file `bot.py` already loads via
   `load_dotenv()`):
   ```
   GITHUB_REPOSITORY=MrDesjardins/python-discord-scheduler-bot
   GITHUB_TOKEN=<fine-grained PAT scoped to only this repo: Contents (write),
                 Pull requests (write), Issues (write)>
   NVIDIA_API_KEY=<NVIDIA integrate.api.nvidia.com key>

   # Model used for triage/fix-plan generation. Defaults to z-ai/glm-5.3-flash
   # if unset (confirmed ~46s round trip on this account). moonshotai/kimi-k3
   # was tried first but its ~2.8T parameters make it too slow for NVIDIA's
   # shared serverless hosting: a real request timed out after 302s with a
   # 504 from NVIDIA's own gateway, not just our client-side timeout — so it
   # is not viable for this synchronous guarded-fix flow. Override to try a
   # different NVIDIA-hosted model (verify its latency first), or set
   # AUTOFIX_PROVIDER=openai + OPENAI_MODEL to use OpenAI instead.
   NVIDIA_AUTOFIX_MODEL=z-ai/glm-5.3-flash

   # Guarded by default — set to true only once you've reviewed a few
   # triage-only runs (AUTO_FIX_ENABLED=false) and trust the output:
   AUTO_FIX_ENABLED=false
   AUTO_FIX_MIN_OCCURRENCES=2
   AUTO_FIX_MIN_CONFIDENCE=0.85
   AUTO_FIX_MAX_ISSUES=20
   AUTO_FIX_MAX_PRS=1
   AUTO_FIX_MAX_DAILY_PRS=3
   ```
   The box's git remote must also have push access (not just the read access
   `deployment/update.sh`'s `git pull` needs), since the guarded flow pushes
   an `automation/log-autofix/<key>` branch when it opens a PR.

2. Install and enable:
   ```bash
   sudo cp systemd/gametimescheduler-log-autofix.service /etc/systemd/system/
   sudo cp systemd/gametimescheduler-log-autofix.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now gametimescheduler-log-autofix.timer
   ```

3. Verify:
   ```bash
   systemctl list-timers gametimescheduler-log-autofix.timer
   sudo systemctl start gametimescheduler-log-autofix.service  # run once now
   journalctl -u gametimescheduler-log-autofix.service -n 50
   cat artifacts/log-autofix/report.json
   ```

From then on, `deployment/update.sh` keeps both unit files current on every
deploy, same as `gametimescheduler.service`.
