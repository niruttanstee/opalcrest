import disnake
from disnake.ext import commands
import json
import os

# Import token.
with open('./tokens.json', 'r') as f:
    tokens = json.load(f)

# Add intents - permission controls
intents = disnake.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.guild_reactions = True
intents.members = True
intents.emojis = True
intents.presences = True
intents.messages = True
intents.reactions = True
intents.message_content = True
intents.voice_states = True

# Create bot object.
bot = commands.InteractionBot(
    intents=intents,
    sync_commands_debug=True)


@bot.event
async def on_ready():
    """
    Prints log in information when bot is ready.
    """
    await bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.watching, name="the calm breeze"))
    print(f"Bot is ready.")


for filename in os.listdir("./cogs/"):
    if filename.endswith(".py"):
        file = filename[:-3]
        bot.load_extension(f"cogs.{file}")
        print(f"Loaded: {file}")

discord_bot_token = tokens["discord_token"]
bot.run(discord_bot_token)
