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

# Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

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
