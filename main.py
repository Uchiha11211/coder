import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from colorama import init, Fore, Style
from utils.logger import log
from utils.image import modify_image

# --- Performance Tweaks (Optional) ---
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# Load environment variables (adjust path as needed)
load_dotenv(dotenv_path="config/.env")
init()

TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_PREFIX = os.getenv("PREFIX", "+")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
BOT_NAME = os.getenv("BOT_NAME", "gacha").lower()

if not TOKEN:
    print(f"{Fore.RED}❌ Error: DISCORD_TOKEN is missing from .env!{Style.RESET_ALL}")
    exit(1)

# Store custom prefixes
custom_prefixes = {}
PREFIX_FILE = "config/prefix.txt"

# Function to get prefix for a guild
def get_prefix(bot, message):
    if not message.guild:
        return DEFAULT_PREFIX
    return custom_prefixes.get(str(message.guild.id), DEFAULT_PREFIX)

# Load custom prefixes
def load_prefixes():
    global custom_prefixes
    try:
        if os.path.exists(PREFIX_FILE):
            with open(PREFIX_FILE, "r") as f:
                custom_prefixes = json.load(f)
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️ Warning: Could not load custom prefixes: {e}{Style.RESET_ALL}")
        custom_prefixes = {}

# Save custom prefixes
def save_prefixes():
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(PREFIX_FILE), exist_ok=True)
        with open(PREFIX_FILE, "w") as f:
            json.dump(custom_prefixes, f, indent=4)
    except Exception as e:
        print(f"{Fore.RED}❌ Error: Could not save custom prefixes: {e}{Style.RESET_ALL}")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)
bot.owner_id = OWNER_ID

# -----------------------------
# Global state and settings
# -----------------------------
SETTINGS_FILE = "settings.json"
settings = {
    "logger": False,
    "paused": [],
    "blocked": [],
    "imgurl_enabled": False,
    "pinging_enabled": {},
    "whitelist": {}
}

pinging_enabled = {}
blocked_users = set()
paused_servers = set()
whitelisted_channels = {}
image_metadata = {}

def load_settings():
    global settings, blocked_users, pinging_enabled, paused_servers, whitelisted_channels
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            loaded = json.load(f)
            settings.update(loaded)
            if "imgurl_enabled" not in settings:
                settings["imgurl_enabled"] = False
            if "paused" not in settings:
                settings["paused"] = []
            if "whitelist" not in settings:
                settings["whitelist"] = {}
            if "pinging_enabled" in settings:
                pinging_enabled.clear()
                for k, v in settings["pinging_enabled"].items():
                    try:
                        pinging_enabled[int(k)] = v
                    except ValueError:
                        pass
            settings["blocked"] = [int(x) for x in settings.get("blocked", [])]
            settings["paused"] = [int(x) for x in settings.get("paused", [])]
            whitelisted_channels.clear()
            for guild_key, channels in settings.get("whitelist", {}).items():
                whitelisted_channels[str(guild_key)] = [int(ch) for ch in channels]
    else:
        settings = {
            "logger": False,
            "paused": [],
            "blocked": [],
            "imgurl_enabled": False,
            "pinging_enabled": {},
            "whitelist": {}
        }
    blocked_users.clear()
    blocked_users.update(settings["blocked"])
    paused_servers.clear()
    paused_servers.update(settings["paused"])

def save_settings():
    settings["blocked"] = list(blocked_users)
    settings["paused"] = list(paused_servers)
    settings["pinging_enabled"] = {str(k): v for k, v in pinging_enabled.items()}
    settings["whitelist"] = whitelisted_channels.copy()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Attach settings to bot object
def attach_settings_to_bot(bot_instance):
    bot_instance.settings = settings
    bot_instance.blocked_users = blocked_users
    bot_instance.paused_servers = paused_servers
    bot_instance.pinging_enabled = pinging_enabled
    bot_instance.whitelisted_channels = whitelisted_channels
    bot_instance.save_settings = save_settings
    bot_instance.load_settings = load_settings

def get_whitelist_str(guild_id):
    guild_key = str(guild_id)
    if guild_key in whitelisted_channels and whitelisted_channels[guild_key]:
        return ", ".join(f"<#{ch}>" for ch in whitelisted_channels[guild_key])
    return "No channels whitelisted."

