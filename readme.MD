# Bot Commands

## Selecting a Channel

The bot needs to send daily messages to a specific channel. To configure, an administrator must call `/channel`.

## Setting a Schedule

User can react to a message every day or can use the `/addschedule` command to set a schedule. The command allows selecting day of the weeks and many hours. If the user executes the command multiple times, the previous schedule will be overridden.

## Removing a Schedule

Once a user set a schedule, they can remove it using the `/removeschedule` command or calling the `/addschedule` which will override the previous schedule.

## See a Schedule

`seeschedule` command will show the current schedule of the user.

# Discord Administration

## Discord Configuration

### Set Up a Discord Bot Account

Create a Discord Application:

1. https://discord.com/developers/applications
2. Click on "New Application" and give it a name.
3. Currently, this application has two applications: `GameTimeScheduler` and `GameTimeScheduler_Dev`. The first one is for production and the second one is for development.

### Create a Bot:

In your application, navigate to the "Bot" tab.

1. Click "Add Bot" and confirm.
2. Under "TOKEN", click "Copy" to get your bot's token. Keep this token secure!

### Invite the Bot to Your Server:

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
# Production Bot
https://discord.com/oauth2/authorize?client_id=1279592054996996219&permissions=76864&integration_type=0&scope=bot

# Dev Bot
https://discord.com/oauth2/authorize?client_id=1282412272458924103&permissions=76864&integration_type=0&scope=bot
```
# Local Development Configuration

## .Env file

The .env file should contain the following in development. These values should be kept secret and be
environment variable for your private deployment.

```
ENV=dev # or prod
BOT_TOKEN=<bot token>
BOT_TOKEN_DEV=<bot token>
```

## Running the bot in Dev:

To run the bot in development, you can use the following commands.

```sh
source .venv/bin/activate
python3 bot.py
```

## Python Environment and Dependencies

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

# Installation with Azure App Service Free Plan

1. Create an account to https://portal.azure.com/
1. Open Deployment Center, configure the Git hub repository
1. Set environment variable (`ENV` and `BOT_TOKEN`) under `settings` and `environment variables`
1. `python3 -m venv .venv`
1. `source .venv/bin/activate`
1. `python3 -m pip install -r requirements.txt`
1. `python3 bot.py`


# Alternative Hosting Solutions
The free plan of [PythonAnywhere](https://www.pythonanywhere.com) does not allow the Discord.py communication on port 443.

