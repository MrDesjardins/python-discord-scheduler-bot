# What is this Bot doing?

1. The bot sends a daily message to a specific channel of the guild asking the user when they plan to play the game. It uses reaction by emoji for user to specify many range of hours that they plan to play.
2. The bot allows a user to specify a recurrent schedule.

# Bot Commands

## `channel` (Admin only)

The bot needs to send daily messages to a specific channel of the guild. An administrator must call `/channel` and specify which channel the bot will send a daily message. Without this configuration, the bot will skip the guild daily message.

## `voicechannel` (Admin only)

The bot needs to know which voice channel to check for the guild. An administrator must call `/voicechannel` and specify which channel the bot check activity. Without this configuration, the bot will skip the voice participation.

## `addschedule`

User can react to a message every day or can use the `/addschedule` command to set a schedule. The command allows selecting day of the weeks and many hours. If the user executes the command multiple times, the previous schedule will be overridden.

## `removeschedule`

Once a user set a schedule, they can remove it using the `/removeschedule` command or calling the `/addschedule` which will override the previous schedule.

## `seeschedule`

`seeschedule` command will show the current schedule of the user.

## `resetcache` (Admin only)

Reset the cache for the administration guild.

## `adduserschedule` (Admin only)

An administrator can add a schedule (hours) for a user for the current day.

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

# Installation on a Raspberry Pi

1. SSH into the Raspberry Pi
1. `ssh pi@10.0.0.192`
1. Clone the repository
1. `git clone https://github.com/MrDesjardins/python-discord-scheduler-bot.git`
1. Create the Python environment `python3 -m venv .venv`
1. Activate the Python environment `source .venv/bin/activate`
1. Install the dependencies `python3 -m pip install -r requirements.txt` 
1. Edit the environment variables file `/etc/environment` (require sudo)
```sh
ENV=prod
BOT_TOKEN=<bot token>
```
6. Install the systemd that will run the bot at startup
```sh
sudo cp /home/pi/python-discord-scheduler-bot/systemd/gametimescheduler.service /etc/systemd/system/gametimescheduler.service
sudo systemctl enable gametimescheduler.service
sudo systemctl start gametimescheduler.service
```

## Debugging
If the service does not start, you can check the status of the service with the following command:
```sh
sudo systemctl status gametimescheduler.service
```

# Alternative Hosting Solutions
1. The free plan of [PythonAnywhere](https://www.pythonanywhere.com) does not allow the Discord.py communication on port 443.
2. [Azure Web App](https://azure.microsoft.com/en-us/products/app-service) free plan does not have "always on" which means the bot cannot remain always active.