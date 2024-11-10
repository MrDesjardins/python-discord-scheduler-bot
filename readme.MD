# What is this Bot doing?

1. The bot sends a daily message to a specific channel of the guild asking the user when they plan to play the game. It uses reaction by emoji for user to specify many range of hours that they plan to play.
2. The bot allows a user to specify a recurrent schedule.
3. The bot a voice message to the first user that joins the voice channel giving who is about to come play (optional).
4. The bot as administrative features with many statistics and analytic giving hindsight on the user's activity to pro-actively reaching folks.
5. The bot allows users to know everyone's timezone in a specific voice channel to help identifying the best host.

# What does the Bot look like?

## Daily Message
The bot sends a daily message to the guild asking the user when they plan to play the game. The user can react to the message with the hours they plan to play. By default, the bot fills the timeline with folks who used the `/addschedule` which allows user to set week day and time in advance. The bot automatically adjust the schedule every 15 minutes by looking at the voice channel and add people in the schedule.
![Daily Message](readme_assets/daily_message.png)

## Admin Console
The admin console allows recurrent task in development (local) or in production (Raspberry Pi). The admin can execute tests or run visualizations of the user activity.
![Admin Menu](readme_assets/botadmin.gif)

## Visualization of User Relationship
One of the administrative feature is to see the relationship between users. The bot uses the voice channel to see who is playing with whom and generate a network graph.

![2D Relationship](readme_assets/2d_relationship_graph.png)

The visualization is also in 3D.

![3D Relationship](readme_assets/3d_relationship.gif)

## Visualization of the Inactive User
The bot keeps track of who is joining the voice channels. The bot can generate a visualization of the inactive user.

![Inactive](readme_assets/inactive_users.png)

## Visualization of the Duo
The bot can analyze who is playing with whom at the same time (in the same voice channel) and create a graph of the most common duo.

![Duo](readme_assets/duo.png)

## Visualization of the Total Voice Time
The bot can gives you who is the most active in the voice channels.

![Voice Active](readme_assets/total_voice.png)

## Visualization of which Week Day is the Most Active per User
The bot can generate a matrix of the most active day of the week for each user.

![Weekday Activity](readme_assets/week_day_activity.png)

# Bot Commands

## User Commands

### Schedule Commands

#### addschedule

User can react to a message every day or can use the `/addschedule` command to set a schedule. The command allows selecting day of the weeks and many hours. If the user executes the command multiple times, the previous schedule will be overridden.

#### removeschedule

Once a user set a schedule, they can remove it using the `/removeschedule` command or calling the `/addschedule` which will override the previous schedule.

#### seeschedule

`/seeschedule` command will show the current schedule of the user.

### Timezone Commands

#### setmytimezone
Allows a user to specify which timezone they are in.

#### getusertimezone
Allows a user to retrieve a user timezone

#### gettimezones
Allows a user to get the list of timezones of all people in a specific voice channel.

### Rank/Role Commands

#### `adjustrank`
Allows the user to type his Ubisoft account name to fetch the maximum rank he achieved and assign the role.

## Moderators/Administrator Commands

### Schedule Commands

#### modadduserschedule

An administrator can add a schedule (hours) for a user for the current day.

#### modrefreshschedule

If the bot is down, call the function to refresh the cache from the reaction of the message.

#### modforcesendschedule

Force sending the daily question regardless if it was already sent or not (in the cache). Useful if the cache has the value that the message was sent but it crashed and the message was never sent.

#### modapplyschedule

Force the bot to check the cache for user's schedule and apply it on the current day.

### Timezone commands

#### modsetusertimezone
Allows an administrator to set the timezone of a user.

### Channels Commands

### modtextschedulechannel

The bot needs to send daily messages to a specific channel of the guild. The action specifies which channel the bot will send a daily message. Without this configuration, the bot will skip the guild daily message.

#### modseeschedulechannel

Allows to see what is the text channel configured for the guild to send the schedule every day.

#### modvoicechannel

