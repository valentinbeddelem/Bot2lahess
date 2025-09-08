import discord
from discord.ext import commands, tasks
from supabase import create_client
import os
from datetime import datetime

# ───────────── Load secrets depuis Replit
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────── Bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

last_checked = datetime.utcnow()

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    check_suggestions.start()

@tasks.loop(seconds=10)
async def check_suggestions():
    global last_checked
    try:
        # Récupérer les suggestions nouvelles et en attente
        response = supabase.table("suggestions_fiches") \
            .select("*") \
            .eq("status", "pending") \
            .gt("created_at", last_checked.isoformat()) \
            .execute()

        suggestions = response.data
        if suggestions:
            channel = discord.utils.get(bot.get_all_channels(), guild__id=GUILD_ID, name="suggestions")
            if not channel:
                print("⚠️ Aucun channel 'suggestions' trouvé")
                return

            for s in suggestions:
                await send_suggestion(channel, s)

        last_checked = datetime.utcnow()
    except Exception as e:
        print(f"Erreur check_suggestions : {e}")

async def send_suggestion(channel, suggestion):
    embed = discord.Embed(
        title=f"Suggestion fiche #{suggestion['id']}",
        description=suggestion["content"],  # ⚠️ à adapter selon ta colonne
        color=discord.Color.blurple(),
        timestamp=datetime.fromisoformat(suggestion["created_at"].replace("Z", "+00:00"))
    )
    embed.set_author(name=suggestion["username"])  # ⚠️ idem, adapte si ça existe pas

    class SuggestionView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="✅ Approuver", style=discord.ButtonStyle.success)
        async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != bot.owner_id:
                await interaction.response.send_message("Tu n’as pas la permission ❌", ephemeral=True)
                return
            supabase.table("suggestions_fiches").update({"status": "approved"}).eq("id", suggestion["id"]).execute()
            await interaction.response.send_message(f"Suggestion {suggestion['id']} approuvée ✅", ephemeral=True)

        @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
        async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != bot.owner_id:
                await interaction.response.send_message("Tu n’as pas la permission ❌", ephemeral=True)
                return
            supabase.table("suggestions_fiches").update({"status": "rejected"}).eq("id", suggestion["id"]).execute()
            await interaction.response.send_message(f"Suggestion {suggestion['id']} refusée ❌", ephemeral=True)

    await channel.send(embed=embed, view=SuggestionView())

bot.run(TOKEN)
