# HTML-TXT Converter Bot

A high-speed Telegram bot to convert advanced HTML files to line-by-line TXT (with headings) and vice versa, applying a pro-level dark theme for HTML outputs.

## Features
- ⚡ **High-Speed Conversion**: Asynchronous processing with `aiohttp` and `BeautifulSoup`.
- 🎨 **Pro-Level HTML**: Automatically applies a responsive dark theme to TXT-to-HTML conversions.
- 🗄 **MongoDB Integrated**: Saves user IDs and manages ban statuses.
- 📂 **Dump Channel**: Forwards all received documents to a specified channel.
- 📊 **Log Channel**: Tracks which users are converting which files.
- 🔐 **Force Subscribe**: Forces users to join a specific channel before using the bot.

## Deployment

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/)
[![Deploy on Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### Environment Variables
| Variable | Description |
|---|---|
| `API_ID` | Your Telegram API ID from my.telegram.org |
| `API_HASH` | Your Telegram API Hash |
| `BOT_TOKEN` | Bot Token from @BotFather |
| `MONGO_URI` | MongoDB Connection URI |
| `ADMINS` | Comma-separated list of Admin user IDs (e.g., `123456,78910`) |
| `LOG_CHANNEL` | ID of the channel for logging usage (e.g., `-100123...`) |
| `DUMP_CHANNEL` | ID of the channel to store all files (e.g., `-100123...`) |
| `FORCE_SUB_CHANNEL` | Username of channel without `@` (e.g., `MyUpdatesChannel`) |
| `CREDIT` | Watermark text to add to output files |
| `PORT` | Port for the webserver (Default: `8080`) |

### Commands
**User Commands:**
- `/start` - Check bot status and instructions.

**Admin Commands:**
- `/users` - Check total users in the database.
- `/ban <user_id>` - Ban a user from using the bot.
- `/unban <user_id>` - Unban a user.
- `/restart` - Restart the bot instance.
