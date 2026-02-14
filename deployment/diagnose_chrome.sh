#!/bin/bash
# Diagnostic script for Chrome/chromedriver issues
# Run this on the production server to diagnose browser startup problems

set -e

echo "=== Chrome/Chromedriver Diagnostic Tool ==="
echo ""

# Check Chrome
echo "1. Checking Chrome binary..."
if [ -f "/usr/bin/google-chrome" ]; then
    echo "   ✓ Chrome binary exists"
    if [ -x "/usr/bin/google-chrome" ]; then
        echo "   ✓ Chrome binary is executable"
        /usr/bin/google-chrome --version 2>&1 || echo "   ✗ Chrome version check failed"
    else
        echo "   ✗ Chrome binary is NOT executable"
        ls -l /usr/bin/google-chrome
    fi
else
    echo "   ✗ Chrome binary NOT FOUND at /usr/bin/google-chrome"
fi
echo ""

# Check Chromedriver
echo "2. Checking Chromedriver binary..."
if [ -f "/usr/bin/chromedriver" ]; then
    echo "   ✓ Chromedriver binary exists"
    if [ -x "/usr/bin/chromedriver" ]; then
        echo "   ✓ Chromedriver binary is executable"
        /usr/bin/chromedriver --version 2>&1 || echo "   ✗ Chromedriver version check failed"
    else
        echo "   ✗ Chromedriver binary is NOT executable"
        ls -l /usr/bin/chromedriver
    fi
else
    echo "   ✗ Chromedriver binary NOT FOUND at /usr/bin/chromedriver"
fi
echo ""

# Test chromedriver startup
echo "3. Testing chromedriver standalone startup..."
timeout 2s /usr/bin/chromedriver --port=9999 2>&1 &
CHROME_PID=$!
sleep 1
if kill -0 $CHROME_PID 2>/dev/null; then
    echo "   ✓ Chromedriver started successfully"
    kill $CHROME_PID 2>/dev/null || true
else
    echo "   ✗ Chromedriver failed to start or exited immediately"
    wait $CHROME_PID
    echo "   Exit code: $?"
fi
echo ""

# Check shared library dependencies
echo "4. Checking Chrome shared library dependencies..."
ldd /usr/bin/google-chrome | grep "not found" && echo "   ✗ Missing dependencies!" || echo "   ✓ All dependencies found"
echo ""

echo "5. Checking Chromedriver shared library dependencies..."
ldd /usr/bin/chromedriver | grep "not found" && echo "   ✗ Missing dependencies!" || echo "   ✓ All dependencies found"
echo ""

# Check Xvfb
echo "6. Checking Xvfb..."
if command -v xvfb-run >/dev/null 2>&1; then
    echo "   ✓ xvfb-run is installed"
    xvfb-run --help >/dev/null 2>&1 && echo "   ✓ xvfb-run is working" || echo "   ✗ xvfb-run failed"
else
    echo "   ✗ xvfb-run NOT FOUND"
fi
echo ""

# Check file descriptor limits
echo "7. Checking file descriptor limits..."
echo "   Current soft limit: $(ulimit -Sn)"
echo "   Current hard limit: $(ulimit -Hn)"
CURRENT_FDS=$(ls -1 /proc/$$/fd | wc -l)
echo "   Current FDs in use: $CURRENT_FDS"
echo ""

# Check for orphaned processes
echo "8. Checking for orphaned Chrome processes..."
CHROME_PROCS=$(pgrep -f "google-chrome.*--remote-debugging" | wc -l)
DRIVER_PROCS=$(pgrep -f "chromedriver" | wc -l)
echo "   Chrome processes: $CHROME_PROCS"
echo "   Chromedriver processes: $DRIVER_PROCS"
if [ $CHROME_PROCS -gt 0 ] || [ $DRIVER_PROCS -gt 0 ]; then
    echo "   ⚠ Warning: Found orphaned processes (may need cleanup)"
fi
echo ""

# Check /tmp for old profile directories
echo "9. Checking /tmp for old Chrome profile directories..."
OLD_PROFILES=$(find /tmp -maxdepth 1 -name 'chrome_profile_*' -mmin +60 2>/dev/null | wc -l)
echo "   Old profile directories (>60 min): $OLD_PROFILES"
if [ $OLD_PROFILES -gt 0 ]; then
    echo "   ⚠ Warning: Found old profile directories (may need cleanup)"
    find /tmp -maxdepth 1 -name 'chrome_profile_*' -mmin +60 2>/dev/null | head -5
fi
echo ""

# Check recent chromedriver logs
echo "10. Checking for recent chromedriver logs..."
RECENT_LOGS=$(find /tmp -name 'chromedriver*.log' -mmin -10 2>/dev/null)
if [ -n "$RECENT_LOGS" ]; then
    echo "   Found recent logs:"
    echo "$RECENT_LOGS"
    for log in $RECENT_LOGS; do
        echo "   --- Last 10 lines of $log ---"
        tail -10 "$log" 2>/dev/null || echo "   (could not read)"
    done
else
    echo "   No recent chromedriver logs found"
fi
echo ""

echo "=== Diagnostic Complete ==="
echo ""
echo "Common issues and fixes:"
echo "  - Version mismatch: Update chromedriver to match Chrome version"
echo "  - Missing dependencies: Install required shared libraries"
echo "  - File descriptor limit: Increase with 'ulimit -n 65536' or systemd LimitNOFILE"
echo "  - Orphaned processes: Run 'pkill -9 chrome; pkill -9 chromedriver'"
echo "  - Xvfb not working: Reinstall with 'sudo apt install xvfb'"
