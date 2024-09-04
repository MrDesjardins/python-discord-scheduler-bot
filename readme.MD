
# Discord
## Set Up a Discord Bot Account
Create a Discord Application: 

1. https://discord.com/developers/applications
2. Click on "New Application" and give it a name.

## Create a Bot:

In your application, navigate to the "Bot" tab.
1. Click "Add Bot" and confirm.
2. Under "TOKEN", click "Copy" to get your bot's token. Keep this token secure!

## Invite the Bot to Your Server:

Navigate to the "OAuth2" tab and then "URL Generator".
Under "Scopes", select:
1. `bot`
2. `applications.commands`

Under "Bot Permissions", select the necessary permissions:
1. View Channels
2. Send Messages
3. Manage messages
4. Read Message History
5. Add Reactions

Copy the generated URL and open it in your browser to invite the bot to your desired server.
# Developer

## Environment

```sh

# Create Environment
python3 -m venv .venv

# Activate Environment
source .venv/bin/activate

# Update PIP
python3 -m pip install --upgrade pip

# Install Requirements
python3 -m pip install -r requirements.txt

# Save Requirements
python3 -m pip freeze > requirements.txt
```