The bot needs to know which voice channel to check for the guild. The action specify which channel the bot check activity. Without this configuration, the bot will skip the voice participation. Calling the function many times adds up the voice channels.

#### modseevoicechannels

Allows to see what is the voice channels configured for the guild.

#### modresetvoicechannel

Rremove all voice channels configuration. It is good to reset and add the voice channels again.

### Bot Behaviors

#### modenablebotvoice
Turn on and off the feature that the bot goes into the voice channel to send a voice mesage to the first user.

### Analytics

#### modshowcommunity
Generate an image that is a network graph of the useer and with whom they play the most. 

#### modversion
Give the latest SHA of the commit. Helps to ensure that the bot is running the latest version.

## Owner Commands

### modresetcache

Reset the cache for the administration guild.


# Discord Administration

## Discord Configuration

### Set Up a Discord Bot Account

Create a Discord Application:

1. https://discord.com/developers/applications
1. Click on "New Application" and give it a name.
1. Currently, this application has two applications: `GameTimeScheduler` and `GameTimeScheduler_Dev`. The first one is for production and the second one is for development.

### Create a Bot:

In your application, navigate to the "Bot" tab.

1. Click "Add Bot" and confirm.
1. Under "TOKEN", click "Copy" to get your bot's token. Keep this token secure!

### Invite the Bot to Your Server:

Navigate to the `OAuth2` tab and then `URL Generator`.
Under `Scopes` select:

1. `bot`
1. `applications.commands`

Under "Bot Permissions", select the necessary permissions:

1. Manage Roles
1. View Channels
1. Send Messages
1. Manage messages
1. Read Message History
1. Add Reactions

Copy the generated URL and open it in your browser to invite the bot to your desired server.

```sh
# Production Bot
https://discord.com/oauth2/authorize?client_id=1279592054996996219&permissions=268512320&redirect_uri=https%3A%2F%2Fdiscord.com%2Foauth2%2Fauthorize&integration_type=0&scope=bot+applications.commands

# Dev Bot
https://discord.com/oauth2/authorize?client_id=1282412272458924103&permissions=268512320&redirect_uri=https%3A%2F%2Fdiscord.com%2Foauth2%2Fauthorize&integration_type=0&scope=bot+applications.commands
```

# Create a TRN Developer Account
To get the statistics of the user, you need to create a developer account on the TRN website. The TRN API is used to get the statistics of the user. The API key is required to get the statistics of the user.

1. Create an account on the TRN website: https://tracker.gg/developers
2. E.g. https://tracker.gg/developers/apps/330f2e3d-c58f-4170-a4c1-65710ba2e55d 

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
TRN_API_KEY<TRN token>
```

11. Install ffmpeg for the audio

```sh
sudo apt-get install ffmpeg
```

12. Install SqlLite3 for analytic

```sh
sudo apt install sqlite3
```

13. Install OpenBLAS for numpy used in the generation of relation analytic between user. This might require other dependencies and must have the latest APT packages.

```sh
sudo apt-get install libopenblas-base
sudo apt-get install libjpeg-dev zlib1g-dev libtiff-dev libopenjp2-7-dev
```

14. Install the systemd that will run the bot at startup

```sh
sudo cp /home/pi/python-discord-scheduler-bot/systemd/gametimescheduler.service /etc/systemd/system/gametimescheduler.service
sudo systemctl enable gametimescheduler.service
sudo systemctl start gametimescheduler.service
```

15. Install Chrome for the web scraping

```sh
sudo apt install -y xvfb
sudo apt install chromium-browser chromium-chromedriver
sudo chown pi:pi /usr/bin/chromedriver
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
python -m unittest discover tests -p "*_unit_test.py"

# or
pytest -v -s ./tests/*_unit_test.py
``` 

# Integration Tests
```sh
pytest -v -s ./tests/*_integration_test.py
```

# Coverage Tests

```sh
coverage run -m pytest -v -s ./tests
coverage report -m
coverage lcov 
coverage html
```