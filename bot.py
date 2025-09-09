import discord
from discord.ext import commands, tasks
from supabase import create_client, ClientError
import os
from datetime import datetime
import aiohttp

# ───────────── Secrets depuis Replit
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────── Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.persistent_views = {}
last_checked = datetime.utcnow()

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    bot.add_view(SuggestionView())  # Réenregistrer les vues persistantes
    if not check_suggestions.is_running():
        check_suggestions.start()

@tasks.loop(seconds=30)
async def check_suggestions():
    """Check toutes les 30s s'il y a des suggestions en attente."""
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
            channel = discord.utils.get(guild.text_channels, name="suggestions")
            if not channel:
                error_msg = "⚠️ Channel #suggestions introuvable"
                print(error_msg)
                await notify_owner(error_msg)
                return
            for s in suggestions:
                await send_suggestion(channel, s)
        last_checked = datetime.utcnow()
    except ClientError as e:
        print(f"Erreur Supabase : {e.message}")
    except aiohttp.ClientError as e:
        print(f"Erreur réseau : {e}")
    except Exception as e:
        print(f"Erreur inattendue dans check_suggestions : {type(e).__name__} - {e}")

async def get_user_info(discord_id: int):
    """Récupère les infos d'un utilisateur depuis discord_users."""
    try:
        response = supabase.table("discord_users").select("username, avatar_url").eq("id", discord_id).execute()
        return response.data[0] if response.data else {"username": "Anonyme", "avatar_url": None}
    except Exception as e:
        print(f"Erreur récupération utilisateur {discord_id} : {e}")
        return {"username": "Anonyme", "avatar_url": None}

async def send_suggestion(channel, suggestion):
    """Envoie une suggestion sous forme d’embed avec boutons."""
    if not all(key in suggestion for key in ["id", "blaze", "type", "created_at", "discord_id"]):
        print(f"⚠️ Suggestion #{suggestion.get('id', 'inconnu')} incomplète : {suggestion}")
        return

    user_info = await get_user_info(suggestion["discord_id"])
    embed = discord.Embed(
        title=f"Suggestion #{suggestion['id']} ({suggestion['type']})",
        description=suggestion.get("description_fiche", "Aucune description"),
        color=discord.Color.blurple(),
        timestamp=datetime.fromisoformat(suggestion["created_at"].replace("Z", "+00:00"))
    )
    embed.add_field(name="Blaze", value=suggestion.get("blaze", "Non fourni"), inline=False)
    embed.add_field(name="Lien Mega", value=suggestion.get("lien_mega", "Non fourni"), inline=False)
    if suggestion.get("serveur"):
        embed.add_field(name="Serveurs", value=", ".join(suggestion["serveur"]), inline=False)
    if suggestion.get("autres_alias"):
        embed.add_field(name="Autres alias", value=", ".join(suggestion["autres_alias"]), inline=False)
    embed.set_author(
        name=user_info["username"],
        icon_url=user_info["avatar_url"] or f"https://cdn.discordapp.com/embed/avatars/{int(suggestion['discord_id']) % 5}.png"
    )
    view = SuggestionView(suggestion)  # Passer suggestion à la vue
    message = await channel.send(embed=embed, view=view)
    bot.persistent_views[message.id] = view

class SuggestionView(discord.ui.View):
    def __init__(self, suggestion):
        super().__init__(timeout=None)
        self.suggestion = suggestion

    @discord.ui.button(label="✅ Approuver", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("⛔ Tu n’as pas la permission", ephemeral=True)
            return
        try:
            # Mettre à jour le statut de la suggestion
            supabase.table("suggestions_fiches") \
                .update({"status": "approved", "updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", self.suggestion["id"]).execute()
            
            # Traiter la suggestion approuvée
            if self.suggestion["type"] == "create":
                # Créer une nouvelle fiche
                supabase.table("fiches").insert({
                    "blaze": self.suggestion.get("blaze"),
                    "serveur": self.suggestion.get("serveur", []),
                    "description_fiche": self.suggestion.get("description_fiche"),
                    "autres_alias": self.suggestion.get("autres_alias", []),
                    "lien_mega": self.suggestion.get("lien_mega"),
                    "discord_id": str(self.suggestion["discord_id"]),  # Convertir en texte pour fiches
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            elif self.suggestion["type"] == "update" and self.suggestion.get("fiche_id"):
                # Mettre à jour la fiche existante
                supabase.table("fiches").update({
                    "blaze": self.suggestion.get("blaze"),
                    "serveur": self.suggestion.get("serveur", []),
                    "description_fiche": self.suggestion.get("description_fiche"),
                    "autres_alias": self.suggestion.get("autres_alias", []),
                    "lien_mega": self.suggestion.get("lien_mega"),
                    "discord_id": str(self.suggestion["discord_id"]),
                }).eq("id", self.suggestion["fiche_id"]).execute()

            await interaction.response.send_message(f"Suggestion {self.suggestion['id']} approuvée ✅", ephemeral=True)
        except Exception as e:
            print(f"Erreur approbation suggestion {self.suggestion['id']} : {e}")
            await interaction.response.send_message("❌ Erreur lors de l'approbation", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await has_permission(interaction.user, interaction.guild):
            await interaction.response.send_message("⛔ Tu n’as pas la permission", ephemeral=True)
            return
        try:
            supabase.table("suggestions_fiches") \
                .update({"status": "rejected", "updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", self.suggestion["id"]).execute()
            await interaction.response.send_message(f"Suggestion {self.suggestion['id']} refusée ❌", ephemeral=True)
        except Exception as e:
            print(f"Erreur rejet suggestion {self.suggestion['id']} : {e}")
            await interaction.response.send_message("❌ Erreur lors du rejet", ephemeral=True)

async def has_permission(user: discord.User, guild: discord.Guild) -> bool:
    """Vérifie si l'utilisateur a les permissions nécessaires."""
    app_info = await bot.application_info()
    if user.id == app_info.owner.id:
        return True
    member = guild.get_member(user.id)
    if not member:
        return False
    authorized_roles = ["Modérateur", "Admin"]
    return any(role.name in authorized_roles for role in member.roles)

async def notify_owner(message):
    """Envoie une notification au propriétaire du bot."""
    app_info = await bot.application_info()
    owner = app_info.owner
    await owner.send(message)

bot.run(TOKEN)
