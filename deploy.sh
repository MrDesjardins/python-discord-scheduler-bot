#!/bin/bash

# Deploy script - push to GitHub and update remote server
# Usage: ./deploy.sh

set -e

REMOTE_HOST="10.0.0.181"
REMOTE_USER="pdesjardins"
REMOTE_DIR="/home/pdesjardins/code/python-discord-scheduler-bot"

# Push to GitHub
echo "Pushing to GitHub..."
git push origin main

# SSH into remote and run update script
echo "Deploying to $REMOTE_HOST..."
ssh "$REMOTE_USER@$REMOTE_HOST" "cd $REMOTE_DIR && bash -l deployment/update.sh"

echo ""
echo "Deploy complete!"
