# What is this Bot doing?

1. The bot sends a daily message to a specific channel of the guild asking the user when they plan to play the game. It uses reaction by emoji for user to specify many range of hours that they plan to play.
2. The bot allows a user to specify a recurrent schedule.

# Bot Commands

## `textchannel` (Admin only)

The bot needs to send daily messages to a specific channel of the guild. An administrator must call `/textchannel` and specify which channel the bot will send a daily message. Without this configuration, the bot will skip the guild daily message.

## `voicechannel` (Admin only)

The bot needs to know which voice channel to check for the guild. An administrator must call `/voicechannel` and specify which channel the bot check activity. Without this configuration, the bot will skip the voice participation. Calling the function many times adds up the voice channels.

## `seetextchannel` (Admin only)

Allows to see what is the text channel configured for the guild.

## `seevoicechannels` (Admin only)

Allows to see what is the voice channels configured for the guild.

## `resetvoicechannel` (Admin only)

An administrator calls `/resetvoicechannel` to remove all voice channels configuration. It is good to reset and add the voice channels again.

## `addschedule`

User can react to a message every day or can use the `/addschedule` command to set a schedule. The command allows selecting day of the weeks and many hours. If the user executes the command multiple times, the previous schedule will be overridden.

## `removeschedule`

Once a user set a schedule, they can remove it using the `/removeschedule` command or calling the `/addschedule` which will override the previous schedule.

## `seeschedule`

`/seeschedule` command will show the current schedule of the user.

## `resetcache` (Admin only)

Reset the cache for the administration guild.

## `adduserschedule` (Admin only)

An administrator can add a schedule (hours) for a user for the current day.

## `applyschedule` (Admin only)

An administrator can invoke the `/applyschedule` to force the bot to check the cache for user's schedule and apply it on the current day.

## `refreshschedule` (Admin only)

If the bot is down, the administrator can call `/refreshschedule` to refresh the cache from the reaction of the message.

## `forcesendschedule` (Admin only)

Force sending the daily question regardless if it was already sent or not (in the cache). Useful if the cache has the value that the message was sent but it crashed and the message was never sent.

## `enablebotvoice` (Admin only)
Turn on and off the feature that the bot goes into the voice channel to send a voice mesage to the first user.

## `showcommunity` (Admin only)
Generate an image that is a network graph of the useer and with whom they play the most. 

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
python3 bot.py # or ./bot.py
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

1. Update the sources list for apt packages (required in some Raspberry Pi to get Python3) by editing `/etc/apt/sources.list`

```
deb http://raspbian.raspberrypi.org/raspbian/ buster main contrib non-free rpi
```

2. Upgrade apt packages `sudo apt-get update` and upgrade `sudo apt-get upgrade`
3. SSH into the Raspberry Pi
4. `ssh pi@10.0.0.192`
5. Clone the repository
6. `git clone https://github.com/MrDesjardins/python-discord-scheduler-bot.git`
7. Create the Python environment `python3 -m venv .venv`
8. Activate the Python environment `source .venv/bin/activate`
9. Install the dependencies `python3 -m pip install -r requirements.txt`
10. Edit the environment variables file `/etc/environment` (require sudo)

```sh
ENV=prod
BOT_TOKEN=<bot token>
```

9. Install ffmpeg for the audio

```sh
sudo apt-get install ffmpeg
```

10. Install SqlLite3 for analytic

```sh
sudo apt install sqlite3
```

11. Install OpenBLAS for numpy used in the generation of relation analytic between user. This might require other dependencies and must have the latest APT packages.

```sh
sudo apt-get install libopenblas-base
sudo apt-get install libjpeg-dev zlib1g-dev libtiff-dev libopenjp2-7-dev
```

12. Install the systemd that will run the bot at startup

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

## Linting

To lint the code, you can use the following command:

```sh
pylint **/*.py
black **/*.py
```

# Deployment

The best way to code and publish a new version is to code, push in GitHub, and then pull the code in the Raspberry Pi. The script `deployment/update.sh` does the fetching, install the dependencies and restart the service.

```sh
deployment/update.sh
```

# Analytic Data

The bot listen to the voice channels selected by the administrator and store the data in a database. The analytic concerns the user, the channel, the time in/out. The goal is establishing pattern which may help in the future scheduling and also see if how we may predict the user's activity and suggest partners.

Information are in the `user_activity.db` database. You can access the database using the following command which download the database in the current directory and open it.

```sh
analytics/transfer.sh
sqlite3 user_activity.db
```

You can also while developing using the test script with `python3 test_analytics_fake_date.py` which will use the local database and generate fake data. You can see the data but also the generated images.

# Unit Tests

```sh
python -m unittest discover tests -p "*_test.py"
``` 