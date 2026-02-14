# Chrome/Chromedriver Fix Deployment Guide

## Problem Summary
Chromedriver was exiting with status code 1 due to the systemd service having an insufficient file descriptor limit (1024). Chrome typically needs 200-400 file descriptors per instance, so it was failing to start.

## Root Cause
The `gametimescheduler.service` file was missing the `LimitNOFILE` setting, causing it to inherit the system's default soft limit of 1024.

## Changes Made

### 1. Enhanced Browser Context Manager (`deps/browser_context_manager.py`)
- Added comprehensive pre-flight environment checking
- Detects Chrome/chromedriver version mismatches
- Captures stderr output from chromedriver when it fails
- Tests chromedriver standalone startup
- Searches for and reads chromedriver log files
- Smarter retry logic (doesn't retry non-retryable errors like version mismatch)
- Better diagnostic output for troubleshooting

### 2. Updated Systemd Service File (`systemd/gametimescheduler.service`)
- Added `LimitNOFILE=65536` to provide sufficient file descriptors for Chrome

### 3. New Diagnostic Tools
- `deployment/diagnose_chrome.sh` - Comprehensive Chrome/chromedriver environment checker
- `deployment/cleanup_chrome_profiles.sh` - Cleans up orphaned Chrome profile directories

### 4. Enhanced Deployment Script (`deployment/update.sh`)
- Now automatically updates systemd service file when it changes
- Runs daemon-reload to pick up changes
- Cleans up old Chrome profiles during deployment

## Deployment Steps

### On Production Server

1. **Pull the latest code and run update script:**
   ```bash
   cd ~/code/python-discord-scheduler-bot
   git pull origin main
   ./deployment/update.sh
   ```

   This will:
   - Pull latest code
   - Install dependencies
   - Clean up old Chrome profiles
   - Update the systemd service file with LimitNOFILE=65536
   - Reload systemd daemon
   - Restart the service

2. **Verify the file descriptor limit is applied:**
   ```bash
   # Check the service is running
   sudo systemctl status gametimescheduler.service

   # Get the PID of the running bot
   PID=$(pgrep -f "bot.py" | head -1)

   # Check the file descriptor limits for that process
   cat /proc/$PID/limits | grep "open files"
   ```

   You should see:
   ```
   Max open files            65536                65536                files
   ```

3. **Monitor the logs for successful Chrome startup:**
   ```bash
   sudo journalctl -u gametimescheduler.service -f
   ```

   Look for messages like:
   ```
   Environment check: Chrome=Google Chrome 144.x.x, Chromedriver=ChromeDriver 144.x.x
   Chrome and chromedriver versions match: 144
   Launching Chrome in System-Level Xvfb environment...
   Driver attached successfully!
   ```

4. **If issues persist, run diagnostics:**
   ```bash
   ./deployment/diagnose_chrome.sh
   ```

## What to Expect After Deployment

### Success Indicators
- Chrome starts without "status code 1" errors
- Stat collection works for users leaving voice channels
- Logs show "Driver attached successfully!"
- File descriptor limit is 65536 for the bot process

### If Problems Persist

1. **Run diagnostics:**
   ```bash
   ./deployment/diagnose_chrome.sh
   ```

2. **Check for version mismatches:**
   - The diagnostic output will show if Chrome and chromedriver versions don't match
   - Update chromedriver if needed: `sudo apt install chromium-chromedriver=<matching-version>`

3. **Check recent error logs:**
   ```bash
   sudo journalctl -u gametimescheduler.service -n 100 --no-pager
   ```

4. **Manual cleanup if needed:**
   ```bash
   # Kill any orphaned processes
   sudo pkill -9 -f "google-chrome.*--remote-debugging"
   sudo pkill -9 -f chromedriver

   # Clean up old profiles
   ./deployment/cleanup_chrome_profiles.sh

   # Restart service
   sudo systemctl restart gametimescheduler.service
   ```

## Rollback Plan

If the deployment causes issues:

1. **Revert systemd changes:**
   ```bash
   git checkout HEAD~1 systemd/gametimescheduler.service
   sudo cp systemd/gametimescheduler.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl restart gametimescheduler.service
   ```

2. **Revert code changes:**
   ```bash
   git revert HEAD
   ./deployment/update.sh
   ```

## Testing After Deployment

1. **Test stat collection manually:**
   - Join a voice channel in Discord
   - Play some Rainbow Six Siege matches
   - Leave the voice channel
   - Check logs to see if stats are collected successfully

2. **Monitor for "Too many open files" errors:**
   ```bash
   sudo journalctl -u gametimescheduler.service -f | grep -i "too many"
   ```
   Should see no errors now.

## Future Maintenance

- Run `deployment/cleanup_chrome_profiles.sh` periodically (or add to cron) if Chrome profiles accumulate
- Run `deployment/diagnose_chrome.sh` after Chrome updates to verify compatibility
- Monitor file descriptor usage if stat collection volume increases significantly

## Questions or Issues?

If Chrome still fails to start after these changes:
1. Run `./deployment/diagnose_chrome.sh` and share the output
2. Check `sudo journalctl -u gametimescheduler.service -n 100` for detailed error messages
3. The enhanced error handling will now show specific issues (version mismatch, missing libraries, etc.)
