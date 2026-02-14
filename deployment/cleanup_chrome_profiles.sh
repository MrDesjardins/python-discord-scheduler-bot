#!/bin/bash
# Cleanup old Chrome profile directories in /tmp
# These can accumulate if Chrome crashes before cleanup

echo "Cleaning up old Chrome profile directories..."

# Find and delete chrome_profile_* directories older than 60 minutes
OLD_PROFILES=$(find /tmp -maxdepth 1 -name 'chrome_profile_*' -type d -mmin +60 2>/dev/null)

if [ -z "$OLD_PROFILES" ]; then
    echo "No old Chrome profiles found (this is good!)"
    exit 0
fi

echo "Found old Chrome profile directories:"
echo "$OLD_PROFILES"

COUNT=$(echo "$OLD_PROFILES" | wc -l)
echo ""
echo "Deleting $COUNT old profile director(ies)..."

find /tmp -maxdepth 1 -name 'chrome_profile_*' -type d -mmin +60 -exec rm -rf {} \; 2>/dev/null

echo "✓ Cleanup complete"
