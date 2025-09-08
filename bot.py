import discord
from discord.ext import commands, tasks
from supabase import create_client
import os
from datetime import datetime

# ───────────── Secrets depuis Replit
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────── Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

last_checked = datetime.utcnow()

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    check_suggestions.start()

@tasks.loop(seconds=10)
async def check_suggestions():
    """Check toutes les 10s s'il y a des suggestions en attente."""
    global last_checked
    try:
        response = supabase.table("suggestions_fiches") \
            .select("*") \
            .eq("status", "pending") \
            .gt("created_at", last_checked.isoformat()) \
            .execute()

        suggestions = response.data
        if suggestions:
            guild = bot.get_guild(GUILD_ID)
            channel = discord.utils.get(guild.text_channels, name="suggestions")  # ⚠️ mets le nom de ton salon
            if not channel:
                print("⚠️ Channel #suggestions introuvable")
                return

            for s in suggestions:
                await send_suggestion(channel, s)

        last_checked = datetime.utcnow()
    except Exception as e:
        print(f"Erreur check_suggestions : {e}")

async def send_suggestion(channel, suggestion):
    """Envoie une suggestion sous forme d’embed avec boutons."""
    embed = discord.Embed(
        title=f"Suggestion #{suggestion['id']}",
        description=suggestion["description_fiche"],
        color=discord.Color.blurple(),
        timestamp=datetime.fromisoformat(suggestion["created_at"].replace("Z", "+00:00"))
    )
    embed.add_field(name="Lien Mega", value=suggestion["lien_mega"], inline=False)
    if suggestion.get("autres_alias"):
        embed.add_field(name="Autres alias", value=suggestion["autres_alias"], inline=False)

    embed.set_author(
        name=suggestion["submitted_by"],
        icon_url=f"https://cdn.discordapp.com/embed/avatars/{int(suggestion['discord_id']) % 5}.png"
    )

    class SuggestionView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="✅ Approuver", style=discord.ButtonStyle.success)
        async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await is_owner(interaction.user):
                await interaction.response.send_message("⛔ Tu n’as pas la permission", ephemeral=True)
                return
            supabase.table("suggestions_fiches") \
                .update({"status": "approved", "updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", suggestion["id"]).execute()
            await interaction.response.send_message(f"Suggestion {suggestion['id']} approuvée ✅", ephemeral=True)

        @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
        async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await is_owner(interaction.user):
                await interaction.response.send_message("⛔ Tu n’as pas la permission", ephemeral=True)
                return
            supabase.table("suggestions_fiches") \
                .update({"status": "rejected", "updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", suggestion["id"]).execute()
            await interaction.response.send_message(f"Suggestion {suggestion['id']} refusée ❌", ephemeral=True)

    await channel.send(embed=embed, view=SuggestionView())

async def is_owner(user: discord.User) -> bool:
    """Vérifie si l’utilisateur est bien le owner du bot."""
    app_info = await bot.application_info()
    return user.id == app_info.owner.id

bot.run(TOKEN)
