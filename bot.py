# bot.py
import os
import discord
from discord.ext import commands
from utils.discord_utils import notify_suggestion_to_discord

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Token bot depuis .env

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot connecté : {bot.user}")

# Commande test
@bot.command()
async def ping(ctx):
    await ctx.send("Pong !")

# Commande pour valider une suggestion depuis Discord (exemple)
@bot.command()
async def approve(ctx, suggestion_id: int):
    # Ici tu peux faire un call vers ton API/site pour valider la fiche
    await ctx.send(f"Suggestion {suggestion_id} approuvée ✅")
    # Optionnel : notifier ton site ou webhook
    notify_suggestion_to_discord(suggestion_id, approved=True)

bot.run(TOKEN)
