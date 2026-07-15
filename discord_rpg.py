import discord
from discord.ext import commands
from dotenv import load_dotenv
import database
import rpg_database
import sqlite3
import os

# Init permissions
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Init command bot prefix wrapper
bot = commands.Bot(command_prefix="!", intents=intents)
load_dotenv

@bot.event
async def on_ready():
    print("==================================================")
    print(f"🤖 DISCORD BOT ACTIVE: Logged in as {bot.user.name} ({bot.user.id})")
    print("📂 Synchronized with gamba_bot.db!")
    print("==================================================")

    # Init RPG database tables (if not yet created)
    rpg_database.init_rpg_db()

    try:
        # Sync / commands with Discord server
        synced = await bot.tree.sync()
        print(f"✨ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"⚠️ Slash command sync failure: {e}")

# ==================================
# GUI: CLASS SELECT MENU
# =================================

class ClassSelectMenu(discord.ui.Select):
    def __init__(self):
        # Define drop-down menu parameters
        options = [
            discord.SelectOption(label="Warrior", description="High Physical damage and Scaling Defense.", emoji="⚔️"),
            discord.SelectOption(label="Wizard", description="Spellcaster of Lightning, Fire, and Ice.", emoji="🪄"),
            discord.SelectOption(label="Archer", description="Evasive, Casts Debuffs, Multiple Strikes", emoji="🏹"),
            discord.SelectOption(label="Valkyrie", description="Well rounded, but slow stat growth.", emoji="🛡️")
        ]
        super().__init__(placeholder="Choose your Class archetype...", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        chosen_class = self.values[0]
        caller_discord_username = interaction.user.name

        verified_yt_handle = database.get_youtube_handle_from_discord(caller_discord_username)
        if not verified_yt_handle:
            await interaction.response.send_message(
                content=(
                    f"❌ [ACCOUNT LINK REQUIRED] Your Discord username (`{caller_discord_username}) "
                    f"is not linked to a YouTube database profile yet!\n"
                    f"💬 Please contact an Administrator with your YouTube handle to link your profile."
                ),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)
        reply_string = rpg_database.register_new_character(verified_yt_handle, chosen_class.lower())

        if "❌" in reply_string:
            await interaction.followup.send(content=reply_string)
            return

        stats = rpg_database.fetch_class_base_stats(chosen_class.lower())
        if not stats:
            await interaction.followup.send(
                content="❌ **GSPREAD CONN ERROR**: Cannot extract stats from RPGConfig spreadsheet.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"✨ HERO AWAKENED: {interaction.user.display_name} ✨",
            description=f"Welcome, traveler. Your hero contract has been formed!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Class Archetype", value=f"**Level 1 {chosen_class}**", inline=False)
        embed.add_field(name="❤️ Max Health (HP)", value=str(stats["hp"]), inline=True)
        embed.add_field(name="🔮 Max Mana (MP)", value=str(stats["mp"]), inline=True)
        embed.add_field(name="🪙 Gold Balance", value="0 Gold", inline=True)
        embed.add_field(
            name="⚔️ Core Attributes Matrix",
            value=f"`💪 STR: {stats['str']}` | `🎯 DEX: {stats['dex']}` | `🧠 INT: {stats['int']}`\n`🩸 VIT: {stats['vit']}` | `⚡ ENG: {stats['eng']}`",
            inline=False
        )
        embed.set_footer(text="💰 Creation Cost of 5,000 points deducted from acount. Thank you for your purchase!")
        await interaction.edit_original_response(content=f"✅ Registration verified successfully!", view=None)
        await interaction.channel.send(embed=embed)

class ClassSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(ClassSelectMenu())

# ==================================
# SLASH COMMAND: create
# ==================================

@bot.tree.command(name="create", description="Create a new Hero! (Costs 5,000 channel points)")
async def create(interaction:discord.Interaction):
    view = ClassSelectView()
    await interaction.response.send_message("🛡️ CHOOSE YOUR CLASS ARCHETYPE BELOW 🛡️", view=view)

# ==================================
# SLASH COMMAND: status
# ==================================

@bot.tree.command(name="status", description="Inspect Hero Card (Status, Equipment, Gold).")
async def status(interaction: discord.Interaction):
    caller_discord_username = interaction.user.name
    
    verified_yt_handle = database.get_youtube_handle_from_discord(caller_discord_username)
    
    if not verified_yt_handle:
        await interaction.response.send_message(
                content=(
                    f"❌ [ACCOUNT LINK REQUIRED] Your Discord username (`{caller_discord_username}) "
                    f"is not linked to a YouTube database profile yet!\n"
                    f"💬 Please contact an Administrator with your YouTube handle to link your profile."
                ),
                ephemeral=True
            )
        return

    await interaction.response.defer(ephemeral=False)

    conn = sqlite3.connect(rpg_database.RPG_DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT class_name, level, xp, gold, current_hp, max_hp, current_mp, max_mp,
               base_str, base_dex, base_int, base_vit, base_eng, stamina
        FROM characters WHERE username = ?
    ''', (verified_yt_handle,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await interaction.followup.send(
            content=f"❌ No Hero profile found, {interaction.user.display_name}! Type `/create` and choose a class."
        )
        return

    c_class, lvl, xp, gold, cur_hp, max_hp, cur_mp, max_mp, b_str, b_dex, b_int, b_vit, b_eng, stam = row
    
    stream_prestige = database.get_prestige_level(verified_yt_handle)
    prestige_text = f" 🏅 [Prestige {stream_prestige}]" if stream_prestige > 0 else ""

    embed = discord.Embed(
        title=f"🛡️ HERO PROFILE CARD: {interaction.user.display_name} {prestige_text} 🛡️",
        description=f"Bound to YouTube Stream Handle: **{verified_yt_handle}**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    # Core Class & Progression Bar Rows
    embed.add_field(name="Class Archetype", value=f"**Level {lvl} {c_class}**", inline=True)
    embed.add_field(name="✨ Total Experience (XP)", value=f"`{xp:,} XP`", inline=True)
    embed.add_field(name="🏃 Active Stamina", value=f"`{stam}/3 Stamina`", inline=True)
    
    # Resource Pool Boundaries (Formatted as Integers)
    embed.add_field(name="❤️ Health Points (HP)", value=f"**{int(cur_hp)} / {int(max_hp)}**", inline=True)
    embed.add_field(name="🔮 Mana Points (MP)", value=f"**{int(cur_mp)} / {int(max_mp)}**", inline=True)
    embed.add_field(name="🪙 Gheed Bank Wallet", value=f"**{int(gold):,} Gold**", inline=True)
    
    # D2 Attribute Matrix Columns
    embed.add_field(
        name="⚔️ Core Attributes Matrix (Dynamic Integers)",
        value=(
            f"`💪 STR: {int(b_str)}` | `🎯 DEX: {int(b_dex)}` | `🧠 INT: {int(b_int)}`\n"
            f"`🩸 VIT: {int(b_vit)}` | `⚡ ENG: {int(b_eng)}`"
        ),
        inline=False
    )
    embed.set_footer(text="🐞 PLACEHOLDER 'CHANNEL POINT TO GOLD VIA GHEED' MESSAGE")

    # Erase processing delay notice, deliver embed data directly to server channel
    await interaction.edit_original_response(embed=embed)

# ===================================================
# SLASH COMMAND REGISTRATION ENGINE: /bank deposit
# ===================================================

@bot.tree.command(name="bank", description="Exchange channel points into Gold via Gheed. (ExchRate = 1000pts -> 1g)")
@discord.app_commands.describe(amount="Number of channel points to exchange, or type 'all'")
async def bank_deposit(interaction: discord.Interaction, amount: str):
    caller_discord_username = interaction.user.name
    
    verified_yt_handle = database.get_youtube_handle_from_discord(caller_discord_username)
    
    if not verified_yt_handle:
        await interaction.response.send_message(
                content=(
                    f"❌ [ACCOUNT LINK REQUIRED] Your Discord username (`{caller_discord_username}) "
                    f"is not linked to a YouTube database profile yet!\n"
                    f"💬 Please contact an Administrator with your YouTube handle to link your profile."
                ),
                ephemeral=True
            )
        return

    await interaction.response.defer(ephemeral=False)

    reply_string = rpg_database.deposit_to_gheed(verified_yt_handle, amount.strip().lower())

    if "❌" in reply_string:
        await interaction.followup.send(content=reply_string)
        return
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gheed_image_path = os.path.join(base_dir, "__graphics__", "gheedSprite.png")
    if os.path.exists(gheed_image_path):
        file_attachment = discord.File(gheed_image_path, filename="gheedSprite.png")
        thumbnail_url = "attachment://gheed.png"
    else:
        file_attachment = None
        thumbnail_url = None

    embed = discord.Embed(
        title="💰 GHEED TRANSACTION RECEIPT 💰",
        description=f"Transaction cleared for stream handle: **{verified_yt_handle}**",
        color=discord.Color.green()
    )

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.add_field(name="Vault Ledger Status", value=reply_string, inline=False)
    embed.set_footer(text="Gheed: 'Pleasure doing business with ya, partner. Come back when you line your pockets again!'")

    if file_attachment:
        await interaction.edit_original_response(file=file_attachment, embed=embed)
    else:
        await interaction.edit_original_response(embed=embed)

# ======================================
# TOWN HUB: MAIN ACTION BUTTONS PANEL
# ======================================

class TownHubView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_verified_user(self, interaction: discord.Interaction):
        caller_name = interaction.user.name
        yt_handle = database.get_youtube_handle_from_discord(caller_name)
        if not yt_handle:
            await interaction.response.send_message(
                content=(
                    f"❌ [ACCOUNT LINK REQUIRED] Your Discord username (`{caller_discord_username}) "
                    f"is not linked to a YouTube database profile yet!\n"
                    f"💬 Please contact an Administrator with your YouTube handle to link your profile."
                ),
                ephemeral=True
            )
            return None
        return yt_handle
    
    @discord.ui.button(label="💤 Rest at Inn (2 Gold)", style=discord.ButtonStyle.green, custom_id="hub_inn")
    async def rest_inn_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        yt_handle = await self.get_verified_user(interaction)
        if not yt_handle: return
        await interaction.response.defer(ephemeral=True)
        reply_msg = rpg_database.rest_at_inn(yt_handle)
        await interaction.followup.send(content=reply_msg, ephemeral=True)

    @discord.ui.button(label="⚔️ Visit Blacksmith", style=discord.ButtonStyle.blurple, custom_id="hub_shop")
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            content="🛡️ **CHARSI'S ARMORY**: 'Looking for weapons or armor? You've come to the right place!'\n*(Charsi item tier menu coming soon...)*",
            ephemeral=True
        )

    @discord.ui.button(label="🔮 Magick Manor", style=discord.ButtonStyle.secondary, custom_id="hub_spells")
    async def spell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            content="🔮 **MAGICK MANOR**: Learn magical spells and abilities to use in combat.\n*(Spell and Ability shop matrix coming soon...)",
            ephemeral=True
        )

# ===========================================
# SLASH COMMAND REGISTRATION ENGINE: /town
# ===========================================

@bot.tree.command(name="town", description="Enter the Rogue Encampment to rest, shop or manage gear.")
async def town(interaction: discord.Interaction):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    town_image_path = os.path.join(base_dir, "__graphics__", "town.png")
    file_attachment = None
    thumbnail_url = None

    if os.path.exists(town_image_path):
        file_attachment = discord.File(town_image.path, filename="town.png")
        thumbnail_url = "attachment://town.png"

    embed = discord.Embed(
        title="⛺ ROGUE ENCAMPMENT ⛺"
        description=(
            "Welcome to the Rogue Encampment. Here you can exchange channel points for Gold, "
            "heal wounds at the Inn, and prepare yourself for battles to come.\n\n"
            "**Available Services:**\n"
            "💤 **Deckard's Inn**: Full HP Recovery for a flat fee of **2 Gold**.\n"
            "⚒️ **Charsi's Forge**: Purchase or Upgrade Weapons and Armor.\n"
            "🔮 **Magick's Manor**: Learn Spells and Abilities.\n"
        ),
        color=discord.Color.dark_green()
    )
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    embed.set_footer(text="Click an option button below to interact with the town merchants.")

    view = TownHubView()
    if file_attachment:
        await interaction.response.send_message(file=file_attachment, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)





######################
### START PIPELINE ###
######################
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ BOOT FAILURE: Could not locate 'DISCORD_BOT_TOKEN' inside local .env varibale!")
    else:
        bot.run(token)