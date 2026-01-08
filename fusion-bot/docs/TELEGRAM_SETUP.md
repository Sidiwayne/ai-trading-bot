# Telegram Bot Setup Guide
==========================

This guide will help you set up Telegram notifications for FusionBot.

## Step 1: Create a Telegram Bot

1. **Open Telegram** and search for `@BotFather`
2. **Start a chat** with BotFather
3. **Send the command**: `/newbot`
4. **Follow the prompts**:
   - Choose a name for your bot (e.g., "FusionBot Trader")
   - Choose a username (must end with `bot`, e.g., "fusionbot_trader_bot")
5. **BotFather will give you a token** that looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   **Save this token** - you'll need it for `TELEGRAM_BOT_TOKEN`

## Step 2: Get Your Chat ID

There are several ways to get your chat ID:

### Method 1: Using @userinfobot (Easiest)

1. **Search for** `@userinfobot` in Telegram
2. **Start a chat** with @userinfobot
3. **Send any message** (e.g., `/start`)
4. **The bot will reply** with your user information, including your Chat ID
5. **Copy the Chat ID** (it's a number, e.g., `123456789`)

### Method 2: Using @getidsbot

1. **Search for** `@getidsbot` in Telegram
2. **Start a chat** with @getidsbot
3. **Send any message**
4. **The bot will reply** with your Chat ID

### Method 3: Using Telegram Web/Desktop (Advanced)

1. **Open Telegram Web** (web.telegram.org) or Desktop app
2. **Start a chat** with your bot (the one you created in Step 1)
3. **Send a message** to your bot (e.g., "Hello")
4. **Open this URL** in your browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
5. **Look for** `"chat":{"id":123456789}` in the JSON response
6. **Copy the number** after `"id":` - that's your Chat ID

### Method 4: Using a Test Message Script

Run this Python script to get your Chat ID:

```python
import requests
import sys

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your token from Step 1

# Get updates
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url)
data = response.json()

if data["ok"]:
    updates = data["result"]
    if updates:
        # Get the last message's chat ID
        chat_id = updates[-1]["message"]["chat"]["id"]
        print(f"Your Chat ID is: {chat_id}")
    else:
        print("No messages found. Send a message to your bot first!")
else:
    print(f"Error: {data.get('description', 'Unknown error')}")
```

**Steps:**
1. Replace `YOUR_BOT_TOKEN_HERE` with your bot token
2. Send a message to your bot in Telegram
3. Run the script
4. Copy the Chat ID from the output

## Step 3: Configure FusionBot

1. **Open your `.env` file** (or create one from `.env.example`)
2. **Add these lines**:

```bash
# Telegram Notifications
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

3. **Replace the values** with your actual token and chat ID
4. **Save the file**

## Step 4: Test Your Setup

Run the test script to verify everything works:

```bash
cd fusion-bot
source venv/bin/activate
python scripts/test_notifications.py
```

You should receive test messages in your Telegram chat!

## Troubleshooting

### "Telegram not configured"
- Check that both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in your `.env` file
- Make sure there are no extra spaces or quotes around the values

### "Failed to send Telegram notification"
- Verify your bot token is correct
- Make sure you've sent at least one message to your bot
- Check that your Chat ID is correct (it's a number, not a username)

### "Unauthorized" error
- Your bot token might be incorrect
- Try creating a new bot with BotFather

### Bot not responding
- Make sure you've started a chat with your bot
- Send a message to your bot first (e.g., `/start`)

## Security Notes

⚠️ **Important:**
- Never commit your `.env` file to Git
- Keep your bot token secret
- The bot can only send messages to chats where users have started a conversation with it
- Your Chat ID is personal - don't share it publicly

## Example .env Configuration

```bash
# === Notifications ===
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

That's it! Your FusionBot will now send notifications to your Telegram chat.

