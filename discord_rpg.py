import discord
from discord.ext import commands
from dotenv import load_dotenv
import database
import rpg_database

# Init permissions
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Init command bot prefix wrapper
bot = commands.Bot(command_prefix="!", intents=intents)
load_dotenv

@bot.event
async def on_ready():
    """ Executes automatically on Discord login """
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

##############################
### GUI: CLASS SELECT MENU ###
##############################

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
        """ Process database lookups on selection """
        chosen_class = self.values[0]
        caller_discord_username = interaction.user.name

        verified_yt_handle = database.get_youtube_handle_from_discord(caller_discord_username)
        if not verified_yt_handle:
            await interaction.response.send_message(
                content=(
                    f"❌ [ACCOUNT LINK REQUIRED] Your Discord username (`{caller_discord_username}) "
                    f"is not linked to a YouTube database profile yet!\n"
                    f"💬 Please DM an Administrator with your YouTube handle to link your profile."
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

#############################
### SLASH COMMAND: create ###
#############################

@bot.tree.command(name="create", description="Create a new Hero! (Costs 5,000 channel points)")
async def create(interaction:discord.Interaction):
    """ Creates a GUI dropdown menu for character creation """
    view = ClassSelectView()
    await interaction.response.send_message("🛡️ CHOOSE YOUR CLASS ARCHETYPE BELOW 🛡️", view=view)


######################
### START PIPELINE ###
######################
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ BOOT FAILURE: Could not locate 'DISCORD_BOT_TOKEN' inside local .env varibale!")
    else:
        bot.run(token)