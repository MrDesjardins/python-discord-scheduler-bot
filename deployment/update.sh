#! /bin/bash

# Print the current working directory for debugging
echo "Current directory: $(pwd)"

# Pull the latest changes
echo "Pulling latest changes from git..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "Failed to pull changes from git."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
uv sync
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

# Clean up old Chrome profile directories
echo "Cleaning up old Chrome profiles..."
./deployment/cleanup_chrome_profiles.sh

# Update systemd service file if it changed
echo "Checking for systemd service file updates..."
if ! cmp -s systemd/gametimescheduler.service /etc/systemd/system/gametimescheduler.service; then
    echo "Systemd service file has changed, updating..."
    sudo cp systemd/gametimescheduler.service /etc/systemd/system/gametimescheduler.service
    sudo systemctl daemon-reload
    echo "✓ Systemd service file updated"
else
    echo "Systemd service file unchanged"
fi

# Update the log-autofix service/timer if they changed (not enabled here;
# see systemd/README.md to opt in on a box that has NVIDIA_API_KEY/GITHUB_TOKEN set)
for unit in gametimescheduler-log-autofix.service gametimescheduler-log-autofix.timer; do
    if [ -f "/etc/systemd/system/$unit" ] && ! cmp -s "systemd/$unit" "/etc/systemd/system/$unit"; then
        echo "$unit has changed, updating..."
        sudo cp "systemd/$unit" "/etc/systemd/system/$unit"
        sudo systemctl daemon-reload
        echo "✓ $unit updated"
    fi
done

# Restart the service
echo "Restarting gametimescheduler.service..."
sudo systemctl restart gametimescheduler.service
if [ $? -ne 0 ]; then
    echo "Failed to restart the service."
    exit 1
fi

# Check the status of the service
echo "Checking the status of gametimescheduler.service..."
sudo systemctl status gametimescheduler.service
if [ $? -ne 0 ]; then
    echo "Service is not running properly."
    exit 1
fi

echo "Script executed successfully."
