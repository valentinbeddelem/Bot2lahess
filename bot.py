import discord
from discord.ext import commands
import os
from keep_alive import keep_alive

# ───────────── Load secrets depuis Replit
TOKEN = os.environ["DISCORD_BOT_TOKEN"]   # secret Replit
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])  # secret Replit

# ───────────── Intents & Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ───────────── Ready
@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")

# ───────────── Commandes admin
@bot.command()
@commands.is_owner()
async def approve(ctx, suggestion_id: int):
    await ctx.send(f"Suggestion {suggestion_id} approuvée ✅")

@bot.command()
@commands.is_owner()
async def reject(ctx, suggestion_id: int):
    await ctx.send(f"Suggestion {suggestion_id} refusée ❌")

# ───────────── Keep bot alive (Replit ping)
keep_alive()
bot.run(TOKEN)
