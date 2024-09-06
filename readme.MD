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

Navigate to the `OAuth2` tab and then `URL Generator`.
Under `Scopes` select:

1. `bot`
2. `applications.commands`

Under "Bot Permissions", select the necessary permissions:

1. View Channels
2. Send Messages
3. Manage messages
4. Read Message History
5. Add Reactions

Copy the generated URL and open it in your browser to invite the bot to your desired server.

```sh
https://discord.com/oauth2/authorize?client_id=1279592054996996219&permissions=76864&integration_type=0&scope=bot
```

## Selecting a Channel

The bot needs to send daily messages to a specific channel. To configure, an administrator must call `/channel`.

## Setting a Schedule

User can react to a message every day or can use the `/addschedule` command to set a schedule. The command allows selecting day of the weeks and many hours.

## Removing a Schedule

Once a user set a schedule, they can remove it using the `/removeschedule` command or calling the `/addschedule` which will override the previous schedule.

# Developer

## .Env file

The .env file should contain the following in development. These values should be kept secret and be
environment variable for your private deployment.

```
BOT_TOKEN=<bot token>
```

## Running the bot in Dev:

To run the bot in development, you can use the following commands.

```sh
source .venv/bin/activate
python3 bot.py
```

## Environment and Dependencies

Here are few commands to set up the environment and dependencies.

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
