import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import pytz
import re
import os
from flask import Flask, request
from threading import Thread

# Your bot token and channel ID
BOT_TOKEN = "7524276385:AAG3b60E2WQf0jfwSqmERdJ7tMWA5wkJd_E"
CHANNEL_ID = -1002192323521  # Replace with your channel ID

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up the scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
scheduler.start()

# Dictionary to store messages and their corresponding times
user_data = {}

# Function to convert text to small caps
def convert_to_small_caps(message: str) -> str:
    small_caps_translation = str.maketrans({
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 
        'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 
        'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ',
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 
        'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 
        'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
    })
    return message.translate(small_caps_translation)

def format_message(message: str) -> str:
    # Preserve links in the text
    message = re.sub(r'(https?://\S+)', r'<a href="\1">\1</a>', message)
    
    # Replace specific words and format
    formatted_message = message.replace("minute", "ᴍɪɴᴜᴛᴇ")  # Small caps minute
    formatted_message = convert_to_small_caps(formatted_message)  # Convert text to small caps

    # Replace "sᴋᴇᴘᴛɪᴄ ᴛʀᴀᴅᴇʀ" with the link
    formatted_message = formatted_message.replace(
        "sᴋᴇᴘᴛɪᴄ ᴛʀᴀᴅᴇʀ", 
        '<a href="https://t.me/+905010726177">sᴋᴇᴘᴛɪᴄ ᴛʀᴀᴅᴇʀ</a>'
    )

    return formatted_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.message.chat_id
    user_data[chat_id] = {'messages': [], 'waiting_for_times': False}
    await update.message.reply_text(
        "Welcome to the Message Scheduler Bot!\n\n"
        "Please send the messages that you want to schedule. "
        "After sending all the messages, type /schedule to provide the times "
        "in HH:MM format (IST) for each message."
    )


async def collect_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect messages from the user."""
    chat_id = update.message.chat_id

    if user_data[chat_id]['waiting_for_times']:
        # If we're waiting for times, process them
        times = update.message.text.split()
        if len(times) != len(user_data[chat_id]['messages']):
            await update.message.reply_text(
                "Please provide the same number of times as messages."
            )
            return
        
        # Store the times and schedule the messages
        for i, msg in enumerate(user_data[chat_id]['messages']):
            time_str = times[i]
            schedule_time = datetime.strptime(time_str, "%H:%M").time()
            now = datetime.now(pytz.timezone("Asia/Kolkata"))
            schedule_datetime = now.replace(hour=schedule_time.hour, minute=schedule_time.minute, second=0, microsecond=0)

            if schedule_datetime < now:
                await update.message.reply_text(
                    f"The time {time_str} has already passed for today. Please choose a future time."
                )
            else:
                scheduler.add_job(
                    send_message_to_channel,
                    trigger=DateTrigger(run_date=schedule_datetime, timezone="Asia/Kolkata"),
                    args=[msg]
                )
        
        await update.message.reply_text("Messages have been scheduled!")
        user_data[chat_id] = {'messages': [], 'waiting_for_times': False}  # Reset data for the user

    else:
        # Collect the message if not waiting for times
        user_data[chat_id]['messages'].append(update.message.text)
        await update.message.reply_text("Message received! Send more or type /schedule to set times.")


async def ask_for_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask the user for times to schedule the messages."""
    chat_id = update.message.chat_id

    if user_data[chat_id]['messages']:
        user_data[chat_id]['waiting_for_times'] = True
        await update.message.reply_text(
            "Now, please provide the times for each message in the format HH:MM HH:MM ... "
            "(separate each time with a space)."
        )
    else:
        await update.message.reply_text(
            "You haven't sent any messages yet. Please send the messages first."
        )


async def send_message_to_channel(message: str):
    """Send a scheduled message to the channel."""
    formatted_message = format_message(message)

    # Build the bot instance
    bot = Application.builder().token(BOT_TOKEN).build()
    await bot.bot.send_message(chat_id=CHANNEL_ID, text=formatted_message, parse_mode="HTML")

# Create a Flask app
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    return "Bot is running!"

def main():
    """Start the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_messages))
    app.add_handler(CommandHandler("schedule", ask_for_times))

    logger.info("Bot started!")

    # Start Flask app in a separate thread
    from threading import Thread

    def run_flask_app():
        flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

    thread = Thread(target=run_flask_app)
    thread.start()

    # Run the bot
    app.run_polling()

if __name__ == "__main__":
    main()
