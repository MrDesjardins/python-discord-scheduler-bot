#!/bin/bash
# Deployment script for file descriptor leak fixes
# Run this on production server after pulling latest code

set -e  # Exit on error

echo "=== File Descriptor Leak Fix Deployment ==="
echo ""

# Step 1: Create systemd override directory
echo "Step 1: Creating systemd override directory..."
sudo mkdir -p /etc/systemd/system/gametimescheduler.service.d

# Step 2: Create override configuration
echo "Step 2: Creating systemd service override configuration..."
sudo tee /etc/systemd/system/gametimescheduler.service.d/override.conf > /dev/null <<'EOF'
# Systemd service override for gametimescheduler.service
# This increases the file descriptor limit to prevent "Too many open files" errors
# when running Chrome/Selenium for R6 Tracker scraping

[Service]
# Increase file descriptor limit
# Default system limit is usually 1024, Chrome can use hundreds of FDs
LimitNOFILE=65536

# Also set limits for child processes
LimitNPROC=4096
EOF

echo "   Created: /etc/systemd/system/gametimescheduler.service.d/override.conf"

# Step 3: Reload systemd
echo "Step 3: Reloading systemd daemon..."
sudo systemctl daemon-reload

# Step 4: Show current limits before restart
echo "Step 4: Current service limits (before restart):"
sudo systemctl show gametimescheduler.service | grep -E "(LimitNOFILE|LimitNPROC)" || true

# Step 5: Restart service
echo "Step 5: Restarting gametimescheduler.service..."
sudo systemctl restart gametimescheduler.service

# Step 6: Wait for service to stabilize
echo "Step 6: Waiting for service to stabilize..."
sleep 3

# Step 7: Check service status
echo "Step 7: Checking service status..."
if sudo systemctl is-active --quiet gametimescheduler.service; then
    echo "   ✓ Service is running"
else
    echo "   ✗ Service failed to start!"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u gametimescheduler.service -n 50 --no-pager
    exit 1
fi

# Step 8: Show new limits
echo "Step 8: New service limits (after restart):"
sudo systemctl show gametimescheduler.service | grep -E "(LimitNOFILE|LimitNPROC)"

# Step 9: Monitor logs for file descriptor usage
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "The service should now log file descriptor usage messages like:"
echo "  - 'File descriptor usage: X/Y (Z%)' - Normal monitoring"
echo "  - 'High file descriptor usage...' - Warning of potential issues"
echo ""
echo "To monitor logs in real-time, run:"
echo "  sudo journalctl -u gametimescheduler.service -f"
echo ""
echo "To check for any 'Too many open files' errors:"
echo "  sudo journalctl -u gametimescheduler.service --since today | grep -i 'too many'"
echo ""