def print_banner():
    server_count = len(bot.guilds)
    command_count = len(bot.commands)
    bot_name = bot.user.name if bot.user else 'N/A'
    bot_id = bot.user.id if bot.user else 'N/A'
    
    banner_width = 70
    
    def center_text(text, width, fill_char=' '):
        text_len = len(text)
        padding = width - text_len
        left_pad = padding // 2
        right_pad = padding - left_pad
        return fill_char * left_pad + text + fill_char * right_pad
    
    lines = [
        f"{Fore.CYAN}╔{'═' * (banner_width - 2)}╗",
        f"║{center_text('🚀  BOT LAUNCHED SUCCESSFULLY!', banner_width - 2)}║",
        f"╠{'═' * (banner_width - 2)}╣"
    ]
    
    info_items = [
        ("Bot Name", f"{Fore.GREEN}{bot_name}{Fore.CYAN}"),
        ("Bot ID", f"{Fore.GREEN}{bot_id}{Fore.CYAN}"),
        ("Default Prefix", f"{Fore.GREEN}{DEFAULT_PREFIX}{Fore.CYAN}"),
        ("Servers", f"{Fore.GREEN}{server_count}{Fore.CYAN}"),
        ("Commands", f"{Fore.GREEN}{command_count}{Fore.CYAN}")
    ]
    
    for label, value in info_items:
        raw_value = str(value).replace(Fore.GREEN, "").replace(Fore.CYAN, "")
        padding = banner_width - len(label) - len(raw_value) - 7
        lines.append(f"║  {label} : {value}{' ' * padding}║")
    
    lines.extend([
        f"╠{'═' * (banner_width - 2)}╣",
        f"║{center_text('Made with ' + Fore.RED + '❤️' + Fore.CYAN + '  by _dr_misterio_', banner_width - 2)}║",
        f"╚{'═' * (banner_width - 2)}╝{Style.RESET_ALL}"
    ])
    
    for line in lines:
        print(line)

# -----------------------------
# Global Command Check
# -----------------------------
@bot.check
async def global_command_check(ctx):
    if ctx.guild:
        guild_id = ctx.guild.id
        
        # Reload settings in real-time for accurate checking
        load_settings()
        
        # Check if user is blocked globally
        if ctx.author.id in blocked_users:
            embed = discord.Embed(
                title="🚫 User Blocked",
                description="❌ **You are blocked from using this bot.**\n\n📧 Contact the bot owner if you believe this is an error.",
                color=discord.Color.red()
            )
            embed.add_field(name="🔍 Status", value="Blocked", inline=True)
            embed.add_field(name="👤 User", value=ctx.author.mention, inline=True)
            embed.set_footer(text="User block is active.")
            await ctx.send(embed=embed, delete_after=15)
            return False
        
        # Check if the bot is paused in this server
        if guild_id in paused_servers:
            embed = discord.Embed(
                title="⏸️ Bot is Currently Paused",
                description="🚫 **The bot is currently paused and not responding to commands.**\n\n✨ This is a temporary state set by the bot administrator.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🔍 Status", value="Paused", inline=True)
            embed.add_field(name="📋 Server", value=ctx.guild.name, inline=True)
            embed.add_field(name="💡 Info", value="The bot will resume when the administrator releases it", inline=False)
            embed.set_footer(text="Bot pause is active in this server.")
            await ctx.send(embed=embed, delete_after=30)
            return False

        # If a whitelist exists (non-empty) for the guild, check that the channel is allowed
        guild_key = str(guild_id)
        if guild_key in whitelisted_channels and whitelisted_channels[guild_key]:
            if ctx.channel.id not in whitelisted_channels[guild_key]:
                embed = discord.Embed(
                    title="🔒 Channel Not Whitelisted",
                    description=f"❌ **This channel is not allowed for bot commands.**\n\n🏠 **Server:** {ctx.guild.name}\n📝 **Channel:** {ctx.channel.mention}",
                    color=discord.Color.orange()
                )
                embed.add_field(name="ℹ️ Info", value="Contact an administrator to add this channel to the whitelist", inline=False)
                embed.set_footer(text="Channel restriction is active.")
                await ctx.send(embed=embed, delete_after=30)
                return False
    return True

# -----------------------------
# Bot Commands
# -----------------------------
@bot.command(name="setprefix")
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, new_prefix: str = None):
    """
    Set a custom prefix for the server. Only administrators can use this command.
    Usage: setprefix <new_prefix>
    """
    if new_prefix is None:
        current_prefix = custom_prefixes.get(str(ctx.guild.id), DEFAULT_PREFIX)
        await ctx.send(f"Current prefix: `{current_prefix}`\nUse `{current_prefix}setprefix <new_prefix>` to change it.")
        return

    if len(new_prefix) > 5:
        await ctx.send("Prefix must be 5 characters or less.")
        return

    custom_prefixes[str(ctx.guild.id)] = new_prefix
    save_prefixes()
    await ctx.send(f"Prefix has been set to `{new_prefix}` for this server.")
    
    if settings["logger"]:
        print(f"{Fore.YELLOW}[LOG] {ctx.author} ({ctx.author.id}) set prefix to '{new_prefix}' in {ctx.guild.name} ({ctx.guild.id}){Style.RESET_ALL}")

@set_prefix.error
async def set_prefix_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need administrator permissions to change the prefix.")
    else:
        await ctx.send(f"An error occurred: {error}")


# -----------------------------
# Bot Events
# -----------------------------
@bot.event
async def setup_hook():
    try:
        from utils.ai import init_module
        await init_module()
        print(f"{Fore.GREEN}✓ Optimized AI module initialized{Style.RESET_ALL}")
        await bot.load_extension("utils.commands")
        await bot.load_extension("utils.image")
        await bot.load_extension("utils.web")
        await bot.load_extension("utils.img2img_cog")
        await bot.load_extension("utils.chat")
        await bot.load_extension("utils.slash_commands")
        print(f"{Fore.GREEN}✓ Loaded all extensions (commands, image, web, img2img_cog){Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✘ Failed to load extensions or initialize AI module: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()

@bot.event
async def on_ready():
    load_prefixes()
    load_settings()
    attach_settings_to_bot(bot)  # Attach settings to bot object
    print_banner()
    print(f"{Fore.GREEN}✓ Logged in as {bot.user.name} ({bot.user.id})!{Style.RESET_ALL}")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"{Fore.GREEN}✓ Synced {len(synced)} slash commands!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✘ Failed to sync slash commands: {e}{Style.RESET_ALL}")

@bot.event
async def on_guild_join(guild):
    """Send a welcome message when the bot joins a new server"""
    try:
        # Try to find a suitable channel to send the welcome message
        target_channel = None
        
        # Priority list of channel names to look for
        preferred_names = ['general', 'chat', 'main', 'welcome', 'lobby', 'talk']
        
        # First, try to find a channel with a preferred name
        for channel in guild.text_channels:
            if channel.name.lower() in preferred_names:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break
        
        # If no preferred channel found, use the first available text channel
        if not target_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break
        
        # If still no channel found, try the system channel
        if not target_channel and guild.system_channel:
            if guild.system_channel.permissions_for(guild.me).send_messages:
                target_channel = guild.system_channel
        
        if target_channel:
            current_prefix = custom_prefixes.get(str(guild.id), DEFAULT_PREFIX)
            
            embed = discord.Embed(
                title=f"👋 Hello {guild.name}!",
                description=f"Thanks for adding **{bot.user.name}** to your server! I'm an AI-powered bot with chat, image generation, and web search capabilities.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🚀 Quick Start",
                value=(
                    f"• **Mention me** `@{bot.user.name}` to chat with me\n"
                    f"• **Activate full mode**: `@{bot.user.name} activate` to make me respond to every message\n"
                    f"• **Get help**: `{current_prefix}help` or `/help` to see all commands"
                ),
                inline=False
            )
            
            embed.add_field(
                name="✨ Key Features",
                value=(
                    "🤖 **AI Chat** - Intelligent conversations with memory\n"
                    "🎨 **Image Generation** - Create images from text\n"
                    "🌐 **Web Search** - Real-time web search with AI responses\n"
                    "🔧 **Customizable** - Set custom prefixes, whitelist channels"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔧 Admin Commands",
                value=(
                    f"`{current_prefix}setprefix <prefix>` - Change bot prefix\n"
                    f"`{current_prefix}whitelist add/remove <channel>` - Manage allowed channels\n"
                    f"`@{bot.user.name} activate/deactivate` - Toggle full response mode"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Use {current_prefix}help for a complete command list • Made with ❤️")
            embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
            
            await target_channel.send(embed=embed)
            print(f"{Fore.GREEN}✓ Sent welcome message to {guild.name} in #{target_channel.name}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️ Could not find a suitable channel to send welcome message in {guild.name}{Style.RESET_ALL}")
            
    except Exception as e:
        print(f"{Fore.RED}✘ Error sending welcome message to {guild.name}: {e}{Style.RESET_ALL}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if message.author.id in blocked_users:
        return

    current_prefix = custom_prefixes.get(str(message.guild.id), DEFAULT_PREFIX)
    
    # Check for @mention commands first
    if bot.user in message.mentions:
        content_lower = message.content.lower()
        
        # @[BOT_NAME] activate
        if 'activate' in content_lower:
            # Check if user is admin
            if message.author.id == OWNER_ID or (message.guild and message.author.guild_permissions.administrator):
                chat_cog = bot.get_cog('ChatCog')
                if chat_cog and hasattr(chat_cog, 'memory'):
                    chat_cog.memory.activate_channel(message.channel.id)
                    embed = discord.Embed(
                        title="🟢 Channel Activated",
                        description=f"✅ Bot will now **respond to ALL messages** in {message.channel.mention}\n\n📝 **Note:** Bot can still respond in other channels when mentioned by name.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="🏠 Channel", value=message.channel.mention, inline=True)
                    embed.add_field(name="📊 Status", value="Fully Active", inline=True)
                    embed.add_field(name="🔧 How to Deactivate", value=f"Use `@{BOT_NAME.capitalize()} deactivate`", inline=False)
                    embed.set_footer(text="Channel activation via mention successful.")
                    await message.reply(embed=embed, mention_author=False)
                else:
                    embed = discord.Embed(
                        title="❌ Error",
                        description="Could not access memory system. Please try again.",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed, mention_author=False)
            else:
                embed = discord.Embed(
                    title="🔒 Admin Only Command",
                    description="You need administrator permissions to use this command!",
                    color=discord.Color.red()
                )
                embed.set_footer(text="This command is restricted to administrators.")
                await message.reply(embed=embed, mention_author=False)
            return
            
        # @[BOT_NAME] deactivate
        elif 'deactivate' in content_lower:
            # Check if user is admin
            if message.author.id == OWNER_ID or (message.guild and message.author.guild_permissions.administrator):
                chat_cog = bot.get_cog('ChatCog')
                if chat_cog and hasattr(chat_cog, 'memory'):
                    if chat_cog.memory.is_channel_active(message.channel.id):
                        chat_cog.memory.deactivate_channel(message.channel.id)
                        embed = discord.Embed(
                            title="🔴 Channel Deactivated",
                            description=f"✅ Bot will **no longer respond to all messages** in {message.channel.mention}\n\n📝 **Note:** Bot can still respond when mentioned by name.",
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="🏠 Channel", value=message.channel.mention, inline=True)
                        embed.add_field(name="📊 Status", value="Normal Mode", inline=True)
                        embed.add_field(name="🔧 How to Reactivate", value=f"Use `@{BOT_NAME.capitalize()} activate`", inline=False)
                        embed.set_footer(text="Channel deactivation via mention successful.")
                        await message.reply(embed=embed, mention_author=False)
                    else:
                        embed = discord.Embed(
                            title="ℹ️ Already Inactive",
                            description=f"{message.channel.mention} is not currently activated.",
                            color=discord.Color.blue()
                        )
                        embed.add_field(name="💡 Tip", value=f"Use `@{BOT_NAME.capitalize()} activate` to make bot respond to all messages", inline=False)
                        await message.reply(embed=embed, mention_author=False)
                else:
                    embed = discord.Embed(
                        title="❌ Error",
                        description="Could not access memory system. Please try again.",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed, mention_author=False)
            else:
                embed = discord.Embed(
                    title="🔒 Admin Only Command",
                    description="You need administrator permissions to use this command!",
                    color=discord.Color.red()
                )
                embed.set_footer(text="This command is restricted to administrators.")
                await message.reply(embed=embed, mention_author=False)
            return
            
        # @[BOT_NAME] wack (reload)
        elif 'wack' in content_lower:
            # Check if user is admin
            if message.author.id == OWNER_ID or (message.guild and message.author.guild_permissions.administrator):
                chat_cog = bot.get_cog('ChatCog')
                if chat_cog and hasattr(chat_cog, 'memory'):
                    # Clear STM for all channels in this guild
                    cleared_channels = 0
                    for channel in message.guild.channels:
                        if isinstance(channel, (discord.TextChannel, discord.Thread)):
                            memory_key = f"{message.guild.id}_{channel.id}"
                            if memory_key in chat_cog.memory.stm:
                                chat_cog.memory.reset(memory_key)
                                cleared_channels += 1
                    
                    embed = discord.Embed(
                        title="🔄 Server Reload Complete",
                        description=f"✅ Bot has been **reloaded** for **{message.guild.name}**\n\n🧠 **STM (Short-term memory) cleared** for all channels",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="🏠 Server", value=message.guild.name, inline=True)
                    embed.add_field(name="🧹 Channels Cleared", value=f"{cleared_channels} channels", inline=True)
                    embed.add_field(name="📊 Memory Status", value="Fresh start", inline=True)
                    embed.set_footer(text="Server-level reload via mention successful. Bot memory refreshed.")
                    await message.reply(embed=embed, mention_author=False)
                else:
                    embed = discord.Embed(
                        title="❌ Error",
                        description="Could not access memory system. Please try again.",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed, mention_author=False)
            else:
                embed = discord.Embed(
                    title="🔒 Admin Only Command",
                    description="You need administrator permissions to use this command!",
                    color=discord.Color.red()
                )
                embed.set_footer(text="This command is restricted to administrators.")
                await message.reply(embed=embed, mention_author=False)
            return
    
    # Skip dynamic detection if it's a prefix command or slash command
    if message.content.strip().startswith(current_prefix) or message.content.strip().startswith('/'):
        await bot.process_commands(message)
        return
    
    # Also skip if message was processed as a command (to prevent chat interference)
    ctx = await bot.get_context(message)
    if ctx.valid:
        return

    # Check for images in current message and references
    def has_images_in_message(msg):
        return any(att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                  for att in msg.attachments)
    
    def count_images_in_message(msg):
        return len([att for att in msg.attachments 
                   if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))])

    current_images = has_images_in_message(message)
    current_image_count = count_images_in_message(message)
    
    ref_msg = None
    ref_has_images = False
    total_image_count = current_image_count
    
    if message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            ref_has_images = has_images_in_message(ref_msg)
            if ref_has_images:
                total_image_count += count_images_in_message(ref_msg)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # Import fast detection functions
    from utils.ai import (
        detect_image_generation_intent,
        detect_image_editing_intent, 
        detect_web_search_intent,
        detect_image_merge_intent
    )

    # Check if bot should respond with dynamic detection
    # Only respond if: 1) Channel is activated, OR 2) bot name keyword is mentioned (respecting whitelist)
    should_respond = False
    
    # Check if channel is activated
    chat_cog = bot.get_cog('ChatCog')
    if chat_cog and hasattr(chat_cog, 'memory'):
        if chat_cog.memory.is_channel_active(message.channel.id):
            should_respond = True
    
    # Check if bot name keyword is mentioned (case insensitive)
    if not should_respond:
        message_lower = message.content.lower()
        if BOT_NAME in message_lower:
            # Check whitelist restrictions for bot name keyword
            if message.guild:
                guild_key = str(message.guild.id)
                if guild_key in whitelisted_channels and whitelisted_channels[guild_key]:
                    # Whitelist exists and is non-empty, check if current channel is whitelisted
                    if message.channel.id in whitelisted_channels[guild_key]:
                        should_respond = True
                else:
                    # No whitelist restrictions, respond in any channel
                    should_respond = True
            else:
                # DM - always respond to bot name keyword
                should_respond = True
    
    # If bot shouldn't respond, return early (skip dynamic detection)
    if not should_respond:
        return
    
    # Use clean message content without attachment contamination for detection
    clean_message_content = message.content.strip()
    
    # Fast dynamic detection (< 5ms total)
    # CRITICAL: If images are present, it's NEVER text-to-image generation (per requirements)
    has_any_images = current_images or ref_has_images
    wants_generation = detect_image_generation_intent(clean_message_content) and not has_any_images
    wants_editing = detect_image_editing_intent(clean_message_content, has_any_images)
    wants_web_search = detect_web_search_intent(clean_message_content)
    wants_merge = detect_image_merge_intent(clean_message_content, total_image_count)

    # Handle image merging (requires 2+ images)
    if wants_merge and total_image_count >= 2:
        async with message.channel.typing():
            image_urls = []
            
            # Collect images from current message
            for att in message.attachments:
                if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    image_urls.append(att.url)
            
            # Collect images from referenced message
            if ref_msg:
                for att in ref_msg.attachments:
                    if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_urls.append(att.url)
            
            if len(image_urls) >= 2:
                from utils.image import generate_image_merge
                from utils.ai import classify_prompt
                
                # Extract merge prompt (remove "merge" keyword) using clean content
                import re
                merge_prompt = re.sub(r'(?i)\bmerge\b', '', clean_message_content).strip()
                if not merge_prompt:
                    merge_prompt = "combine these images"
                
                # NSFW check
                try:
                    nsfw_check = await classify_prompt(merge_prompt)
                    if nsfw_check == "NSFW":
                        embed = discord.Embed(
                            title="🚫 NSFW Content Detected",
                            description="NSFW content detected in merge request.",
                            color=discord.Color.red()
                        )
                        await message.channel.send(embed=embed, reference=message, delete_after=30)
                        return
                except Exception:
                    pass
                
                img_data, final_url, error = await generate_image_merge(merge_prompt, image_urls)
                
                if img_data and error is None:
                    # Reset BytesIO position to ensure clean read
                    img_data.seek(0)
                    file = discord.File(img_data, filename="merged_image.png")
                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                    allowed = discord.AllowedMentions(replied_user=ping_enabled)
                    
                    try:
                        sent_msg = await message.channel.send(file=file, reference=message, allowed_mentions=allowed)
                        
                        # Store metadata
                        image_metadata[str(sent_msg.id)] = {
                            "prompt": merge_prompt,
                            "seed": None,
                            "type": "merge",
                            "source_images": image_urls
                        }
                        return
                    except discord.HTTPException as e:
                        if e.code == 20009:  # Explicit content cannot be sent
                            embed = discord.Embed(
                                title="🚫 Content Blocked",
                                description="❌ **NSFW content detected by Discord**\n\nThe merged image contains explicit content that cannot be sent.",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="🛡️ Content Policy", value="Please try a different prompt or different source images", inline=False)
                            embed.set_footer(text="Content moderation is active to ensure safe usage")
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        else:
                            embed = discord.Embed(
                                title="❌ Merge Failed",
                                description=f"Failed to send merged image: {str(e)}",
                                color=discord.Color.red()
                            )
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        return
                else:
                    embed = discord.Embed(
                        title="❌ Merge Failed",
                        description=f"Failed to merge images: {error or 'Unknown error'}",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed, reference=message, delete_after=30)
                    return

    # Handle batch image editing (2+ images without merge)
    if wants_editing and total_image_count >= 2 and not wants_merge:
        async with message.channel.typing():
            image_urls = []
            
            # Collect images from current message
            for att in message.attachments:
                if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    image_urls.append(att.url)
            
            # Collect images from referenced message
            if ref_msg:
                for att in ref_msg.attachments:
                    if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_urls.append(att.url)
            
            if len(image_urls) >= 2:
                from utils.img2img_cog import generate_img2img_with_retry
                from utils.ai import classify_prompt
                import random
                
                # NSFW check
                try:
                    nsfw_check = await classify_prompt(clean_message_content)
                    if nsfw_check == "NSFW":
                        embed = discord.Embed(
                            title="🚫 NSFW Content Detected",
                            description="NSFW content detected in editing request.",
                            color=discord.Color.red()
                        )
                        await message.channel.send(embed=embed, reference=message, delete_after=30)
                        return
                except Exception:
                    pass
                edited_files = []
                failed_edits = []
                
                # Process each image individually
                for i, image_url in enumerate(image_urls):
                    try:
                        seed = random.randint(100000, 999999)
                        img_data, final_url, error = await generate_img2img_with_retry(clean_message_content, image_url, seed=seed)
                        
                        if img_data:
                            filename = f"edited_image_{i+1}.png"
                            edited_files.append(discord.File(img_data, filename=filename))
                        else:
                            failed_edits.append(f"Image {i+1}: {error or 'Unknown error'}")
                    except Exception as e:
                        failed_edits.append(f"Image {i+1}: {str(e)}")
                
                # Send results
                if edited_files:
                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                    allowed = discord.AllowedMentions(replied_user=ping_enabled)
                    
                    try:
                        # Send all edited images
                        sent_msg = await message.channel.send(
                            files=edited_files, 
                            reference=message, 
                            allowed_mentions=allowed
                        )
                        
                        # Store metadata for the response message
                        image_metadata[str(sent_msg.id)] = {
                            "prompt": clean_message_content,
                            "type": "batch_edit",
                            "source_images": image_urls,
                            "total_images": len(edited_files),
                            "failed_count": len(failed_edits)
                        }
                    except discord.HTTPException as e:
                        if e.code == 20009:  # Explicit content cannot be sent
                            embed = discord.Embed(
                                title="🚫 Content Blocked",
                                description="❌ **NSFW content detected by Discord**\n\nOne or more edited images contain explicit content that cannot be sent.",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="🛡️ Content Policy", value="Please try a different prompt that complies with content guidelines", inline=False)
                            embed.set_footer(text="Content moderation is active to ensure safe usage")
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        else:
                            embed = discord.Embed(
                                title="❌ Batch Editing Failed",
                                description=f"Failed to send edited images: {str(e)}",
                                color=discord.Color.red()
                            )
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        return
                    
                    # Send error summary if some failed
                    if failed_edits:
                        error_msg = f"⚠️ Some images failed to edit:\n" + "\n".join(failed_edits[:3])
                        if len(failed_edits) > 3:
                            error_msg += f"\n... and {len(failed_edits) - 3} more"
                        embed = discord.Embed(
                            title="Partial Success",
                            description=error_msg,
                            color=discord.Color.orange()
                        )
                        await message.channel.send(embed=embed, delete_after=30)
                else:
                    # All edits failed
                    error_list = "\n".join(failed_edits[:5])
                    if len(failed_edits) > 5:
                        error_list += f"\n... and {len(failed_edits) - 5} more errors"
                    embed = discord.Embed(
                        title="❌ Batch Editing Failed",
                        description=f"Failed to edit any images:\n{error_list}",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed, reference=message, delete_after=30)
                return

    # Handle single image editing (requires images to be present)
    if wants_editing and (current_images or ref_has_images) and total_image_count == 1:
        async with message.channel.typing():
            image_url = None
            
            # Get reference image URL
            if current_images:
                for att in message.attachments:
                    if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_url = att.url
                        break
            elif ref_has_images and ref_msg:
                for att in ref_msg.attachments:
                    if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_url = att.url
                        break
            
            if image_url:
                from utils.img2img_cog import generate_img2img_with_retry
                from utils.ai import classify_prompt
                import random
                
                # NSFW check
                try:
                    nsfw_check = await classify_prompt(clean_message_content)
                    if nsfw_check == "NSFW":
                        embed = discord.Embed(
                            title="🚫 NSFW Content Detected",
                            description="NSFW content detected in editing request.",
                            color=discord.Color.red()
                        )
                        await message.channel.send(embed=embed, reference=message, delete_after=30)
                        return
                except Exception:
                    pass
                
                seed = random.randint(100000, 999999)
                img_data, final_url, error = await generate_img2img_with_retry(clean_message_content, image_url, seed=seed)
                
                if img_data:
                    file = discord.File(img_data, filename="edited_image.png")
                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                    allowed = discord.AllowedMentions(replied_user=ping_enabled)
                    
                    try:
                        sent_msg = await message.channel.send(file=file, reference=message, allowed_mentions=allowed)
                        
                        # Store metadata
                        image_metadata[str(sent_msg.id)] = {
                            "prompt": clean_message_content,
                            "seed": seed,
                            "type": "img2img",
                            "reference_image": image_url
                        }
                        return
                    except discord.HTTPException as e:
                        if e.code == 20009:  # Explicit content cannot be sent
                            embed = discord.Embed(
                                title="🚫 Content Blocked",
                                description="❌ **NSFW content detected by Discord**\n\nThe edited image contains explicit content that cannot be sent.",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="🛡️ Content Policy", value="Please try a different prompt that complies with content guidelines", inline=False)
                            embed.set_footer(text="Content moderation is active to ensure safe usage")
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        else:
                            embed = discord.Embed(
                                title="❌ Editing Failed",
                                description=f"Failed to send edited image: {str(e)}",
                                color=discord.Color.red()
                            )
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        return
                else:
                    embed = discord.Embed(
                        title="❌ Editing Failed", 
                        description=f"Failed to edit image: {error or 'Unknown error'}",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed, reference=message, delete_after=30)
                    return

    # Show error for editing/merging without images
    if wants_editing and not (current_images or ref_has_images):
        embed = discord.Embed(
            title="❌ No Image Found",
            description="Image editing requires an image to be attached or referenced. Please attach an image or reply to a message with an image.",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, reference=message, delete_after=30)
        return
    
    # Handle merge error for single image
    if wants_merge and total_image_count == 1:
        embed = discord.Embed(
            title="❌ Need at least 2 images to merge",
            description="Image merging requires 2 or more images. Please attach multiple images or reply to messages with images.",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, reference=message, delete_after=30)
        return
    
    if wants_merge and total_image_count < 2:
        embed = discord.Embed(
            title="❌ Insufficient Images",
            description="Image merging requires 2 or more images. Please attach multiple images or reply to messages with images.",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, reference=message, delete_after=30)
        return

    # Handle image generation
    if wants_generation:
        from utils.image import generate_image
        from utils.ai import classify_prompt
        
        # NSFW check
        try:
            nsfw_check = await classify_prompt(clean_message_content)
            if nsfw_check == "NSFW":
                embed = discord.Embed(
                    title="🚫 NSFW Content Detected",
                    description="NSFW content detected in generation request.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed, reference=message, delete_after=30)
                return
        except Exception:
            pass
        
        async with message.channel.typing():
            result = await generate_image(clean_message_content, user_id=message.author.id)
            
            if isinstance(result, (tuple, list)) and len(result) >= 3:
                img_data, seed, final_url = result[:3]
                ai_params = result[3] if len(result) >= 4 else None
                
                if img_data and img_data != "NSFW":
                    file = discord.File(img_data, filename="generated_image.png")
                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                    allowed = discord.AllowedMentions(replied_user=ping_enabled)
                    
                    try:
                        sent_msg = await message.channel.send(file=file, reference=message, allowed_mentions=allowed)
                        
                        # Store metadata
                        image_metadata[str(sent_msg.id)] = {
                            "prompt": clean_message_content,
                            "seed": seed,
                            "ai_params": ai_params,
                            "type": "generation"
                        }
                        return
                    except discord.HTTPException as e:
                        if e.code == 20009:  # Explicit content cannot be sent
                            embed = discord.Embed(
                                title="🚫 Content Blocked",
                                description="❌ **NSFW content detected by Discord**\n\nThe generated image contains explicit content that cannot be sent.",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="🛡️ Content Policy", value="Please try a different prompt that complies with content guidelines", inline=False)
                            embed.set_footer(text="Content moderation is active to ensure safe usage")
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        else:
                            embed = discord.Embed(
                                title="❌ Generation Failed",
                                description=f"Failed to send generated image: {str(e)}",
                                color=discord.Color.red()
                            )
                            await message.channel.send(embed=embed, reference=message, allowed_mentions=allowed)
                        return
        
        embed = discord.Embed(
            title="❌ Generation Failed",
            description="Failed to generate image. Please try again.",
            color=discord.Color.red()
        )
        await message.channel.send(embed=embed, reference=message, delete_after=30)
        return

    # Handle web search
    if wants_web_search:
        from utils.web import get_valid_search_results, generate_ai_response, send_long_message
        from utils.ai import load_context_files
        
        async with message.channel.typing():
            search_results = await get_valid_search_results(clean_message_content)
            
            if search_results:
                instructions, personality, backstory = load_context_files()
                system_context = f"{instructions}\n{personality}\n{backstory}".strip()
                
                import datetime
                current_datetime = datetime.datetime.now(datetime.timezone.utc)
                current_date = current_datetime.strftime("%Y-%m-%d")
                current_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
                
                # Override system context for web search to prevent contradictions
                web_system_context = (
                    "You are a helpful AI assistant. Your ONLY job is to provide accurate information based on the search results provided. "
                    "CRITICAL RULES:\n"
                    "1. Use ONLY the information from the search results\n"
                    "2. Never contradict or modify the search results\n"
                    "3. If search results say something, accept it as fact\n"
                    "4. Do not use your own knowledge that conflicts with search results\n"
                    "5. Present the information exactly as found in the search results\n"
                    "6. If unsure, quote the search results directly"
                )
                
                messages = [
                    {"role": "system", "content": web_system_context},
                    {"role": "user", "content": (
                        f"Current date: {current_date}, Current time: {current_time}. "
                        f"User query: {clean_message_content}\n\n"
                        f"SEARCH RESULTS (TRUST THESE COMPLETELY):\n{search_results}\n\n"
                        "Answer the user's question using ONLY the search results above. "
                        "Trust the search results completely, even if they seem unusual."
                    )}
                ]
                
                response, error = await generate_ai_response("gemini-2.0-flash", messages, timeout=30)
                
                if response and not error:
                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                    await send_long_message(message.channel, response, mention_author=ping_enabled)
                    return

    # Handle image analysis (when user sends images but doesn't want editing/merging)
    if has_any_images and not wants_editing and not wants_merge and not wants_generation and not wants_web_search:
        async with message.channel.typing():
            from utils.chat import analyze_image
            import io
            import aiohttp
            
            try:
                # Get the first image for analysis
                image_url = None
                if current_images:
                    for att in message.attachments:
                        if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            image_url = att.url
                            break
                elif ref_has_images and ref_msg:
                    for att in ref_msg.attachments:
                        if att.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            image_url = att.url
                            break
                
                if image_url:
                    # Download the image
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                image_buffer = io.BytesIO(image_data)
                                
                                # Analyze the image
                                analysis = await analyze_image(image_buffer)
                                
                                # If user provided text, use it as context for analysis
                                if message_content.strip():
                                    from utils.ai import generate_response_web, load_context_files
                                    instructions, personality, backstory = load_context_files()
                                    
                                    combined_prompt = f"User message: {message_content}\n\nImage analysis: {analysis}\n\nPlease respond to the user's message with the image context in mind."
                                    
                                    response = await generate_response_web(combined_prompt, instructions)
                                    if response:
                                        ping_enabled = pinging_enabled.get(message.guild.id, True)
                                        allowed = discord.AllowedMentions(replied_user=ping_enabled)
                                        await message.channel.send(response, reference=message, allowed_mentions=allowed)
                                        return
                                else:
                                    # Just provide image analysis
                                    ping_enabled = pinging_enabled.get(message.guild.id, True)
                                    allowed = discord.AllowedMentions(replied_user=ping_enabled)
                                    await message.channel.send(analysis, reference=message, allowed_mentions=allowed)
                                    return
            except Exception as e:
                print(f"Error in image analysis: {e}")
                # Fall through to normal command processing

    await bot.process_commands(message)

@bot.event
async def on_command(ctx):
    if settings["logger"]:
        print(f"{Fore.YELLOW}[CMD] {ctx.author} ({ctx.author.id}) used '{ctx.message.content}' in {ctx.guild.name} ({ctx.guild.id}){Style.RESET_ALL}")

@bot.event
async def on_command_error(ctx, error):
    if settings["logger"]:
        print(f"{Fore.RED}[ERR] Command '{ctx.message.content}' by {ctx.author} ({ctx.author.id}) failed: {error}{Style.RESET_ALL}")
    
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        # Instead of printing a plaintext error, embed it or do what you want
        embed = discord.Embed(
            title="Missing Required Argument",
            description=f"Parameter: {error.param.name}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=30)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error}")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Command on cooldown. Try again in {error.retry_after:.2f} seconds.")
    elif isinstance(error, commands.CheckFailure):
        return
    else:
        await ctx.send(f"An error occurred: {error}")

# -----------------------------
# Cleanup and Shutdown
# -----------------------------
async def cleanup():
    """Perform cleanup actions before bot shutdown"""
    try:
        from utils.ai import shutdown_cleanup_task
        await shutdown_cleanup_task()  # This calls session.close() on all sessions in ai.py
        print(f"{Fore.GREEN}✓ Successfully closed all AI sessions{Style.RESET_ALL}")
    except ImportError:
        # If for some reason we can't import it, do a fallback
        print(f"{Fore.YELLOW}⚠ No shutdown_cleanup_task found in ai.py, skipping session close{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✘ Error during AI session cleanup: {e}{Style.RESET_ALL}")
    
    save_settings()
    save_prefixes()
    print(f"{Fore.GREEN}✓ All settings saved{Style.RESET_ALL}")

@bot.event
async def on_disconnect():
    """Optionally close or cleanup anything needed on a forced disconnect"""
    pass

# Add attributes to bot for global access
bot.blocked_users = blocked_users
bot.pinging_enabled = pinging_enabled
bot.paused_servers = paused_servers
bot.whitelisted_channels = whitelisted_channels
bot.settings = settings
bot.load_settings = load_settings
bot.save_settings = save_settings
bot.get_whitelist_str = get_whitelist_str
bot.image_metadata = image_metadata
bot.image_edit_count = {}  # Track edit counts for images
bot.custom_prefixes = custom_prefixes
bot.load_prefixes = load_prefixes
bot.save_prefixes = save_prefixes
bot.cleanup = cleanup

# Run the bot with proper signal handling
try:
    bot.run(TOKEN)
except KeyboardInterrupt:
    print(f"{Fore.YELLOW}Received keyboard interrupt, shutting down...{Style.RESET_ALL}")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cleanup())
except Exception as e:
    print(f"{Fore.RED}✘ Error during bot startup: {e}{Style.RESET_ALL}")
finally:
    print(f"{Fore.YELLOW}Bot has shut down.{Style.RESET_ALL}")