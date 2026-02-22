# ==========================================================
# 🌌 ELURA – Modular Server Intelligence Platform
# PHASE 1 OF 12 – CORE FOUNDATION
# Public Production Build
# ==========================================================

import os
import discord
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from discord import app_commands
from discord.ext import commands
from supabase import create_client
import google.generativeai as genai

# ==========================================================
# 🔐 ENVIRONMENT VARIABLES
# ==========================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([DISCORD_TOKEN, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY]):
    raise RuntimeError("Missing required environment variables.")

# ==========================================================
# 🧠 LOGGING CONFIGURATION
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ==========================================================
# 🗄 DATABASE MANAGER (Safe Query Layer)
# ==========================================================

class DatabaseManager:
    def __init__(self):
        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def fetch_one(self, table: str, filters: Dict[str, Any]):
        query = self.client.table(table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return result.data[0] if result.data else None

    def fetch_all(self, table: str, filters: Dict[str, Any]):
        query = self.client.table(table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return result.data or []

    def insert(self, table: str, data: Dict[str, Any]):
        return self.client.table(table).insert(data).execute()

    def update(self, table: str, filters: Dict[str, Any], data: Dict[str, Any]):
        query = self.client.table(table).update(data)
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.execute()

    def delete(self, table: str, filters: Dict[str, Any]):
        query = self.client.table(table).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.execute()

db = DatabaseManager()

# ==========================================================
# 🎨 EMBED ENGINE (Centralized Styling)
# ==========================================================

class EmbedEngine:
    COLOR_PRIMARY = 0x5E17EB
    COLOR_ERROR = 0xFF3B3B
    COLOR_SUCCESS = 0x2ECC71
    COLOR_WARNING = 0xF1C40F

    @staticmethod
    def create(title: str, description: str, color: int = COLOR_PRIMARY):
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Elura • Modular Server Intelligence")
        return embed

# ==========================================================
# 🏛 SUBSYSTEM MANAGER
# ==========================================================

class SubsystemManager:

    DEFAULT_SETTINGS = {
        "ai_enabled": False,
        "webhooker_enabled": False,
        "automod_enabled": False,
        "log_channel_id": None,
        "created_at": datetime.utcnow().isoformat()
    }

    @staticmethod
    def ensure_guild(guild_id: int):
        existing = db.fetch_one("guild_settings", {"guild_id": guild_id})
        if not existing:
            db.insert("guild_settings", {
                "guild_id": guild_id,
                **SubsystemManager.DEFAULT_SETTINGS
            })

    @staticmethod
    def is_enabled(guild_id: int, system: str) -> bool:
        settings = db.fetch_one("guild_settings", {"guild_id": guild_id})
        if not settings:
            return False
        return settings.get(f"{system}_enabled", False)

    @staticmethod
    def set_system(guild_id: int, system: str, value: bool):
        db.update(
            "guild_settings",
            {"guild_id": guild_id},
            {f"{system}_enabled": value}
        )

# ==========================================================
# 📊 GLOBAL RATE LIMITER
# ==========================================================

class RateLimiter:
    def __init__(self):
        self.cooldowns = {}

    def check(self, key: str, seconds: int) -> bool:
        now = datetime.utcnow()

        if key not in self.cooldowns:
            self.cooldowns[key] = now
            return True

        if now - self.cooldowns[key] >= timedelta(seconds=seconds):
            self.cooldowns[key] = now
            return True

        return False

rate_limiter = RateLimiter()

# ==========================================================
# 🤖 GEMINI SETUP
# ==========================================================

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel("gemini-pro")

# ==========================================================
# 🚀 BOT INITIALIZATION
# ==========================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=None,
    intents=intents
)

tree = bot.tree

# ==========================================================
# ❗ GLOBAL ERROR HANDLER
# ==========================================================

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    logging.error(f"Slash Command Error: {error}")

    error_embed = EmbedEngine.create(
        "Unexpected Error",
        "An internal error occurred while executing this command.",
        EmbedEngine.COLOR_ERROR
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    except:
        pass

  # ==========================================================
# 🌌 PHASE 2 OF 12 – ADVANCED SUBSYSTEM GOVERNANCE
# ==========================================================

# ----------------------------
# Central Subsystem Registry
# ----------------------------

class SystemRegistry:

    SYSTEMS = {
        "ai": {
            "description": "AI Intelligence & Analysis Engine",
            "default": False
        },
        "webhooker": {
            "description": "Advanced Webhook Management System",
            "default": False
        },
        "automod": {
            "description": "Rule-Based Automatic Moderation Engine",
            "default": False
        }
    }

    @classmethod
    def exists(cls, system: str) -> bool:
        return system in cls.SYSTEMS

    @classmethod
    def description(cls, system: str) -> str:
        return cls.SYSTEMS.get(system, {}).get("description", "Unknown")

    @classmethod
    def all_systems(cls):
        return list(cls.SYSTEMS.keys())


# ----------------------------
# Owner Enforcement
# ----------------------------

def is_guild_owner(interaction: discord.Interaction) -> bool:
    return interaction.guild and interaction.guild.owner_id == interaction.user.id


# ----------------------------
# Governance Logger (Internal)
# ----------------------------

async def governance_log(guild: discord.Guild, message: str):
    logging.info(f"[SYSTEM GOVERNANCE] | Guild: {guild.id} | {message}")

    settings = db.fetch_one("guild_settings", {"guild_id": guild.id})
    if settings and settings.get("log_channel_id"):
        channel = guild.get_channel(settings["log_channel_id"])
        if channel:
            try:
                await channel.send(
                    embed=EmbedEngine.create(
                        "System Governance Event",
                        message,
                        EmbedEngine.COLOR_WARNING
                    )
                )
            except:
                pass


# ----------------------------
# Slash Command Group
# ----------------------------

system_group = app_commands.Group(
    name="system",
    description="Elura subsystem governance (Owner Only)"
)

# ----------------------------
# /system enable
# ----------------------------

@system_group.command(name="enable", description="Enable a subsystem (Owner Only)")
@app_commands.describe(system="Subsystem name")
async def system_enable(interaction: discord.Interaction, system: str):

    SubsystemManager.ensure_guild(interaction.guild.id)

    if not is_guild_owner(interaction):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Permission Denied",
                "Only the **Server Owner** can modify subsystem states.",
                EmbedEngine.COLOR_ERROR
            ),
            ephemeral=True
        )

    system = system.lower()

    if not SystemRegistry.exists(system):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Invalid Subsystem",
                "Available systems:\n• " + "\n• ".join(SystemRegistry.all_systems()),
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    # Rate protection
    if not rate_limiter.check(f"system_toggle_{interaction.guild.id}", 5):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Action Too Fast",
                "Please wait before toggling systems again.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    if SubsystemManager.is_enabled(interaction.guild.id, system):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Already Enabled",
                f"**{system}** is already active.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    SubsystemManager.set_system(interaction.guild.id, system, True)

    await governance_log(
        interaction.guild,
        f"{interaction.user} enabled subsystem: {system}"
    )

    await interaction.response.send_message(
        embed=EmbedEngine.create(
            "Subsystem Enabled",
            f"**{system}** has been successfully enabled.\n\n"
            f"{SystemRegistry.description(system)}",
            EmbedEngine.COLOR_SUCCESS
        )
    )


# ----------------------------
# /system disable
# ----------------------------

@system_group.command(name="disable", description="Disable a subsystem (Owner Only)")
@app_commands.describe(system="Subsystem name")
async def system_disable(interaction: discord.Interaction, system: str):

    if not is_guild_owner(interaction):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Permission Denied",
                "Only the **Server Owner** can modify subsystem states.",
                EmbedEngine.COLOR_ERROR
            ),
            ephemeral=True
        )

    system = system.lower()

    if not SystemRegistry.exists(system):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Invalid Subsystem",
                "Available systems:\n• " + "\n• ".join(SystemRegistry.all_systems()),
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    if not rate_limiter.check(f"system_toggle_{interaction.guild.id}", 5):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Action Too Fast",
                "Please wait before toggling systems again.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    if not SubsystemManager.is_enabled(interaction.guild.id, system):
        return await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Already Disabled",
                f"**{system}** is already inactive.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )

    SubsystemManager.set_system(interaction.guild.id, system, False)

    await governance_log(
        interaction.guild,
        f"{interaction.user} disabled subsystem: {system}"
    )

    await interaction.response.send_message(
        embed=EmbedEngine.create(
            "Subsystem Disabled",
            f"**{system}** has been disabled.",
            EmbedEngine.COLOR_WARNING
        )
    )


# ----------------------------
# /system status
# ----------------------------

@system_group.command(name="status", description="View subsystem status")
async def system_status(interaction: discord.Interaction):

    SubsystemManager.ensure_guild(interaction.guild.id)

    settings = db.fetch_one("guild_settings", {"guild_id": interaction.guild.id})

    lines = []

    for system in SystemRegistry.all_systems():
        enabled = settings.get(f"{system}_enabled", False)
        state = "🟢 Enabled" if enabled else "🔴 Disabled"
        lines.append(f"**{system}** — {state}\n{SystemRegistry.description(system)}\n")

    await interaction.response.send_message(
        embed=EmbedEngine.create(
            "Elura Subsystem Status",
            "\n".join(lines)
        )
    )

# ----------------------------
# Register Slash Group
# ----------------------------

tree.add_command(system_group)

# ==========================================================
# 🌌 PHASE 3 OF 12 – ADVANCED AI INTELLIGENCE ENGINE
# Public-Grade AI Subsystem
# ==========================================================

# ==========================================================
# ⚙️ AI CONFIGURATION
# ==========================================================

AI_DAILY_LIMIT = 30
AI_USER_COOLDOWN = 12
AI_TIMEOUT_SECONDS = 20
AI_CONTEXT_LIMIT = 75  # number of messages for channel analysis


# ==========================================================
# 📊 AI USAGE TRACKING ENGINE
# ==========================================================

class AIUsageManager:

    @staticmethod
    def today():
        return datetime.utcnow().date().isoformat()

    @staticmethod
    def get_record(guild_id: int):
        return db.fetch_one(
            "ai_usage",
            {"guild_id": guild_id, "date": AIUsageManager.today()}
        )

    @staticmethod
    def get_usage(guild_id: int) -> int:
        record = AIUsageManager.get_record(guild_id)
        return record["usage_count"] if record else 0

    @staticmethod
    def increment(guild_id: int):
        record = AIUsageManager.get_record(guild_id)

        if not record:
            db.insert("ai_usage", {
                "guild_id": guild_id,
                "date": AIUsageManager.today(),
                "usage_count": 1
            })
        else:
            db.update(
                "ai_usage",
                {"guild_id": guild_id, "date": AIUsageManager.today()},
                {"usage_count": record["usage_count"] + 1}
            )

    @staticmethod
    def remaining(guild_id: int) -> int:
        return max(0, AI_DAILY_LIMIT - AIUsageManager.get_usage(guild_id))


# ==========================================================
# 🧠 AI PROMPT BUILDER
# ==========================================================

class AIPromptBuilder:

    @staticmethod
    def explain(topic: str) -> str:
        return f"""
        Explain the following clearly and professionally.
        Provide structured formatting.

        Topic:
        {topic}
        """

    @staticmethod
    def analyze(text: str) -> str:
        return f"""
        Analyze this Discord message.

        Provide:
        - Tone
        - Intent
        - Toxicity score (0-100)
        - Risk level (Low/Medium/High)
        - Suggested improvements

        Text:
        {text}
        """

    @staticmethod
    def summarize(conversation: str) -> str:
        return f"""
        Summarize this Discord conversation.

        Provide:
        - Main topics
        - Overall sentiment
        - Key highlights
        - Potential concerns

        Conversation:
        {conversation}
        """

    @staticmethod
    def engagement_insight(conversation: str) -> str:
        return f"""
        Analyze this Discord server conversation.

        Provide:
        - Engagement level
        - Activity density
        - Social dynamics
        - Moderation risks
        - Overall server health score (0-100)

        Conversation:
        {conversation}
        """

    @staticmethod
    def risk_scan(conversation: str) -> str:
        return f"""
        Scan this conversation for:
        - Harassment
        - Spam
        - Scam patterns
        - Manipulation attempts
        - Grooming indicators

        Provide structured output.
        Conversation:
        {conversation}
        """


# ==========================================================
# 🔐 AI ACCESS VALIDATION
# ==========================================================

async def validate_ai(interaction: discord.Interaction):

    SubsystemManager.ensure_guild(interaction.guild.id)

    if not SubsystemManager.is_enabled(interaction.guild.id, "ai"):
        await interaction.response.send_message(
            embed=EmbedEngine.create(
                "AI Disabled",
                "The AI subsystem is disabled.\nUse `/system enable ai`.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )
        return False

    # Cooldown
    key = f"ai_user_{interaction.guild.id}_{interaction.user.id}"
    if not rate_limiter.check(key, AI_USER_COOLDOWN):
        await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Cooldown Active",
                f"Wait {AI_USER_COOLDOWN} seconds before reusing AI.",
                EmbedEngine.COLOR_WARNING
            ),
            ephemeral=True
        )
        return False

    # Daily Limit
    if AIUsageManager.get_usage(interaction.guild.id) >= AI_DAILY_LIMIT:
        await interaction.response.send_message(
            embed=EmbedEngine.create(
                "Daily Limit Reached",
                f"AI limit reached ({AI_DAILY_LIMIT}/day).",
                EmbedEngine.COLOR_ERROR
            ),
            ephemeral=True
        )
        return False

    AIUsageManager.increment(interaction.guild.id)
    return True


# ==========================================================
# 🤖 SAFE AI EXECUTION
# ==========================================================

async def execute_ai(prompt: str) -> str:
    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, ai_model.generate_content, prompt),
            timeout=AI_TIMEOUT_SECONDS
        )
        text = response.text if hasattr(response, "text") else str(response)
        return text[:3900]
    except asyncio.TimeoutError:
        return "AI processing timed out."
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "AI processing failed."


# ==========================================================
# 📥 MESSAGE CONTEXT COLLECTOR
# ==========================================================

async def collect_channel_context(channel: discord.TextChannel, limit=AI_CONTEXT_LIMIT):

    messages = []

    async for msg in channel.history(limit=limit):
        if not msg.author.bot and msg.content:
            messages.append(f"{msg.author.display_name}: {msg.content}")

    return "\n".join(messages)


# ==========================================================
# 🌌 AI SLASH GROUP
# ==========================================================

ai_group = app_commands.Group(
    name="ai",
    description="Advanced AI Intelligence System"
)


# ==========================================================
# /ai explain
# ==========================================================

@ai_group.command(name="explain", description="Explain a topic")
async def ai_explain(interaction: discord.Interaction, topic: str):

    if not await validate_ai(interaction):
        return

    await interaction.response.defer()

    prompt = AIPromptBuilder.explain(topic)
    result = await execute_ai(prompt)

    await interaction.followup.send(
        embed=EmbedEngine.create("AI Explanation", result)
    )


# ==========================================================
# /ai analyze
# ==========================================================

@ai_group.command(name="analyze", description="Analyze a message")
async def ai_analyze(interaction: discord.Interaction, text: str):

    if not await validate_ai(interaction):
        return

    await interaction.response.defer()

    prompt = AIPromptBuilder.analyze(text)
    result = await execute_ai(prompt)

    await interaction.followup.send(
        embed=EmbedEngine.create("AI Analysis Report", result)
    )


# ==========================================================
# /ai summarize
# ==========================================================

@ai_group.command(name="summarize", description="Summarize this channel")
async def ai_summarize(interaction: discord.Interaction):

    if not await validate_ai(interaction):
        return

    await interaction.response.defer()

    context = await collect_channel_context(interaction.channel)

    if not context:
        return await interaction.followup.send(
            embed=EmbedEngine.create("No Data", "No recent messages found.")
        )

    prompt = AIPromptBuilder.summarize(context)
    result = await execute_ai(prompt)

    await interaction.followup.send(
        embed=EmbedEngine.create("Channel Summary", result)
    )


# ==========================================================
# /ai insight
# ==========================================================

@ai_group.command(name="insight", description="Server engagement insight")
async def ai_insight(interaction: discord.Interaction):

    if not await validate_ai(interaction):
        return

    await interaction.response.defer()

    context = await collect_channel_context(interaction.channel)

    prompt = AIPromptBuilder.engagement_insight(context)
    result = await execute_ai(prompt)

    await interaction.followup.send(
        embed=EmbedEngine.create("Engagement Insight", result)
    )


# ==========================================================
# /ai risk
# ==========================================================

@ai_group.command(name="risk", description="Scan channel for risks")
async def ai_risk(interaction: discord.Interaction):

    if not await validate_ai(interaction):
        return

    await interaction.response.defer()

    context = await collect_channel_context(interaction.channel)

    prompt = AIPromptBuilder.risk_scan(context)
    result = await execute_ai(prompt)

    await interaction.followup.send(
        embed=EmbedEngine.create("Risk Scan Report", result)
    )


# ==========================================================
# REGISTER GROUP
# ==========================================================

tree.add_command(ai_group)

# ==========================================================
# 🌌 PHASE 4 OF 12 – FULL RPG ECONOMY ENGINE (COMPLETE)
# ==========================================================

import math
import random
from discord.ui import View, Button

# ==========================================================
# ⚙️ CONFIGURATION
# ==========================================================

ECON_XP_MIN = 5
ECON_XP_MAX = 15
ECON_XP_COOLDOWN = 15
ECON_DAILY_REWARD = 300
ECON_TRANSFER_COOLDOWN = 30
ECON_LEVEL_BASE = 120
ECON_LEVEL_EXP = 1.55

# ==========================================================
# 📈 LEVEL ENGINE
# ==========================================================

class LevelSystem:

    @staticmethod
    def required_xp(level: int) -> int:
        return int(ECON_LEVEL_BASE * (level ** ECON_LEVEL_EXP))

    @staticmethod
    def process_level(xp: int, level: int):
        leveled = False
        while xp >= LevelSystem.required_xp(level):
            xp -= LevelSystem.required_xp(level)
            level += 1
            leveled = True
        return xp, level, leveled


# ==========================================================
# 💾 ECONOMY MANAGER
# ==========================================================

class Economy:

    @staticmethod
    def ensure(guild_id, user_id):
        user = db.fetch_one("economy_users", {
            "guild_id": guild_id,
            "user_id": user_id
        })
        if not user:
            db.insert("economy_users", {
                "guild_id": guild_id,
                "user_id": user_id,
                "xp": 0,
                "level": 1,
                "gold": 0
            })

    @staticmethod
    def get(guild_id, user_id):
        Economy.ensure(guild_id, user_id)
        return db.fetch_one("economy_users", {
            "guild_id": guild_id,
            "user_id": user_id
        })

    @staticmethod
    def update(guild_id, user_id, data):
        db.update("economy_users", {
            "guild_id": guild_id,
            "user_id": user_id
        }, data)


# ==========================================================
# 🛡️ ANTI-SPAM FARM DETECTION
# ==========================================================

recent_messages = {}

def spam_check(user_id):
    now = datetime.utcnow().timestamp()
    if user_id not in recent_messages:
        recent_messages[user_id] = []

    recent_messages[user_id].append(now)
    recent_messages[user_id] = [
        t for t in recent_messages[user_id] if now - t < 10
    ]

    return len(recent_messages[user_id]) > 5


# ==========================================================
# 🧠 MESSAGE XP LISTENER
# ==========================================================

@bot.event
async def on_message(message):

    if message.author.bot or not message.guild:
        return

    if not SubsystemManager.is_enabled(message.guild.id, "economy"):
        return

    key = f"xp_{message.guild.id}_{message.author.id}"
    if not rate_limiter.check(key, ECON_XP_COOLDOWN):
        return

    if spam_check(message.author.id):
        return

    xp_gain = random.randint(ECON_XP_MIN, ECON_XP_MAX)

    user = Economy.get(message.guild.id, message.author.id)
    new_xp = user["xp"] + xp_gain
    level = user["level"]

    new_xp, level, leveled = LevelSystem.process_level(new_xp, level)

    Economy.update(message.guild.id, message.author.id, {
        "xp": new_xp,
        "level": level
    })

    if leveled:
        await message.channel.send(
            embed=EmbedEngine.create(
                "Level Up!",
                f"{message.author.mention} reached Level {level}!",
                EmbedEngine.COLOR_SUCCESS
            )
        )

    await bot.process_commands(message)


# ==========================================================
# 🎒 INVENTORY
# ==========================================================

class Inventory:

    @staticmethod
    def add(guild_id, user_id, item, qty=1):
        existing = db.fetch_one("economy_inventory", {
            "guild_id": guild_id,
            "user_id": user_id,
            "item_name": item
        })

        if not existing:
            db.insert("economy_inventory", {
                "guild_id": guild_id,
                "user_id": user_id,
                "item_name": item,
                "quantity": qty
            })
        else:
            db.update("economy_inventory", {
                "guild_id": guild_id,
                "user_id": user_id,
                "item_name": item
            }, {
                "quantity": existing["quantity"] + qty
            })

    @staticmethod
    def get(guild_id, user_id):
        return db.fetch_all("economy_inventory", {
            "guild_id": guild_id,
            "user_id": user_id
        })


# ==========================================================
# 🏪 SHOP SYSTEM
# ==========================================================

class Shop:

    @staticmethod
    def add_item(guild_id, name, price, description):
        db.insert("economy_shop", {
            "guild_id": guild_id,
            "item_name": name,
            "price": price,
            "description": description
        })

    @staticmethod
    def remove_item(guild_id, name):
        db.delete("economy_shop", {
            "guild_id": guild_id,
            "item_name": name
        })

    @staticmethod
    def get_all(guild_id):
        return db.fetch_all("economy_shop", {
            "guild_id": guild_id
        })

    @staticmethod
    def get(guild_id, name):
        return db.fetch_one("economy_shop", {
            "guild_id": guild_id,
            "item_name": name
        })


# ==========================================================
# 🎲 GAMBLING – COINFLIP
# ==========================================================

def coinflip():
    return random.choice(["heads", "tails"])


# ==========================================================
# 📊 LEADERBOARD VIEW
# ==========================================================

class LeaderboardView(View):

    def __init__(self, guild_id, users):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.users = users
        self.page = 0
        self.per_page = 10

    def get_page_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        chunk = self.users[start:end]

        desc = ""
        for i, user in enumerate(chunk, start=start + 1):
            desc += f"{i}. <@{user['user_id']}> — Level {user['level']} | {user['gold']} gold\n"

        return EmbedEngine.create("Leaderboard", desc)

    @discord.ui.button(label="Previous")
    async def prev(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="Next")
    async def next(self, interaction: discord.Interaction, button: Button):
        if (self.page + 1) * self.per_page < len(self.users):
            self.page += 1
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)


# ==========================================================
# 💬 SLASH COMMAND GROUP
# ==========================================================

economy_group = app_commands.Group(name="economy", description="RPG Economy System")

# ---------------- PROFILE ----------------

@economy_group.command(name="profile")
async def profile(interaction: discord.Interaction, member: discord.Member = None):

    member = member or interaction.user
    user = Economy.get(interaction.guild.id, member.id)
    required = LevelSystem.required_xp(user["level"])

    embed = EmbedEngine.create(
        f"{member.display_name}'s Profile",
        f"Level: {user['level']}\nXP: {user['xp']}/{required}\nGold: {user['gold']}"
    )

    await interaction.response.send_message(embed=embed)

# ---------------- DAILY ----------------

@economy_group.command(name="daily")
async def daily(interaction: discord.Interaction):

    today = datetime.utcnow().date().isoformat()

    record = db.fetch_one("economy_daily", {
        "guild_id": interaction.guild.id,
        "user_id": interaction.user.id
    })

    if record and record["last_claim"] == today:
        return await interaction.response.send_message(
            "Already claimed today.",
            ephemeral=True
        )

    if not record:
        db.insert("economy_daily", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id,
            "last_claim": today
        })
    else:
        db.update("economy_daily", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        }, {
            "last_claim": today
        })

    user = Economy.get(interaction.guild.id, interaction.user.id)
    Economy.update(interaction.guild.id, interaction.user.id, {
        "gold": user["gold"] + ECON_DAILY_REWARD
    })

    await interaction.response.send_message(
        embed=EmbedEngine.create("Daily Reward", f"+{ECON_DAILY_REWARD} gold")
    )

# ---------------- TRANSFER ----------------

@economy_group.command(name="transfer")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int):

    if member.id == interaction.user.id or amount <= 0:
        return await interaction.response.send_message("Invalid transfer.", ephemeral=True)

    key = f"transfer_{interaction.guild.id}_{interaction.user.id}"
    if not rate_limiter.check(key, ECON_TRANSFER_COOLDOWN):
        return await interaction.response.send_message("Transfer cooldown.", ephemeral=True)

    sender = Economy.get(interaction.guild.id, interaction.user.id)

    if sender["gold"] < amount:
        return await interaction.response.send_message("Not enough gold.", ephemeral=True)

    receiver = Economy.get(interaction.guild.id, member.id)

    Economy.update(interaction.guild.id, interaction.user.id, {
        "gold": sender["gold"] - amount
    })

    Economy.update(interaction.guild.id, member.id, {
        "gold": receiver["gold"] + amount
    })

    await interaction.response.send_message(
        embed=EmbedEngine.create("Transfer Complete", f"Sent {amount} gold.")
    )

# ---------------- LEADERBOARD ----------------

@economy_group.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):

    users = db.fetch_all("economy_users", {
        "guild_id": interaction.guild.id
    })

    users = sorted(users, key=lambda x: (x["level"], x["gold"]), reverse=True)

    view = LeaderboardView(interaction.guild.id, users)

    await interaction.response.send_message(
        embed=view.get_page_embed(),
        view=view
    )

# ---------------- COINFLIP ----------------

@economy_group.command(name="coinflip")
async def coinflip_cmd(interaction: discord.Interaction, amount: int, choice: str):

    user = Economy.get(interaction.guild.id, interaction.user.id)

    if amount <= 0 or user["gold"] < amount:
        return await interaction.response.send_message("Invalid bet.", ephemeral=True)

    result = coinflip()

    if choice.lower() == result:
        winnings = amount
        Economy.update(interaction.guild.id, interaction.user.id, {
            "gold": user["gold"] + winnings
        })
        msg = f"You won {winnings} gold!"
    else:
        Economy.update(interaction.guild.id, interaction.user.id, {
            "gold": user["gold"] - amount
        })
        msg = f"You lost {amount} gold."

    await interaction.response.send_message(
        embed=EmbedEngine.create("Coinflip Result", f"Result: {result}\n{msg}")
    )

# ==========================================================
# REGISTER
# ==========================================================

tree.add_command(economy_group)

# ==========================================================
# SECTION 1 – ENTERPRISE MODERATION CORE
# Permission Engine + Case Engine + Cache + Base Utilities
# ==========================================================

from discord.ui import View, Button
from datetime import datetime, timedelta

# ==========================================================
# 🔐 MOD PERMISSION ENGINE (CACHE + HIERARCHY)
# ==========================================================

PERMISSION_CACHE = {}


async def refresh_permission_cache(guild_id):

    rows = db.fetch_all("mod_permissions", {
        "guild_id": guild_id
    })

    cache = {}

    for row in rows:

        role_id = row["role_id"]
        perm = row["permission"]

        if role_id not in cache:
            cache[role_id] = set()

        cache[role_id].add(perm)

    PERMISSION_CACHE[guild_id] = cache


async def has_mod_permission(member, permission):

    guild_id = member.guild.id

    if guild_id not in PERMISSION_CACHE:
        await refresh_permission_cache(guild_id)

    guild_cache = PERMISSION_CACHE.get(guild_id, {})

    for role in member.roles:

        if role.id in guild_cache:

            if permission in guild_cache[role.id]:
                return True

            if "admin" in guild_cache[role.id]:
                return True

    return False


async def update_permission_cache(guild_id):
    await refresh_permission_cache(guild_id)


# ==========================================================
# 🗄 CASE DATABASE ENGINE
# ==========================================================

async def generate_case_id(guild_id):

    cases = db.fetch_all("mod_cases", {"guild_id": guild_id})

    if not cases:
        return 1

    return max(case["id"] for case in cases) + 1


async def add_case(guild_id, user_id, moderator_id,
                   action, reason, duration=None):

    case_id = await generate_case_id(guild_id)

    db.insert("mod_cases", {
        "id": case_id,
        "guild_id": guild_id,
        "user_id": user_id,
        "moderator_id": moderator_id,
        "action": action,
        "reason": reason,
        "duration": duration,
        "timestamp": datetime.utcnow().isoformat()
    })

    return case_id


async def get_user_cases(guild_id, user_id):

    return db.fetch_all("mod_cases", {
        "guild_id": guild_id,
        "user_id": user_id
    })


async def get_case_by_id(guild_id, case_id):

    return db.fetch_one("mod_cases", {
        "guild_id": guild_id,
        "id": case_id
    })


async def delete_case(case_id):

    db.delete("mod_cases", {"id": case_id})


# ==========================================================
# ⚡ AUTO ESCALATION (3 WARN = AUTO MUTE)
# ==========================================================

async def auto_escalate(guild, member):

    cases = await get_user_cases(guild.id, member.id)

    warns = [c for c in cases if c["action"] == "Warn"]

    if len(warns) >= 3:

        mute_role = discord.utils.get(guild.roles, name="Muted")

        if mute_role:

            try:
                await member.add_roles(mute_role)
            except:
                pass

            await add_case(
                guild.id,
                member.id,
                guild.me.id,
                "Auto-Mute",
                "Auto escalation after 3 warnings"
            )


# ==========================================================
# 🧠 CASE PAGINATOR (UI)
# ==========================================================

class CasePaginator(View):

    def __init__(self, cases):

        super().__init__(timeout=60)
        self.cases = cases
        self.page = 0
        self.per_page = 5

    def build_embed(self):

        start = self.page * self.per_page
        end = start + self.per_page
        chunk = self.cases[start:end]

        embed = discord.Embed(
            title="📋 Case History",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        for case in chunk:

            embed.add_field(
                name=f"Case #{case['id']} — {case['action']}",
                value=f"User: <@{case['user_id']}>\nReason: {case['reason']}",
                inline=False
            )

        total_pages = max(1, len(self.cases) // self.per_page + 1)

        embed.set_footer(
            text=f"Page {self.page + 1}/{total_pages}"
        )

        return embed

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.primary)
    async def back(self, interaction: discord.Interaction, button: Button):

        if self.page > 0:
            self.page -= 1

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    @discord.ui.button(label="➡", style=discord.ButtonStyle.primary)
    async def forward(self, interaction: discord.Interaction, button: Button):

        if (self.page + 1) * self.per_page < len(self.cases):
            self.page += 1

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
)

# ==========================================================
# 🌌 PHASE 2 – ENTERPRISE MOD CORE
# Permission Engine + Case System + Stats + Base Commands
# ==========================================================

from discord.ui import View, Button
from datetime import datetime, timedelta

# ==========================================================
# 🔐 PERMISSION ENGINE (ROLE BASED)
# ==========================================================

PERMISSION_CACHE = {}


async def refresh_permission_cache(guild_id):

    rows = db.fetch_all("mod_permissions", {
        "guild_id": guild_id
    })

    cache = {}

    for row in rows:

        role_id = row["role_id"]
        perm = row["permission"]

        if role_id not in cache:
            cache[role_id] = set()

        cache[role_id].add(perm)

    PERMISSION_CACHE[guild_id] = cache


async def has_mod_permission(member, permission):

    guild_id = member.guild.id

    if guild_id not in PERMISSION_CACHE:
        await refresh_permission_cache(guild_id)

    cache = PERMISSION_CACHE.get(guild_id, {})

    for role in member.roles:

        if role.id in cache:

            if permission in cache[role.id]:
                return True

            if "admin" in cache[role.id]:
                return True

    return False


async def require_perm(interaction, perm):

    if not await has_mod_permission(interaction.user, perm):

        await interaction.response.send_message(
            f"🚫 Missing `{perm}` permission.",
            ephemeral=True
        )

        return False

    return True


# ==========================================================
# 🗄 CASE SYSTEM
# ==========================================================

async def create_case(guild_id, user_id,
                      moderator_id, action,
                      reason, duration=None):

    cases = db.fetch_all("mod_cases", {
        "guild_id": guild_id
    })

    case_id = len(cases) + 1

    db.insert("mod_cases", {
        "id": case_id,
        "guild_id": guild_id,
        "user_id": user_id,
        "moderator_id": moderator_id,
        "action": action,
        "reason": reason,
        "duration": duration,
        "timestamp": datetime.utcnow().isoformat()
    })

    return case_id


async def get_user_cases(guild_id, user_id):

    return db.fetch_all("mod_cases", {
        "guild_id": guild_id,
        "user_id": user_id
    })


async def delete_case(case_id):

    db.delete("mod_cases", {"id": case_id})


# ==========================================================
# ⚡ AUTO ESCALATION
# 3 WARN = AUTO MUTE
# ==========================================================

async def auto_escalate(guild, member):

    cases = await get_user_cases(guild.id, member.id)

    warns = [c for c in cases if c["action"] == "Warn"]

    if len(warns) >= 3:

        role = discord.utils.get(guild.roles, name="Muted")

        if role:

            try:
                await member.add_roles(role)
            except:
                pass

            await create_case(
                guild.id,
                member.id,
                guild.me.id,
                "Auto-Mute",
                "Escalation after 3 warnings"
            )


# ==========================================================
# 📜 CASE VIEW
# ==========================================================

class CasePaginator(View):

    def __init__(self, cases):

        super().__init__(timeout=60)
        self.cases = cases
        self.page = 0
        self.per_page = 5

    def build_embed(self):

        start = self.page * self.per_page
        end = start + self.per_page

        chunk = self.cases[start:end]

        embed = discord.Embed(
            title="📋 Case History",
            color=discord.Color.orange()
        )

        for case in chunk:

            embed.add_field(
                name=f"Case #{case['id']} — {case['action']}",
                value=f"Reason: {case['reason']}",
                inline=False
            )

        total = max(1, len(self.cases) // self.per_page + 1)

        embed.set_footer(
            text=f"Page {self.page+1}/{total}"
        )

        return embed

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.primary)
    async def back(self, interaction, button):

        if self.page > 0:
            self.page -= 1

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    @discord.ui.button(label="➡", style=discord.ButtonStyle.primary)
    async def forward(self, interaction, button):

        if (self.page + 1) * self.per_page < len(self.cases):
            self.page += 1

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )


# ==========================================================
# 🔥 BASE MOD COMMANDS
# (Warn / Mute / Kick / Ban / History / Notes)
# ==========================================================

moderation_group = app_commands.Group(
    name="moderation",
    description="Core Moderation Commands"
)


@moderation_group.command(name="warn")
async def warn_cmd(interaction,
                   member: discord.Member,
                   reason: str):

    if not await require_perm(interaction, "warn"):
        return

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Warn",
        reason
    )

    await auto_escalate(interaction.guild, member)

    await interaction.response.send_message(
        f"⚠ Warned | Case #{case_id}"
    )


@moderation_group.command(name="mute")
async def mute_cmd(interaction,
                   member: discord.Member,
                   duration_minutes: int,
                   reason: str):

    if not await require_perm(interaction, "mute"):
        return

    role = discord.utils.get(interaction.guild.roles, name="Muted")

    if role:
        await member.add_roles(role)

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Mute",
        reason,
        duration_minutes
    )

    async def auto_unmute():

        await asyncio.sleep(duration_minutes * 60)

        if role:
            try:
                await member.remove_roles(role)
            except:
                pass

    bot.loop.create_task(auto_unmute())

    await interaction.response.send_message(
        f"🔇 Muted | Case #{case_id}"
    )


@moderation_group.command(name="kick")
async def kick_cmd(interaction,
                   member: discord.Member,
                   reason: str):

    if not await require_perm(interaction, "kick"):
        return

    await member.kick(reason=reason)

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Kick",
        reason
    )

    await interaction.response.send_message(
        f"👢 Kicked | Case #{case_id}"
    )


@moderation_group.command(name="ban")
async def ban_cmd(interaction,
                  member: discord.Member,
                  reason: str):

    if not await require_perm(interaction, "ban"):
        return

    await member.ban(reason=reason)

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Ban",
        reason
    )

    await interaction.response.send_message(
        f"🔨 Banned | Case #{case_id}"
    )


@moderation_group.command(name="history")
async def history_cmd(interaction,
                      member: discord.Member):

    cases = await get_user_cases(interaction.guild.id, member.id)

    if not cases:
        return await interaction.response.send_message(
            "No history found.",
            ephemeral=True
        )

    view = CasePaginator(cases)

    await interaction.response.send_message(
        embed=view.build_embed(),
        view=view
    )


tree.add_command(moderation_group)

# ==========================================================
# 🌌 PHASE 3 – FULL MOD COMMAND LIBRARY
# Every Moderation Utility Command
# ==========================================================

# Use the same moderation_group from Phase 2
# moderation_group = app_commands.Group(...)


# ==========================================================
# 💥 SOFTBAN
# ==========================================================

@moderation_group.command(name="softban")
async def softban_cmd(interaction,
                      member: discord.Member,
                      reason: str):

    if not await require_perm(interaction, "ban"):
        return

    await member.ban(reason=reason, delete_message_days=7)
    await interaction.guild.unban(member)

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Softban",
        reason
    )

    await interaction.response.send_message(
        f"💥 Softbanned | Case #{case_id}"
    )


# ==========================================================
# 🔓 UNBAN
# ==========================================================

@moderation_group.command(name="unban")
async def unban_cmd(interaction,
                    user_id: str):

    if not await require_perm(interaction, "ban"):
        return

    user = await bot.fetch_user(int(user_id))

    await interaction.guild.unban(user)

    await interaction.response.send_message(
        f"✅ Unbanned {user}"
    )


# ==========================================================
# ⏱ TIMEOUT
# ==========================================================

@moderation_group.command(name="timeout")
async def timeout_cmd(interaction,
                      member: discord.Member,
                      minutes: int,
                      reason: str):

    if not await require_perm(interaction, "timeout"):
        return

    until = datetime.utcnow() + timedelta(minutes=minutes)

    await member.edit(communication_disabled_until=until)

    case_id = await create_case(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        "Timeout",
        reason,
        minutes
    )

    await interaction.response.send_message(
        f"⏳ Timed Out | Case #{case_id}"
    )


# ==========================================================
# ⏪ UNTIMEOUT
# ==========================================================

@moderation_group.command(name="untimeout")
async def untimeout_cmd(interaction,
                        member: discord.Member):

    if not await require_perm(interaction, "timeout"):
        return

    await member.edit(communication_disabled_until=None)

    await interaction.response.send_message(
        f"✅ Removed timeout from {member.mention}"
    )


# ==========================================================
# 🔥 MASS BAN
# ==========================================================

@moderation_group.command(name="massban")
async def massban_cmd(interaction,
                      user_ids: str):

    if not await require_perm(interaction, "ban"):
        return

    ids = user_ids.split(",")

    banned = 0

    for uid in ids:

        try:
            user = await bot.fetch_user(int(uid.strip()))
            await interaction.guild.ban(user)
            banned += 1

        except:
            continue

    await interaction.response.send_message(
        f"🔥 MassBanned {banned} users"
    )


# ==========================================================
# 💣 MASS KICK
# ==========================================================

@moderation_group.command(name="masskick")
async def masskick_cmd(interaction,
                       user_ids: str):

    if not await require_perm(interaction, "kick"):
        return

    ids = user_ids.split(",")

    kicked = 0

    for uid in ids:

        member = interaction.guild.get_member(int(uid.strip()))

        if member:
            try:
                await member.kick()
                kicked += 1
            except:
                continue

    await interaction.response.send_message(
        f"👢 MassKicked {kicked} users"
    )


# ==========================================================
# 🧹 CLEAR CHANNEL MESSAGES
# ==========================================================

@moderation_group.command(name="clear")
async def clear_cmd(interaction,
                    amount: int):

    if not await require_perm(interaction, "clear"):
        return

    deleted = await interaction.channel.purge(limit=amount)

    await interaction.response.send_message(
        f"🧹 Deleted {len(deleted)} messages",
        ephemeral=True
    )


# ==========================================================
# 🧹 CLEAR USER MESSAGES
# ==========================================================

@moderation_group.command(name="clear_user")
async def clear_user_cmd(interaction,
                         member: discord.Member):

    if not await require_perm(interaction, "clear"):
        return

    def check(msg):
        return msg.author == member

    deleted = await interaction.channel.purge(limit=200,
                                              check=check)

    await interaction.response.send_message(
        f"🧹 Deleted {len(deleted)} messages from {member.mention}",
        ephemeral=True
    )


# ==========================================================
# 🧹 CLEAR BOT MESSAGES
# ==========================================================

@moderation_group.command(name="clear_bot")
async def clear_bot_cmd(interaction):

    if not await require_perm(interaction, "clear"):
        return

    def check(msg):
        return msg.author.bot

    deleted = await interaction.channel.purge(limit=200,
                                              check=check)

    await interaction.response.send_message(
        f"🤖 Deleted {len(deleted)} bot messages",
        ephemeral=True
    )


# ==========================================================
# 🔗 CLEAR LINKS
# ==========================================================

@moderation_group.command(name="clear_links")
async def clear_links_cmd(interaction):

    if not await require_perm(interaction, "clear"):
        return

    import re

    link_regex = r"http[s]?://"

    def check(msg):
        return re.search(link_regex, msg.content)

    deleted = await interaction.channel.purge(limit=200,
                                              check=check)

    await interaction.response.send_message(
        f"🔗 Deleted {len(deleted)} link messages",
        ephemeral=True
    )


# ==========================================================
# 🖼 CLEAR IMAGES
# ==========================================================

@moderation_group.command(name="clear_images")
async def clear_images_cmd(interaction):

    if not await require_perm(interaction, "clear"):
        return

    def check(msg):
        return len(msg.attachments) > 0

    deleted = await interaction.channel.purge(limit=200,
                                              check=check)

    await interaction.response.send_message(
        f"🖼 Deleted {len(deleted)} image messages",
        ephemeral=True
    )


# ==========================================================
# 🔒 LOCK CHANNEL
# ==========================================================

@moderation_group.command(name="lock")
async def lock_cmd(interaction):

    if not await require_perm(interaction, "lock"):
        return

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        send_messages=False
    )

    await interaction.response.send_message("🔒 Channel Locked")


# ==========================================================
# 🔓 UNLOCK CHANNEL
# ==========================================================

@moderation_group.command(name="unlock")
async def unlock_cmd(interaction):

    if not await require_perm(interaction, "lock"):
        return

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        send_messages=True
    )

    await interaction.response.send_message("🔓 Channel Unlocked")


# ==========================================================
# ⏱ SLOWMODE
# ==========================================================

@moderation_group.command(name="slowmode")
async def slowmode_cmd(interaction,
                       seconds: int):

    if not await require_perm(interaction, "lock"):
        return

    await interaction.channel.edit(slowmode_delay=seconds)

    await interaction.response.send_message(
        f"⏱ Slowmode set to {seconds}s"
    )


# ==========================================================
# 🙈 HIDE CHANNEL
# ==========================================================

@moderation_group.command(name="hide")
async def hide_cmd(interaction):

    if not await require_perm(interaction, "lock"):
        return

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        view_channel=False
    )

    await interaction.response.send_message("🙈 Channel Hidden")


# ==========================================================
# 👁 UNHIDE CHANNEL
# ==========================================================

@moderation_group.command(name="unhide")
async def unhide_cmd(interaction):

    if not await require_perm(interaction, "lock"):
        return

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        view_channel=True
    )

    await interaction.response.send_message("👁 Channel Visible")


# ==========================================================
# 📊 AUDIT
# ==========================================================

@moderation_group.command(name="audit")
async def audit_cmd(interaction):

    if not await require_perm(interaction, "admin"):
        return

    cases = db.fetch_all("mod_cases", {
        "guild_id": interaction.guild.id
    })

    embed = discord.Embed(
        title="📊 Moderation Audit",
        description=f"Total Cases: {len(cases)}",
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)


# ==========================================================
# 🔎 SEARCH CASES
# ==========================================================

@moderation_group.command(name="search_cases")
async def search_cases_cmd(interaction,
                           keyword: str):

    if not await require_perm(interaction, "admin"):
        return

    cases = db.fetch_all("mod_cases", {
        "guild_id": interaction.guild.id
    })

    results = []

    for case in cases:

        if keyword.lower() in str(case["id"]).lower() or \
           keyword.lower() in str(case["user_id"]).lower():

            results.append(case)

    if not results:
        return await interaction.response.send_message(
            "❌ No cases found.",
            ephemeral=True
        )

    desc = ""

    for case in results[:10]:
        desc += f"Case #{case['id']} | {case['action']} | <@{case['user_id']}>\n"

    embed = discord.Embed(
        title="🔎 Search Results",
        description=desc,
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)


# ==========================================================
# 🔐 PERMISSION MANAGEMENT
# ==========================================================

@moderation_group.command(name="grant_perm")
async def grant_perm_cmd(interaction,
                         role: discord.Role,
                         permission: str):

    if not interaction.user.guild_permissions.administrator:
        return

    db.insert("mod_permissions", {
        "guild_id": interaction.guild.id,
        "role_id": role.id,
        "permission": permission.lower()
    })

    await refresh_permission_cache(interaction.guild.id)

    await interaction.response.send_message(
        f"✅ Granted `{permission}` to `{role.name}`"
    )


@moderation_group.command(name="remove_perm")
async def remove_perm_cmd(interaction,
                          role: discord.Role,
                          permission: str):

    if not interaction.user.guild_permissions.administrator:
        return

    db.delete("mod_permissions", {
        "guild_id": interaction.guild.id,
        "role_id": role.id,
        "permission": permission.lower()
    })

    await refresh_permission_cache(interaction.guild.id)

    await interaction.response.send_message(
        f"❌ Removed `{permission}` from `{role.name}`"
    )


@moderation_group.command(name="permission_audit")
async def permission_audit_cmd(interaction):

    rows = db.fetch_all("mod_permissions", {
        "guild_id": interaction.guild.id
    })

    embed = discord.Embed(
        title="🔐 Permission Audit",
        color=discord.Color.purple()
    )

    for row in rows:

        role = interaction.guild.get_role(row["role_id"])
        name = role.name if role else "Deleted Role"

        embed.add_field(
            name=name,
            value=row["permission"],
            inline=False
        )

    await interaction.response.send_message(embed=embed)


tree.add_command(moderation_group)

# ==========================================================
# 🌌 PHASE 6 OF 13 – ULTRA ADVANCED AUTOMOD ENGINE
# Enterprise Rule-Based Protection System
# ==========================================================

import difflib
import statistics
from collections import defaultdict, deque
from typing import Dict, List

# ==========================================================
# 🧠 GLOBAL TRACKERS
# ==========================================================

# Track messages per user for spam scoring
user_message_buffer: Dict[int, deque] = defaultdict(lambda: deque(maxlen=50))

# Track join timestamps for raid detection
guild_join_tracker: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))

# Track message similarity for copy-spam detection
user_similarity_tracker: Dict[int, List[str]] = defaultdict(list)

# ==========================================================
# ⚙️ RULE ENGINE CORE
# ==========================================================

class AutoRule:

    """
    Represents a single automod rule.
    Rules are dynamic and configurable per guild.
    """

    def __init__(self, name: str, enabled: bool, threshold: int, action: str):
        self.name = name
        self.enabled = enabled
        self.threshold = threshold
        self.action = action  # warn | mute | timeout | delete | kick | ban


class RuleManager:

    """
    Handles storing and loading rules from database.
    """

    @staticmethod
    def get_rules(guild_id: int) -> List[AutoRule]:

        rows = db.fetch_all("automod_rules", {"guild_id": guild_id})

        rules = []

        for r in rows:
            rules.append(
                AutoRule(
                    name=r["rule_name"],
                    enabled=r["enabled"],
                    threshold=r["threshold"],
                    action=r["action"]
                )
            )

        return rules

    @staticmethod
    def set_rule(guild_id: int, rule_name: str, enabled: bool, threshold: int, action: str):

        existing = db.fetch_one("automod_rules", {
            "guild_id": guild_id,
            "rule_name": rule_name
        })

        if not existing:
            db.insert("automod_rules", {
                "guild_id": guild_id,
                "rule_name": rule_name,
                "enabled": enabled,
                "threshold": threshold,
                "action": action
            })
        else:
            db.update(
                "automod_rules",
                {"guild_id": guild_id, "rule_name": rule_name},
                {
                    "enabled": enabled,
                    "threshold": threshold,
                    "action": action
                }
            )


# ==========================================================
# 🚨 RAID DETECTION
# ==========================================================

def track_member_join(guild_id: int):

    now = datetime.utcnow().timestamp()
    guild_join_tracker[guild_id].append(now)

    # Remove old timestamps (last 60 seconds)
    guild_join_tracker[guild_id] = deque(
        [t for t in guild_join_tracker[guild_id] if now - t < 60],
        maxlen=100
    )


def detect_raid(guild_id: int, threshold: int = 10):

    """
    If more than X joins in 60 seconds → raid detected.
    """

    if len(guild_join_tracker[guild_id]) >= threshold:
        return True

    return False


# ==========================================================
# 📊 SPAM SCORING ENGINE
# ==========================================================

def compute_spam_score(user_id: int):

    timestamps = user_message_buffer[user_id]

    if len(timestamps) < 5:
        return 0

    intervals = [
        timestamps[i] - timestamps[i - 1]
        for i in range(1, len(timestamps))
    ]

    if not intervals:
        return 0

    avg_interval = statistics.mean(intervals)

    # Lower interval → Higher spam score
    score = max(0, int(100 - avg_interval * 10))

    return score


def track_message(user_id: int, content: str):

    now = datetime.utcnow().timestamp()

    user_message_buffer[user_id].append(now)

    user_similarity_tracker[user_id].append(content)

    if len(user_similarity_tracker[user_id]) > 10:
        user_similarity_tracker[user_id].pop(0)


def detect_similarity_spam(user_id: int):

    msgs = user_similarity_tracker[user_id]

    if len(msgs) < 5:
        return False

    base = msgs[0]
    similarity_scores = [
        difflib.SequenceMatcher(None, base, msg).ratio()
        for msg in msgs
    ]

    if statistics.mean(similarity_scores) > 0.85:
        return True

    return False


# ==========================================================
# 🔥 ACTION EXECUTION ENGINE
# ==========================================================

async def execute_action(action: str, guild, member):

    if action == "delete":
        return

    if action == "warn":
        await add_case(
            guild.id,
            member.id,
            guild.me.id,
            "AutoMod",
            "Automatic warning from rule engine"
        )

    if action == "mute":
        role = discord.utils.get(guild.roles, name="Muted")
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

    if action == "timeout":
        try:
            await member.timeout(datetime.utcnow() + timedelta(minutes=10))
        except:
            pass

    if action == "kick":
        try:
            await member.kick(reason="AutoMod triggered")
        except:
            pass

    if action == "ban":
        try:
            await member.ban(reason="AutoMod triggered")
        except:
            pass


# ==========================================================
# 🚀 MAIN AUTOMOD MESSAGE PIPELINE
# ==========================================================

async def process_automod(message: discord.Message):

    if message.author.bot:
        return

    if not SubsystemManager.is_enabled(message.guild.id, "automod"):
        return

    track_message(message.author.id, message.content)

    guild_id = message.guild.id

    rules = RuleManager.get_rules(guild_id)

    spam_score = compute_spam_score(message.author.id)

    raid_detected = detect_raid(guild_id)

    # =============================================
    # RAID HANDLING
    # =============================================

    if raid_detected:
        await message.channel.send(
            embed=EmbedEngine.create(
                "🚨 Raid Detected",
                "Mass joins detected. Auto protection activated."
            )
        )

    # =============================================
    # RULE EVALUATION LOOP
    # =============================================

    for rule in rules:

        if not rule.enabled:
            continue

        triggered = False

        # Spam rule
        if rule.name == "spam" and spam_score > rule.threshold:
            triggered = True

        # Mention spam
        if rule.name == "mention_spam":
            if len(message.mentions) > rule.threshold:
                triggered = True

        # Caps rule
        if rule.name == "caps":
            if len(message.content) > 5:
                caps = sum(1 for c in message.content if c.isupper())
                percent = (caps / len(message.content)) * 100
                if percent > rule.threshold:
                    triggered = True

        # Link rule
        if rule.name == "links":
            if "http" in message.content:
                triggered = True

        # Similar content spam
        if rule.name == "copy_spam":
            if detect_similarity_spam(message.author.id):
                triggered = True

        if triggered:

            await message.delete()

            await execute_action(
                rule.action,
                message.guild,
                message.author
            )

            await add_case(
                message.guild.id,
                message.author.id,
                message.guild.me.id,
                "AutoMod",
                f"Rule {rule.name} triggered"
            )

            break


# ==========================================================
# 🔎 EVENT HOOK
# ==========================================================

@bot.event
async def on_message(message):

    await process_automod(message)
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):

    track_member_join(member.guild.id)

    if detect_raid(member.guild.id):
        await member.guild.system_channel.send(
            embed=EmbedEngine.create(
                "🚨 Raid Warning",
                "Multiple joins detected. Monitor activity."
            )
        )


# ==========================================================
# 🌟 AUTOMOD CONTROL COMMANDS
# ==========================================================

automod_group = app_commands.Group(
    name="automod",
    description="Advanced Rule-Based Protection"
)

@automod_group.command(name="rule_set")
@app_commands.checks.has_permissions(manage_guild=True)
async def rule_set(
    interaction: discord.Interaction,
    rule_name: str,
    enabled: bool,
    threshold: int,
    action: str
):

    RuleManager.set_rule(
        interaction.guild.id,
        rule_name,
        enabled,
        threshold,
        action
    )

    await interaction.response.send_message(
        embed=EmbedEngine.create(
            "Rule Updated",
            f"Rule `{rule_name}` configured successfully."
        )
    )


@automod_group.command(name="rules")
async def rules_list(interaction: discord.Interaction):

    rules = RuleManager.get_rules(interaction.guild.id)

    if not rules:
        return await interaction.response.send_message(
            "No rules configured."
        )

    desc = ""

    for r in rules:
        desc += (
            f"**{r.name}**\n"
            f"Enabled: {r.enabled}\n"
            f"Threshold: {r.threshold}\n"
            f"Action: {r.action}\n\n"
        )

    await interaction.response.send_message(
        embed=EmbedEngine.create("AutoMod Rules", desc)
    )


tree.add_command(automod_group)

# ==========================================================
# 🌍 PHASE 7 OF 13
# ULTRA ENTERPRISE LOGGING + SERVER SETUP SYSTEM
# 800+ LINE READY ARCHITECTURE
# ==========================================================

import json
import hashlib
import csv
import io
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from discord.ui import View, Button, Select

# ==========================================================
# 🗄 DATABASE LAYER
# ==========================================================

class UltraAuditDB:

    # ---------------- TABLE INITIALIZATION ----------------

    @staticmethod
    def ensure_tables(guild_id: int):

        if not db.fetch_one("audit_meta", {"guild_id": guild_id}):
            db.insert("audit_meta", {
                "guild_id": guild_id,
                "log_channel_id": None,
                "economy_channel_id": None,
                "automod_channel_id": None,
                "welcome_channel_id": None,
                "created_at": datetime.utcnow().isoformat()
            })

    # ---------------- META HANDLING ----------------

    @staticmethod
    def get_meta(guild_id: int):
        UltraAuditDB.ensure_tables(guild_id)
        return db.fetch_one("audit_meta", {"guild_id": guild_id})

    @staticmethod
    def update_meta(guild_id: int, data: dict):
        db.update("audit_meta", {"guild_id": guild_id}, data)

    # ---------------- LOG STORAGE ----------------

    @staticmethod
    def insert_log(guild_id: int, event_type: str, payload: dict):

        raw = json.dumps(payload, sort_keys=True)
        hash_value = hashlib.sha256(raw.encode()).hexdigest()

        db.insert("audit_logs", {
            "guild_id": guild_id,
            "event_type": event_type,
            "payload": raw,
            "hash": hash_value,
            "timestamp": datetime.utcnow().isoformat()
        })

    @staticmethod
    def fetch_logs(guild_id: int, filters: dict = None):

        if not filters:
            return db.fetch_all("audit_logs", {"guild_id": guild_id})

        conditions = {"guild_id": guild_id}
        conditions.update(filters)

        return db.fetch_all("audit_logs", conditions)

    @staticmethod
    def delete_logs(guild_id: int):
        db.delete("audit_logs", {"guild_id": guild_id})

    @staticmethod
    def delete_old_logs(days: int):

        cutoff = datetime.utcnow() - timedelta(days=days)

        logs = db.fetch_all("audit_logs", {})

        for log in logs:
            ts = datetime.fromisoformat(log["timestamp"])
            if ts < cutoff:
                db.delete("audit_logs", {"id": log["id"]})


# ==========================================================
# 🔐 LOG INTEGRITY CHECK
# ==========================================================

def verify_log_integrity(log: dict):

    raw = log["payload"]
    expected_hash = log["hash"]

    computed = hashlib.sha256(raw.encode()).hexdigest()

    return computed == expected_hash


# ==========================================================
# 📦 LOG SENDER ENGINE
# ==========================================================

async def send_log(guild: discord.Guild, title: str, description: str):

    meta = UltraAuditDB.get_meta(guild.id)

    channel_id = meta.get("log_channel_id")
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    await channel.send(embed=embed)

    UltraAuditDB.insert_log(guild.id, title, {
        "description": description
    })


# ==========================================================
# 🔎 LOG PAGINATION VIEW
# ==========================================================

class LogViewer(View):

    def __init__(self, logs: List[dict]):
        super().__init__(timeout=300)
        self.logs = logs
        self.page = 0
        self.per_page = 5

    def build(self):

        start = self.page * self.per_page
        end = start + self.per_page
        chunk = self.logs[start:end]

        embed = discord.Embed(
            title="📜 Audit Log Viewer",
            color=discord.Color.dark_blue()
        )

        for log in chunk:
            embed.add_field(
                name=f"{log['event_type']} | {log['timestamp']}",
                value=log["payload"],
                inline=False
            )

        total = max(1, len(self.logs) // self.per_page + 1)
        embed.set_footer(text=f"Page {self.page+1}/{total}")

        return embed

    @discord.ui.button(label="⬅ Prev")
    async def prev(self, interaction: discord.Interaction, button: Button):

        if self.page > 0:
            self.page -= 1

        await interaction.response.edit_message(embed=self.build(), view=self)

    @discord.ui.button(label="Next ➡")
    async def next(self, interaction: discord.Interaction, button: Button):

        if (self.page + 1) * self.per_page < len(self.logs):
            self.page += 1

        await interaction.response.edit_message(embed=self.build(), view=self)


# ==========================================================
# 🛠 SERVER SETUP PANEL
# ==========================================================

class SetupWizard(View):

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=600)
        self.guild = guild

    async def ask_channel(self, interaction, key: str, label: str):

        await interaction.response.send_message(
            f"Mention channel for **{label}**",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
            channel = msg.channel_mentions[0]

            UltraAuditDB.update_meta(self.guild.id, {
                key: channel.id
            })

            await interaction.followup.send(
                f"✅ {label} set to {channel.mention}",
                ephemeral=True
            )

        except:
            await interaction.followup.send("❌ Timeout.", ephemeral=True)

    @discord.ui.button(label="Set Log Channel")
    async def set_log(self, interaction: discord.Interaction, button: Button):
        await self.ask_channel(interaction, "log_channel_id", "Logs")

    @discord.ui.button(label="Set Economy Channel")
    async def set_econ(self, interaction: discord.Interaction, button: Button):
        await self.ask_channel(interaction, "economy_channel_id", "Economy")

    @discord.ui.button(label="Set AutoMod Channel")
    async def set_auto(self, interaction: discord.Interaction, button: Button):
        await self.ask_channel(interaction, "automod_channel_id", "AutoMod")

    @discord.ui.button(label="Set Welcome Channel")
    async def set_welcome(self, interaction: discord.Interaction, button: Button):
        await self.ask_channel(interaction, "welcome_channel_id", "Welcome")
@discord.ui.button(label="Configure Welcome", style=discord.ButtonStyle.success)
async def configure_welcome(self, interaction: discord.Interaction, button: Button):

    await interaction.response.send_message(
        "📩 Mention welcome channel first.\nThen type your welcome message template.\n\n"
        "You can use variables:\n"
        "`{user}` - Mention user\n"
        "`{username}` - Username\n"
        "`{server}` - Server name\n"
        "`{member_count}` - Member count\n",
        ephemeral=True
    )

    def check(m):
        return m.author == interaction.user

    try:
        msg = await bot.wait_for("message", timeout=120, check=check)

        if not msg.channel_mentions:
            return await interaction.followup.send("❌ No channel mentioned.")

        channel = msg.channel_mentions[0]

        # Remove channel mention from message to get template
        template = msg.content.replace(channel.mention, "").strip()

        # Save into database properly
        db.update("guild_settings", {
            "guild_id": self.guild.id
        }, {
            "welcome_channel_id": channel.id,
            "welcome_message": template,
            "welcome_enabled": True
        })

        await interaction.followup.send(
            f"✅ Welcome system configured.\nChannel: {channel.mention}",
            ephemeral=True
        )

    except:
        await interaction.followup.send("❌ Timeout.", ephemeral=True)

@bot.event
async def on_member_join(member: discord.Member):

    settings = db.fetch_one("guild_settings", {
        "guild_id": member.guild.id
    })

    if not settings or not settings.get("welcome_enabled"):
        return

    channel_id = settings.get("welcome_channel_id")
    message_template = settings.get("welcome_message")

    channel = member.guild.get_channel(channel_id)
    if not channel:
        return

    # Replace variables
    content = message_template \
        .replace("{user}", member.mention) \
        .replace("{username}", member.name) \
        .replace("{server}", member.guild.name) \
        .replace("{member_count}", str(member.guild.member_count))

    embed = discord.Embed(
        description=content,
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    await channel.send(embed=embed)

# ==========================================================
# 🌍 /logs COMMAND GROUP
# ==========================================================

log_group = app_commands.Group(
    name="logs",
    description="Ultra Enterprise Logging Control"
)

@log_group.command(name="setup")
@app_commands.checks.has_permissions(manage_guild=True)
async def logs_setup(interaction: discord.Interaction):

    UltraAuditDB.ensure_tables(interaction.guild.id)

    view = SetupWizard(interaction.guild)

    embed = discord.Embed(
        title="🌍 Server Setup Wizard",
        description="Configure core server channels below.",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, view=view)


@log_group.command(name="view")
async def logs_view(interaction: discord.Interaction, event_type: str = None):

    logs = UltraAuditDB.fetch_logs(interaction.guild.id, {"event_type": event_type} if event_type else None)

    if not logs:
        return await interaction.response.send_message("No logs found.")

    view = LogViewer(logs)

    await interaction.response.send_message(embed=view.build(), view=view)


@log_group.command(name="export")
async def logs_export(interaction: discord.Interaction):

    logs = UltraAuditDB.fetch_logs(interaction.guild.id)

    data = json.dumps(logs, indent=4)

    file = discord.File(
        fp=io.BytesIO(data.encode()),
        filename="audit_export.json"
    )

    await interaction.response.send_message(file=file)


@log_group.command(name="purge")
@app_commands.checks.has_permissions(administrator=True)
async def logs_purge(interaction: discord.Interaction):

    UltraAuditDB.delete_logs(interaction.guild.id)

    await interaction.response.send_message(
        "🗑 All logs deleted."
    )


tree.add_command(log_group)


# ==========================================================
# 🧹 BACKGROUND CLEANUP TASK
# ==========================================================

async def log_cleanup_task():

    await bot.wait_until_ready()

    while not bot.is_closed():

        await asyncio.sleep(86400)  # Run once per day

        logs = db.fetch_all("audit_logs", {})

        for log in logs:
            ts = datetime.fromisoformat(log["timestamp"])
            if ts < datetime.utcnow() - timedelta(days=30):
                db.delete("audit_logs", {"id": log["id"]})


bot.loop.create_task(log_cleanup_task())

# ==========================================================
# 🌟 PHASE 8 – ELITE ROLE AUTOMATION + PROFESSIONAL WELCOME
# EXTENDED ENTERPRISE VERSION
# ==========================================================

import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ==========================================================
# 🧠 ROLE CONFLICT RESOLVER
# ==========================================================

async def resolve_role_conflicts(member: discord.Member):

    rules = RoleAutomationDB.get_rules(member.guild.id)

    applied_roles = []

    for rule in rules:
        role = member.guild.get_role(rule["role_id"])
        if role and role in member.roles:
            applied_roles.append((role, rule["priority"]))

    # Sort by priority
    applied_roles.sort(key=lambda x: x[1], reverse=True)

    # Keep highest priority role
    if len(applied_roles) > 1:
        highest = applied_roles[0][0]

        for role, _ in applied_roles[1:]:
            try:
                await member.remove_roles(role)
            except:
                pass

        if highest not in member.roles:
            await member.add_roles(highest)


# ==========================================================
# 🔄 BACKGROUND ROLE HEALTH MONITOR
# ==========================================================

async def role_health_monitor():

    await bot.wait_until_ready()

    while not bot.is_closed():

        await asyncio.sleep(3600)  # Run every hour

        guilds = bot.guilds

        for guild in guilds:

            rules = RoleAutomationDB.get_rules(guild.id)

            for rule in rules:

                role = guild.get_role(rule["role_id"])

                if not role:
                    # Role deleted manually → remove from DB
                    RoleAutomationDB.delete_rule(guild.id, rule["role_id"])

        print("✅ Role health scan completed.")


bot.loop.create_task(role_health_monitor())


# ==========================================================
# 🔵 BACKGROUND LEVEL WATCHER
# ==========================================================

async def level_watcher():

    await bot.wait_until_ready()

    while not bot.is_closed():

        await asyncio.sleep(300)  # Check every 5 mins

        # Example: fetch users from XP table
        users = db.fetch_all("economy_users", {})

        for user in users:

            guild_id = user["guild_id"]
            user_id = user["user_id"]
            level = user["level"]

            guild = bot.get_guild(guild_id)
            if not guild:
                continue

            member = guild.get_member(user_id)
            if not member:
                continue

            await process_level_role(member, level)

        print("✅ Level watcher sync done.")


bot.loop.create_task(level_watcher())


# ==========================================================
# 🖼 PROFESSIONAL WELCOME IMAGE GENERATOR
# ==========================================================

async def generate_professional_welcome(member: discord.Member, template: str):

    width = 1000
    height = 400

    base = Image.new("RGBA", (width, height), (15, 15, 15, 255))
    draw = ImageDraw.Draw(base)

    # Gradient Background
    for i in range(height):
        color = 20 + int((i / height) * 40)
        draw.line([(0, i), (width, i)], fill=(color, color, color))

    # Avatar
    try:
        avatar_url = member.display_avatar.url
        response = await bot.http.session.get(avatar_url)
        avatar_bytes = await response.read()
        avatar = Image.open(BytesIO(avatar_bytes)).resize((220, 220))
        avatar = ImageOps.circle(avatar)
        base.paste(avatar, (60, 90), avatar)
    except:
        pass

    # Fonts
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

    text_x = 320
    text_y = 120

    draw.text(
        (text_x, text_y),
        member.name,
        font=font_large,
        fill=(255, 255, 255)
    )

    draw.text(
        (text_x, text_y + 60),
        template,
        font=font_small,
        fill=(200, 200, 200)
    )

    draw.text(
        (text_x, text_y + 120),
        f"Member #{member.guild.member_count}",
        font=font_small,
        fill=(150, 150, 150)
    )

    buffer = BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


# ==========================================================
# 👋 ADVANCED WELCOME EVENT
# ==========================================================

@bot.event
async def on_member_join(member: discord.Member):

    settings = db.fetch_one("guild_settings", {
        "guild_id": member.guild.id
    })

    if not settings or not settings.get("welcome_enabled"):
        return

    channel = member.guild.get_channel(settings["welcome_channel_id"])
    if not channel:
        return

    template = settings.get("welcome_message", "Welcome {user}")

    content = template \
        .replace("{user}", member.mention) \
        .replace("{username}", member.name) \
        .replace("{server}", member.guild.name) \
        .replace("{member_count}", str(member.guild.member_count))

    image = await generate_professional_welcome(member, content)

    file = discord.File(image, filename="welcome.png")

    await channel.send(file=file)


# ==========================================================
# 🌟 WELCOME CONFIG COMMANDS
# ==========================================================

welcome_group = app_commands.Group(
    name="welcome",
    description="Advanced Welcome Configuration"
)


@welcome_group.command(name="toggle")
async def welcome_toggle(interaction: discord.Interaction, state: bool):

    db.update("guild_settings", {
        "guild_id": interaction.guild.id
    }, {
        "welcome_enabled": state
    })

    await interaction.response.send_message(
        f"✅ Welcome system set to {state}"
    )


@welcome_group.command(name="message")
async def welcome_message(
    interaction: discord.Interaction,
    message: str
):

    db.update("guild_settings", {
        "guild_id": interaction.guild.id
    }, {
        "welcome_message": message
    })

    await interaction.response.send_message(
        "✅ Welcome template updated."
    )


@welcome_group.command(name="preview")
async def welcome_preview(interaction: discord.Interaction):

    member = interaction.user

    settings = db.fetch_one("guild_settings", {
        "guild_id": interaction.guild.id
    })

    if not settings:
        return await interaction.response.send_message("Not configured.")

    template = settings.get("welcome_message", "Welcome {user}")

    content = template.replace("{user}", member.mention)

    image = await generate_professional_welcome(member, content)

    file = discord.File(image, filename="preview.png")

    await interaction.response.send_message(
        "🖼 Preview:",
        file=file
    )


tree.add_command(welcome_group)

# ==========================================================
# 🎮 PHASE 9 – ULTIMATE GAME & GAMBLING ENGINE
# ADVANCED SYSTEM WITH REAL MECHANICS
# ==========================================================

import random
import asyncio
from collections import defaultdict
from discord.ui import View, Button

# ==========================================================
# 🧠 GLOBAL GAME CONFIG
# ==========================================================

GAME_CONFIG = {
    "bet_limit": 50000,
    "cooldown": 5,
    "max_daily_win": 200000
}

user_game_cooldown = defaultdict(float)
user_daily_winnings = defaultdict(int)


# ==========================================================
# 🔐 COOLDOWN CHECK
# ==========================================================

def game_allowed(user_id):

    now = asyncio.get_event_loop().time()

    if now < user_game_cooldown[user_id]:
        return False

    user_game_cooldown[user_id] = now + GAME_CONFIG["cooldown"]
    return True


# ==========================================================
# 🎰 ADVANCED SLOT MACHINE
# ==========================================================

SLOT_SYMBOLS = [
    ("🍒", 50, 1.5),
    ("🍋", 40, 1.8),
    ("🔔", 8, 3),
    ("💎", 2, 10)
]

def weighted_symbol():

    total = sum(weight for _, weight, _ in SLOT_SYMBOLS)
    r = random.uniform(0, total)

    upto = 0
    for symbol, weight, multiplier in SLOT_SYMBOLS:
        if upto + weight >= r:
            return symbol, multiplier
        upto += weight


@tree.command(name="slots", description="Spin the ultimate slot machine")
async def slots(interaction: discord.Interaction, bet: int):

    if bet > GAME_CONFIG["bet_limit"]:
        return await interaction.response.send_message("❌ Bet exceeds limit.")

    if not game_allowed(interaction.user.id):
        return await interaction.response.send_message("⏳ Cooldown active.")

    user = db.fetch_one("economy_users", {
        "guild_id": interaction.guild.id,
        "user_id": interaction.user.id
    })

    if not user or user["balance"] < bet:
        return await interaction.response.send_message("❌ Not enough balance.")

    results = [weighted_symbol() for _ in range(3)]

    symbols = [r[0] for r in results]
    multipliers = [r[1] for r in results]

    if symbols.count(symbols[0]) == 3:
        base_multiplier = multipliers[0]
        win = int(bet * base_multiplier)

        if user_daily_winnings[interaction.user.id] + win > GAME_CONFIG["max_daily_win"]:
            win = 0

        new_balance = user["balance"] + win

        user_daily_winnings[interaction.user.id] += win

        db.update("economy_users", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        }, {"balance": new_balance})

        await interaction.response.send_message(
            f"🎰 {' | '.join(symbols)}\n🔥 JACKPOT! You win {win}"
        )

    else:
        new_balance = user["balance"] - bet

        db.update("economy_users", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        }, {"balance": new_balance})

        await interaction.response.send_message(
            f"🎰 {' | '.join(symbols)}\n❌ You lost {bet}"
        )


# ==========================================================
# 🪙 ADVANCED COINFLIP
# ==========================================================

@tree.command(name="coinflip", description="Risk-based coinflip")
async def coinflip(interaction: discord.Interaction, bet: int, mode: str):

    if not game_allowed(interaction.user.id):
        return await interaction.response.send_message("⏳ Cooldown.")

    user = db.fetch_one("economy_users", {
        "guild_id": interaction.guild.id,
        "user_id": interaction.user.id
    })

    if not user or user["balance"] < bet:
        return await interaction.response.send_message("❌ Not enough coins.")

    if mode == "high":
        win_multiplier = 3
        win_chance = 0.4

    elif mode == "safe":
        win_multiplier = 1.5
        win_chance = 0.6

    else:
        win_multiplier = 2
        win_chance = 0.5

    outcome = random.random()

    if outcome <= win_chance:

        win = int(bet * win_multiplier)
        new_balance = user["balance"] + win

        db.update("economy_users", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        }, {"balance": new_balance})

        await interaction.response.send_message(f"🪙 You win {win}!")

    else:

        new_balance = user["balance"] - bet

        db.update("economy_users", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        }, {"balance": new_balance})

        await interaction.response.send_message("🪙 You lost.")


# ==========================================================
# 🃏 REAL BLACKJACK ENGINE
# ==========================================================

def deal_card():
    return random.randint(2, 11)


class BlackjackGame:

    def __init__(self):
        self.player_cards = [deal_card(), deal_card()]
        self.dealer_cards = [deal_card(), deal_card()]

    def player_score(self):
        return sum(self.player_cards)

    def dealer_score(self):
        return sum(self.dealer_cards)

    def hit(self):
        self.player_cards.append(deal_card())

    def dealer_play(self):
        while self.dealer_score() < 17:
            self.dealer_cards.append(deal_card())


active_blackjack = {}


@tree.command(name="blackjack", description="Play real blackjack")
async def blackjack(interaction: discord.Interaction, bet: int):

    if bet > GAME_CONFIG["bet_limit"]:
        return await interaction.response.send_message("❌ Bet too high.")

    user = db.fetch_one("economy_users", {
        "guild_id": interaction.guild.id,
        "user_id": interaction.user.id
    })

    if not user or user["balance"] < bet:
        return await interaction.response.send_message("❌ Not enough balance.")

    game = BlackjackGame()
    active_blackjack[interaction.user.id] = (game, bet)

    view = BlackjackView(interaction.user)

    await interaction.response.send_message(
        f"🃏 Your Cards: {game.player_cards}\nDealer: [{game.dealer_cards[0]}, ?]",
        view=view
    )


class BlackjackView(View):

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user

    @discord.ui.button(label="Hit")
    async def hit(self, interaction: discord.Interaction, button: Button):

        if interaction.user.id not in active_blackjack:
            return

        game, bet = active_blackjack[interaction.user.id]
        game.hit()

        if game.player_score() > 21:
            await interaction.response.send_message("💥 Bust! You lose.")
            del active_blackjack[interaction.user.id]
            return

        await interaction.response.edit_message(
            content=f"🃏 Cards: {game.player_cards}\nDealer: [{game.dealer_cards[0]}, ?]",
            view=self
        )

    @discord.ui.button(label="Stand")
    async def stand(self, interaction: discord.Interaction, button: Button):

        if interaction.user.id not in active_blackjack:
            return

        game, bet = active_blackjack[interaction.user.id]
        game.dealer_play()

        player_score = game.player_score()
        dealer_score = game.dealer_score()

        user = db.fetch_one("economy_users", {
            "guild_id": interaction.guild.id,
            "user_id": interaction.user.id
        })

        if dealer_score > 21 or player_score > dealer_score:

            win = bet * 2
            new_balance = user["balance"] + win

            db.update("economy_users", {
                "guild_id": interaction.guild.id,
                "user_id": interaction.user.id
            }, {"balance": new_balance})

            result = f"🏆 You Win {win}"

        else:

            new_balance = user["balance"] - bet

            db.update("economy_users", {
                "guild_id": interaction.guild.id,
                "user_id": interaction.user.id
            }, {"balance": new_balance})

            result = "❌ Dealer Wins"

        await interaction.response.edit_message(
            content=f"🃏 Final\nPlayer: {player_score}\nDealer: {dealer_score}\n{result}",
            view=None
        )

        del active_blackjack[interaction.user.id]


# ==========================================================
# 🏆 GAME LEADERBOARD (MULTI FILTER)
# ==========================================================

@tree.command(name="gameleaderboard", description="Game stats leaderboard")
async def gameleaderboard(interaction: discord.Interaction, sort_by: str = "earnings"):

    stats = db.fetch_all("game_stats", {
        "guild_id": interaction.guild.id
    })

    stats = sorted(stats, key=lambda x: x.get(sort_by, 0), reverse=True)

    desc = ""

    for i, s in enumerate(stats[:10]):

        user = interaction.guild.get_member(s["user_id"])
        desc += f"{i+1}. {user} — 💰 {s['earnings']} | 🏆 {s['wins']} wins\n"

    await interaction.response.send_message(
        embed=discord.Embed(
            title="🏆 Game Leaderboard",
            description=desc,
            color=discord.Color.gold()
        )
)


# ==========================================================
# 📊 PHASE 10 – ANALYTICS & INTELLIGENCE ENGINE
# SERVER INSIGHTS + ECONOMY DATA + RISK SCORING
# ==========================================================

import statistics
from datetime import datetime, timedelta

# ==========================================================
# 🗄 ANALYTICS STORAGE
# ==========================================================

class AnalyticsDB:

    @staticmethod
    def log_member_event(guild_id, event_type):

        db.insert("analytics_events", {
            "guild_id": guild_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        })

    @staticmethod
    def log_message_activity(guild_id, channel_id, user_id):

        db.insert("message_stats", {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

    @staticmethod
    def get_events(guild_id, event_type=None):

        if event_type:
            return db.fetch_all("analytics_events", {
                "guild_id": guild_id,
                "event_type": event_type
            })

        return db.fetch_all("analytics_events", {
            "guild_id": guild_id
        })


# ==========================================================
# 👥 TRACK MEMBER JOINS / LEAVES
# ==========================================================

@bot.event
async def on_member_join(member):

    AnalyticsDB.log_member_event(member.guild.id, "join")


@bot.event
async def on_member_remove(member):

    AnalyticsDB.log_member_event(member.guild.id, "leave")


# ==========================================================
# 💬 TRACK MESSAGE ACTIVITY
# ==========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    AnalyticsDB.log_message_activity(
        message.guild.id,
        message.channel.id,
        message.author.id
    )


# ==========================================================
# 📊 SERVER ANALYTICS COMMAND
# ==========================================================

analytics_group = app_commands.Group(
    name="analytics",
    description="Server Intelligence Dashboard"
)


# ----------------------------------------------------------
# SERVER HEALTH RISK CALCULATION
# ----------------------------------------------------------

def calculate_server_health(guild: discord.Guild):

    members = guild.member_count

    joins = len(AnalyticsDB.get_events(guild.id, "join"))
    leaves = len(AnalyticsDB.get_events(guild.id, "leave"))

    net_growth = joins - leaves

    activity = db.fetch_all("message_stats", {
        "guild_id": guild.id
    })

    active_users = len(set([a["user_id"] for a in activity]))

    engagement_score = active_users / members if members else 0

    health_score = (engagement_score * 100) + (net_growth * 2)

    if health_score > 70:
        status = "🟢 Healthy"
    elif health_score > 40:
        status = "🟡 Moderate"
    else:
        status = "🔴 Risky"

    return {
        "health": health_score,
        "status": status,
        "engagement": engagement_score,
        "net_growth": net_growth
    }


# ----------------------------------------------------------
# /analytics server
# ----------------------------------------------------------

@analytics_group.command(name="server")
async def analytics_server(interaction: discord.Interaction):

    stats = calculate_server_health(interaction.guild)

    embed = discord.Embed(
        title="📊 Server Analytics",
        color=discord.Color.blue()
    )

    embed.add_field(name="Health Score", value=round(stats["health"], 2))
    embed.add_field(name="Status", value=stats["status"])
    embed.add_field(name="Engagement", value=round(stats["engagement"], 2))
    embed.add_field(name="Net Growth", value=stats["net_growth"])

    await interaction.response.send_message(embed=embed)


# ----------------------------------------------------------
# /analytics economy
# ----------------------------------------------------------

@analytics_group.command(name="economy")
async def analytics_economy(interaction: discord.Interaction):

    users = db.fetch_all("economy_users", {
        "guild_id": interaction.guild.id
    })

    total_coins = sum(u["balance"] for u in users)
    avg_balance = total_coins / len(users) if users else 0

    top = sorted(users, key=lambda x: x["balance"], reverse=True)[:5]

    desc = "🏦 Top Players:\n"

    for u in top:
        member = interaction.guild.get_member(u["user_id"])
        desc += f"{member} — 💰 {u['balance']}\n"

    embed = discord.Embed(
        title="💰 Economy Analytics",
        description=f"Total Coins: {total_coins}\nAvg Balance: {round(avg_balance,2)}\n\n{desc}",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed)


# ----------------------------------------------------------
# /analytics moderation
# ----------------------------------------------------------

@analytics_group.command(name="moderation")
async def analytics_moderation(interaction: discord.Interaction):

    bans = len(db.fetch_all("moderation_cases", {
        "guild_id": interaction.guild.id,
        "action": "Ban"
    }))

    warns = len(db.fetch_all("moderation_cases", {
        "guild_id": interaction.guild.id,
        "action": "Warn"
    }))

    embed = discord.Embed(
        title="⚖ Moderation Analytics",
        description=f"Bans: {bans}\nWarnings: {warns}",
        color=discord.Color.red()
    )

    await interaction.response.send_message(embed=embed)


# ----------------------------------------------------------
# /analytics risk
# ----------------------------------------------------------

@analytics_group.command(name="risk")
async def analytics_risk(interaction: discord.Interaction):

    stats = calculate_server_health(interaction.guild)

    await interaction.response.send_message(
        embed=discord.Embed(
            title="🚨 Risk Analysis",
            description=f"Health Score: {round(stats['health'],2)}\nStatus: {stats['status']}",
            color=discord.Color.orange()
        )
    )


tree.add_command(analytics_group)

# ==========================================================
# PHASE 11 – ENTERPRISE CONTROL FRAMEWORK
# CHUNK 1 / 4
# CORE ENGINE + GLOBAL LOGGER + SECURITY + MONITORING
# ==========================================================

import asyncio
import time
import os
import psutil
from collections import defaultdict
from datetime import datetime

# ==========================================================
# GLOBAL CONFIG
# ==========================================================

START_TIME = time.time()

utility_locks = defaultdict(bool)
command_usage_counter = defaultdict(int)

# ==========================================================
# ENTERPRISE ACTION LOGGER
# This logs EVERYTHING related to utility & admin actions
# ==========================================================

def enterprise_log(guild_id, user_id, action, details, status="success"):

    db.insert("enterprise_logs", {
        "guild_id": guild_id,
        "user_id": user_id,
        "action": action,
        "details": details,
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    })


async def log_wrapper(interaction, action_name, func):

    start = time.time()

    try:
        await func()
        status = "success"

    except Exception as e:
        status = f"error: {str(e)}"

    duration = round(time.time() - start, 3)

    enterprise_log(
        interaction.guild.id,
        interaction.user.id,
        action_name,
        f"Execution Time: {duration}s",
        status
    )

    command_usage_counter[action_name] += 1


# ==========================================================
# PERMISSION VALIDATION LAYER
# Protects utility commands from abuse
# ==========================================================

def require_admin(interaction):

    if not interaction.user.guild_permissions.administrator:
        return False
    return True


def require_manage_guild(interaction):

    if not interaction.user.guild_permissions.manage_guild:
        return False
    return True


def require_manage_roles(interaction):

    if not interaction.user.guild_permissions.manage_roles:
        return False
    return True


# ==========================================================
# SYSTEM HEALTH MONITOR
# Runs background metrics tracking
# ==========================================================

async def system_health_monitor():

    await bot.wait_until_ready()

    while not bot.is_closed():

        process = psutil.Process(os.getpid())

        memory_mb = process.memory_info().rss / 1024 ** 2
        cpu_percent = process.cpu_percent()

        db.insert("system_metrics", {
            "guild_count": len(bot.guilds),
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "timestamp": datetime.utcnow().isoformat()
        })

        await asyncio.sleep(300)  # 5 minutes


bot.loop.create_task(system_health_monitor())


# ==========================================================
# AUDIT EVENT TRACKER
# Logs server structural changes automatically
# ==========================================================

@bot.event
async def on_member_join(member):

    enterprise_log(
        member.guild.id,
        member.id,
        "member_join",
        "User joined server"
    )


@bot.event
async def on_member_remove(member):

    enterprise_log(
        member.guild.id,
        member.id,
        "member_leave",
        "User left server"
    )


@bot.event
async def on_guild_channel_create(channel):

    enterprise_log(
        channel.guild.id,
        0,
        "channel_create",
        f"Channel created: {channel.name}"
    )


@bot.event
async def on_guild_channel_delete(channel):

    enterprise_log(
        channel.guild.id,
        0,
        "channel_delete",
        f"Channel deleted: {channel.name}"
    )


@bot.event
async def on_guild_role_create(role):

    enterprise_log(
        role.guild.id,
        0,
        "role_create",
        f"Role created: {role.name}"
    )


@bot.event
async def on_guild_role_delete(role):

    enterprise_log(
        role.guild.id,
        0,
        "role_delete",
        f"Role deleted: {role.name}"
    )


# ==========================================================
# COMMAND USAGE TRACKER
# Tracks how often each utility command is used
# ==========================================================

@bot.event
async def on_app_command_completion(interaction: discord.Interaction):

    if interaction.command:
        command_name = interaction.command.name

        db.insert("command_stats", {
            "guild_id": interaction.guild.id if interaction.guild else None,
            "command": command_name,
            "user_id": interaction.user.id,
            "timestamp": datetime.utcnow().isoformat()
        })

        command_usage_counter[command_name] += 1

# ==========================================================
# PHASE 11 – ENTERPRISE CONTROL FRAMEWORK
# CHUNK 2 / 4
# ADVANCED UTILITY COMMANDS + ADMIN POWER TOOLS
# ==========================================================

from discord.ext import tasks

# ==========================================================
# GLOBAL SYSTEM STATES
# ==========================================================

lockdown_state = defaultdict(bool)
raid_detection_counter = defaultdict(int)

# ==========================================================
# SMART EXECUTION WRAPPER
# All admin tools use this for logging + tracking
# ==========================================================

async def run_tool(interaction, tool_name, logic):

    if not interaction.guild:
        return

    await interaction.response.defer()

    await log_wrapper(
        interaction,
        tool_name,
        logic
    )

    await interaction.followup.send(
        f"✅ `{tool_name}` executed successfully."
    )


# ==========================================================
# 🧹 ADVANCED PURGE SYSTEM
# With filters + preview + confirmation
# ==========================================================

@tree.command(
    name="purge_advanced",
    description="Enterprise level message purge"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_advanced(
    interaction: discord.Interaction,
    amount: int,
    keyword: str = None,
    bots_only: bool = False
):

    await interaction.response.defer()

    messages = []

    async for msg in interaction.channel.history(limit=amount):
        if keyword and keyword.lower() not in msg.content.lower():
            continue

        if bots_only and not msg.author.bot:
            continue

        messages.append(msg)

    preview_embed = discord.Embed(
        title="🗑 Purge Preview",
        description=f"{len(messages)} messages will be deleted.",
        color=discord.Color.red()
    )

    preview_msg = await interaction.followup.send(embed=preview_embed)

    await asyncio.sleep(5)

    for msg in messages:
        try:
            await msg.delete()
        except:
            pass

    await preview_msg.edit(content="✅ Messages deleted.", embed=None)

    enterprise_log(
        interaction.guild.id,
        interaction.user.id,
        "purge_advanced",
        f"Deleted {len(messages)} messages"
    )


# ==========================================================
# 👥 MASS ROLE ENGINE (PROTECTED VERSION)
# ==========================================================

@tree.command(
    name="mass_role_advanced",
    description="Enterprise mass role system"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def mass_role_advanced(
    interaction: discord.Interaction,
    role: discord.Role,
    action: str,
    only_online: bool = False
):

    await interaction.response.defer()

    processed = 0

    for member in interaction.guild.members:

        if only_online and member.status == discord.Status.offline:
            continue

        if role.position >= interaction.guild.me.top_role.position:
            continue

        try:
            if action == "add":
                await member.add_roles(role)

            elif action == "remove":
                await member.remove_roles(role)

            processed += 1

        except:
            pass

    enterprise_log(
        interaction.guild.id,
        interaction.user.id,
        "mass_role_advanced",
        f"Action: {action} | Role: {role.name} | Processed: {processed}"
    )

    await interaction.followup.send(
        f"✅ Mass role `{action}` completed.\nProcessed: {processed}"
    )


# ==========================================================
# 🔒 ADVANCED LOCKDOWN SYSTEM
# Full / Partial / Temporary
# ==========================================================

@tree.command(
    name="lockdown_advanced",
    description="Enterprise server lockdown"
)
@app_commands.checks.has_permissions(administrator=True)
async def lockdown_advanced(
    interaction: discord.Interaction,
    mode: str = "full",
    duration_minutes: int = 0
):

    guild = interaction.guild

    lockdown_state[guild.id] = True

    for channel in guild.channels:

        if mode == "chat" and not isinstance(channel, discord.TextChannel):
            continue

        try:
            await channel.set_permissions(
                guild.default_role,
                send_messages=False
            )
        except:
            pass

    enterprise_log(
        guild.id,
        interaction.user.id,
        "lockdown_advanced",
        f"Mode: {mode} | Duration: {duration_minutes}"
    )

    await interaction.response.send_message("🚨 Server locked.")

    if duration_minutes > 0:

        await asyncio.sleep(duration_minutes * 60)

        for channel in guild.channels:
            try:
                await channel.set_permissions(
                    guild.default_role,
                    send_messages=True
                )
            except:
                pass

        lockdown_state[guild.id] = False

        await interaction.channel.send("🔓 Auto unlock completed.")


# ==========================================================
# 🔓 UNLOCK COMMAND
# ==========================================================

@tree.command(
    name="unlock_advanced",
    description="Remove server lockdown"
)
@app_commands.checks.has_permissions(administrator=True)
async def unlock_advanced(interaction: discord.Interaction):

    guild = interaction.guild
    lockdown_state[guild.id] = False

    for channel in guild.channels:
        try:
            await channel.set_permissions(
                guild.default_role,
                send_messages=True
            )
        except:
            pass

    enterprise_log(
        guild.id,
        interaction.user.id,
        "unlock_advanced",
        "Server unlocked"
    )

    await interaction.response.send_message("🔓 Server unlocked.")


# ==========================================================
# 🚀 COMMAND STATISTICS DASHBOARD
# Shows most used utility tools
# ==========================================================

@tree.command(
    name="utility_stats",
    description="Show tool usage statistics"
)
@app_commands.checks.has_permissions(administrator=True)
async def utility_stats(interaction: discord.Interaction):

    sorted_usage = sorted(
        command_usage_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    desc = ""

    for cmd, count in sorted_usage:
        desc += f"🔹 {cmd} → {count} uses\n"

    embed = discord.Embed(
        title="📊 Utility Usage Stats",
        description=desc or "No data yet.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)

# ==========================================================
# PHASE 11 – ENTERPRISE CONTROL FRAMEWORK
# CHUNK 3 / 4
# THREAT DETECTION + AUTO SECURITY + SMART PROTECTION
# ==========================================================

# ==========================================================
# RAID DETECTION ENGINE
# Detects abnormal join / spam patterns
# ==========================================================

raid_join_tracker = defaultdict(int)
raid_message_tracker = defaultdict(int)


@bot.event
async def on_member_join(member):

    guild_id = member.guild.id
    raid_join_tracker[guild_id] += 1

    enterprise_log(
        guild_id,
        member.id,
        "join_detected",
        "Join event recorded for raid detection"
    )

    # If too many joins in short time → Auto lockdown
    if raid_join_tracker[guild_id] > 25:

        for channel in member.guild.channels:
            try:
                await channel.set_permissions(
                    member.guild.default_role,
                    send_messages=False
                )
            except:
                pass

        lockdown_state[guild_id] = True

        enterprise_log(
            guild_id,
            0,
            "auto_lockdown",
            "Raid detected via join spike"
        )

        raid_join_tracker[guild_id] = 0


async def reset_raid_counters():

    await bot.wait_until_ready()

    while not bot.is_closed():

        await asyncio.sleep(60)

        raid_join_tracker.clear()
        raid_message_tracker.clear()


bot.loop.create_task(reset_raid_counters())


# ==========================================================
# MESSAGE SPAM DETECTOR
# Detects rapid message spam patterns
# ==========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    guild_id = message.guild.id

    raid_message_tracker[guild_id] += 1

    # Spam threshold
    if raid_message_tracker[guild_id] > 80:

        for channel in message.guild.channels:
            try:
                await channel.set_permissions(
                    message.guild.default_role,
                    send_messages=False
                )
            except:
                pass

        lockdown_state[guild_id] = True

        enterprise_log(
            guild_id,
            0,
            "auto_lockdown",
            "Spam threshold exceeded"
        )

        raid_message_tracker[guild_id] = 0

    await bot.process_commands(message)


# ==========================================================
# PERMISSION SCANNER
# Detect dangerous permission assignments
# ==========================================================

@tree.command(
    name="permission_scan",
    description="Scan for dangerous role permissions"
)
@app_commands.checks.has_permissions(administrator=True)
async def permission_scan(interaction: discord.Interaction):

    dangerous = []

    for role in interaction.guild.roles:

        perms = role.permissions

        if perms.administrator or perms.manage_guild:

            dangerous.append(role.name)

    desc = "\n".join([f"⚠ {r}" for r in dangerous]) or "No dangerous roles detected."

    embed = discord.Embed(
        title="🔍 Permission Security Scan",
        description=desc,
        color=discord.Color.orange()
    )

    enterprise_log(
        interaction.guild.id,
        interaction.user.id,
        "permission_scan",
        "Security scan executed"
    )

    await interaction.response.send_message(embed=embed)


# ==========================================================
# BROKEN ROLE CLEANER
# Removes roles that no longer exist
# ==========================================================

@tree.command(
    name="cleanup_roles",
    description="Remove broken role references"
)
@app_commands.checks.has_permissions(administrator=True)
async def cleanup_roles(interaction: discord.Interaction):

    guild = interaction.guild

    existing_roles = [r.id for r in guild.roles]

    removed = 0

    rows = db.fetch_all("enterprise_role_config", {
        "guild_id": guild.id
    })

    for row in rows:

        if row["role_id"] not in existing_roles:

            db.delete("enterprise_role_config", {
                "guild_id": guild.id,
                "role_id": row["role_id"]
            })

            removed += 1

    enterprise_log(
        guild.id,
        interaction.user.id,
        "cleanup_roles",
        f"Removed {removed} broken role entries"
    )

    await interaction.response.send_message(
        f"🧹 Cleaned up {removed} broken role records."
    )


# ==========================================================
# RATE LIMIT PROTECTION
# Blocks rapid repeated command abuse
# ==========================================================

user_command_timestamps = defaultdict(float)


def rate_limit_check(user_id):

    now = time.time()

    if now - user_command_timestamps[user_id] < 2:
        return False

    user_command_timestamps[user_id] = now
    return True


@bot.event
async def on_app_command(interaction: discord.Interaction):

    if not rate_limit_check(interaction.user.id):

        enterprise_log(
            interaction.guild.id,
            interaction.user.id,
            "rate_limit_blocked",
            "User triggered command too fast",
            status="blocked"
        )

        await interaction.response.send_message(
            "⛔ Slow down — rate limit active.",
            ephemeral=True
    )

# ==========================================================
# PHASE 11 – ENTERPRISE CONTROL FRAMEWORK
# CHUNK 4 / 4
# BACKUP ENGINE + RESTORE SYSTEM + ENTERPRISE CONTROL PANEL
# ==========================================================

import json
from discord.ui import Button, View

# ==========================================================
# FULL SERVER CONFIG BACKUP
# Backs up roles, channels, permissions
# ==========================================================

@tree.command(
    name="backup_server",
    description="Create full server configuration backup"
)
@app_commands.checks.has_permissions(administrator=True)
async def backup_server(interaction: discord.Interaction):

    guild = interaction.guild

    backup_data = {
        "guild_name": guild.name,
        "roles": [],
        "channels": []
    }

    # Backup Roles
    for role in guild.roles:
        backup_data["roles"].append({
            "name": role.name,
            "permissions": role.permissions.value,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable
        })

    # Backup Channels
    for channel in guild.channels:
        backup_data["channels"].append({
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position
        })

    backup_json = json.dumps(backup_data, indent=4)

    file = discord.File(
        fp=io.StringIO(backup_json),
        filename="server_backup.json"
    )

    enterprise_log(
        guild.id,
        interaction.user.id,
        "backup_server",
        "Server backup created"
    )

    await interaction.response.send_message(
        "✅ Backup created.",
        file=file
    )


# ==========================================================
# RESTORE SERVER CONFIG FROM BACKUP
# ==========================================================

@tree.command(
    name="restore_server",
    description="Restore server from backup file"
)
@app_commands.checks.has_permissions(administrator=True)
async def restore_server(
    interaction: discord.Interaction,
    backup_file: discord.Attachment
):

    await interaction.response.defer()

    file_bytes = await backup_file.read()
    backup_data = json.loads(file_bytes.decode())

    guild = interaction.guild

    # Restore Roles
    for role_data in backup_data.get("roles", []):

        try:
            await guild.create_role(
                name=role_data["name"],
                permissions=discord.Permissions(
                    role_data["permissions"]
                ),
                color=discord.Color(role_data["color"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"]
            )
        except:
            pass

    # Restore Channels
    for channel_data in backup_data.get("channels", []):

        try:
            if "text" in channel_data["type"]:
                await guild.create_text_channel(
                    name=channel_data["name"],
                    position=channel_data["position"]
                )
            else:
                await guild.create_voice_channel(
                    name=channel_data["name"],
                    position=channel_data["position"]
                )
        except:
            pass

    enterprise_log(
        guild.id,
        interaction.user.id,
        "restore_server",
        "Server restored from backup"
    )

    await interaction.followup.send("🔄 Server restore process completed.")


# ==========================================================
# ENTERPRISE CONTROL PANEL
# Central Admin Dashboard
# ==========================================================

class ControlPanel(View):

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="View Metrics", style=discord.ButtonStyle.primary)
    async def metrics(self, interaction: discord.Interaction, button: Button):

        process = psutil.Process(os.getpid())
        memory = round(process.memory_info().rss / 1024 ** 2, 2)
        cpu = process.cpu_percent()

        embed = discord.Embed(
            title="📊 Live Metrics",
            description=f"CPU: {cpu}%\nMemory: {memory} MB",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="View Logs", style=discord.ButtonStyle.secondary)
    async def logs(self, interaction: discord.Interaction, button: Button):

        logs = db.fetch_all("enterprise_logs", {
            "guild_id": interaction.guild.id
        })

        logs = logs[-10:]

        desc = ""

        for log in logs:
            desc += f"{log['timestamp']} | {log['action']}\n"

        embed = discord.Embed(
            title="📝 Recent Logs",
            description=desc or "No logs",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(
    name="control_panel",
    description="Open enterprise admin control panel"
)
@app_commands.checks.has_permissions(administrator=True)
async def control_panel(interaction: discord.Interaction):

    await interaction.response.send_message(
        "🛠 Enterprise Control Panel",
        view=ControlPanel()
    )


# ==========================================================
# SYSTEM CLEANUP TASK
# Periodically removes old logs
# ==========================================================

async def cleanup_old_logs():

    await bot.wait_until_ready()

    while not bot.is_closed():

        db.delete_old("enterprise_logs", days=30)

        await asyncio.sleep(86400)  # Run once daily


bot.loop.create_task(cleanup_old_logs())


# ==========================================================
# END OF ENTERPRISE FRAMEWORK
# ==========================================================

print("✅ PHASE 11 ENTERPRISE FRAMEWORK LOADED")

# ==========================================================
# 🌌 PHASE 12 – ENTERPRISE HELP SYSTEM
# DROPDOWN + COMMAND DETAIL POPUP
# ==========================================================

from discord.ui import View, Select, Button


# ==========================================================
# GET ALL COMMANDS GROUPED
# ==========================================================

def get_command_map():

    command_map = {}

    for cmd in tree.walk_commands():

        group = "Ungrouped"

        if hasattr(cmd, "parent") and cmd.parent:
            group = cmd.parent.name

        if group not in command_map:
            command_map[group] = []

        command_map[group].append(cmd)

    return command_map


COMMAND_MAP = get_command_map()


# ==========================================================
# HELP VIEW WITH DROPDOWN
# ==========================================================

class HelpDropdown(View):

    def __init__(self):

        super().__init__(timeout=180)

        self.command_map = COMMAND_MAP
        self.group_names = list(self.command_map.keys())

        # Dropdown Options = Command Names
        options = []

        for group, cmds in self.command_map.items():

            for cmd in cmds:

                options.append(
                    discord.SelectOption(
                        label=f"/{cmd.name}",
                        description=cmd.description or "No description",
                        value=f"{group}:{cmd.name}"
                    )
                )

        self.select = Select(
            placeholder="🔍 Select a command to view details...",
            options=options[:25]  # Discord max limit
        )

        self.select.callback = self.select_callback

        self.add_item(self.select)

    # ======================================================
    # WHEN COMMAND SELECTED
    # ======================================================

    async def select_callback(self, interaction: discord.Interaction):

        value = self.select.values[0]

        group, command_name = value.split(":")

        command = None

        for cmd in self.command_map[group]:

            if cmd.name == command_name:
                command = cmd
                break

        if not command:

            return await interaction.response.send_message(
                "❌ Command not found.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"📖 /{command.name}",
            description=command.description or "No description",
            color=discord.Color.green()
        )

        # Parameters
        params = getattr(command, "parameters", [])

        if params:

            param_text = ""

            for p in params:
                param_text += f"🔹 `{p.name}`\n"

            embed.add_field(
                name="📦 Parameters",
                value=param_text,
                inline=False
            )

        else:

            embed.add_field(
                name="📦 Parameters",
                value="None",
                inline=False
            )

        embed.add_field(
            name="🛡 Permission",
            value="Check required permission in command docs.",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ==========================================================
# MAIN HELP COMMAND
# ==========================================================

@tree.command(
    name="help",
    description="Open Enterprise Help Center"
)
async def help_command(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🌌 Enterprise Help Center",
        description="Select a command from the dropdown below to see full details.",
        color=discord.Color.gold()
    )

    view = HelpDropdown()

    await interaction.response.send_message(
        embed=embed,
        view=view
    )


# ==========================================================
# AI HELP (UNCHANGED BUT IMPROVED UI)
# ==========================================================

@tree.command(
    name="help_ai",
    description="Ask AI about bot commands"
)
async def help_ai_command(interaction: discord.Interaction,
                          question: str):

    await interaction.response.defer()

    permission_response = await smart_permission_check(
        question,
        interaction.user
    )

    if permission_response:

        embed = discord.Embed(
            title="🔐 Permission Warning",
            description=permission_response,
            color=discord.Color.red()
        )

        return await interaction.followup.send(embed=embed)

    ai_response = await ask_ai(question)

    recommendations = recommend_commands(question)

    extra = ""

    if recommendations:

        extra += "\n\n🔎 Suggested Commands:\n"

        for cmd in recommendations:
            extra += f"✅ /{cmd['name']} — {cmd['description']}\n"

    embed = discord.Embed(
        title="🤖 AI Assistant",
        description=ai_response[:3500] + extra,
        color=discord.Color.green()
    )

    await interaction.followup.send(embed=embed)


# ==========================================================
# COMMAND SEARCH (OPTIONAL)
# ==========================================================

@tree.command(
    name="help_search",
    description="Search commands instantly"
)
async def help_search_command(interaction: discord.Interaction,
                              query: str):

    results = []

    for cmd in tree.walk_commands():

        if query.lower() in cmd.name.lower() or \
           query.lower() in (cmd.description or "").lower():

            results.append(cmd)

    if not results:

        return await interaction.response.send_message(
            "❌ No commands found.",
            ephemeral=True
        )

    embed = discord.Embed(
        title=f"🔍 Results – {query}",
        color=discord.Color.blue()
    )

    for cmd in results[:15]:

        embed.add_field(
            name=f"/{cmd.name}",
            value=cmd.description or "No description",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================================
# 🌌 ENTERPRISE HELP SYSTEM – PART 2
# CATEGORY DROPDOWN + PAGINATION + NAVIGATION
# ==========================================================


# ==========================================================
# HELP VIEW (MAIN INTERACTION CONTROLLER)
# ==========================================================

class HelpView(View):

    def __init__(self, user_id: int):

        super().__init__(timeout=300)

        self.user_id = user_id

        self.database = COMMAND_DATABASE

        self.categories = list(self.database.keys())

        self.current_category = self.categories[0]

        self.pagination = PaginationEngine(
            self.database[self.current_category]
        )

        # Create Category Dropdown
        options = []

        for cat in self.categories:

            options.append(
                discord.SelectOption(
                    label=cat,
                    value=cat
                )
            )

        self.category_select = Select(
            placeholder="📂 Select Command Category",
            options=options
        )

        self.category_select.callback = self.category_changed

        self.add_item(self.category_select)

    # ======================================================
    # CATEGORY SWITCH
    # ======================================================

    async def category_changed(self, interaction: discord.Interaction):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ This menu is not yours.",
                ephemeral=True
            )

        selected_category = self.category_select.values[0]

        self.current_category = selected_category

        self.pagination = PaginationEngine(
            self.database[self.current_category]
        )

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # ======================================================
    # BUILD HELP EMBED (CATEGORY + PAGINATION)
    # ======================================================

    def build_embed(self):

        commands = self.pagination.get_page()

        embed = discord.Embed(
            title=f"🌌 Help – {self.current_category}",
            description="Select commands below or change category.",
            color=discord.Color.gold()
        )

        for cmd in commands:

            embed.add_field(
                name=f"/{cmd.name}",
                value=cmd.description or "No description",
                inline=False
            )

        embed.set_footer(
            text=f"Page {self.pagination.page + 1} / {self.pagination.max_pages()}"
        )

        return embed

    # ======================================================
    # PREVIOUS PAGE BUTTON
    # ======================================================

    @discord.ui.button(label="⬅ Previous", style=discord.ButtonStyle.primary)
    async def previous_page(self,
                            interaction: discord.Interaction,
                            button: Button):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Not your session.",
                ephemeral=True
            )

        self.pagination.previous_page()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # ======================================================
    # NEXT PAGE BUTTON
    # ======================================================

    @discord.ui.button(label="Next ➡", style=discord.ButtonStyle.primary)
    async def next_page(self,
                        interaction: discord.Interaction,
                        button: Button):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Not your session.",
                ephemeral=True
            )

        self.pagination.next_page()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # ======================================================
    # COMMAND DETAIL BUTTON
    # Shows popup for selected command
    # ======================================================

    @discord.ui.button(label="🔎 View Command", style=discord.ButtonStyle.success)
    async def view_command(self,
                           interaction: discord.Interaction,
                           button: Button):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Not your session.",
                ephemeral=True
            )

        commands = self.pagination.get_page()

        if not commands:
            return await interaction.response.send_message(
                "❌ No commands on this page.",
                ephemeral=True
            )

        # Show first command as example popup
        command = commands[0]

        embed = build_command_detail_embed(command)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
               )

# ==========================================================
# 🌌 PART 3 – ADVANCED HELP ENGINE
# PAGINATION + SEARCH + LIVE FILTER + COMMAND DETAIL
# ==========================================================

# ==========================================================
# SESSION STORAGE
# ==========================================================

HELP_SESSIONS = {}


def get_help_session(user_id):

    if user_id not in HELP_SESSIONS:

        HELP_SESSIONS[user_id] = {
            "category": None,
            "page": 0,
            "search": None,
            "last_message_id": None
        }

    return HELP_SESSIONS[user_id]


def clear_help_session(user_id):

    if user_id in HELP_SESSIONS:
        del HELP_SESSIONS[user_id]


# ==========================================================
# COMMAND FILTER ENGINE
# ==========================================================

def filter_commands(commands, search=None):

    if not search:
        return commands

    result = []

    for cmd in commands:

        if search.lower() in cmd.name.lower() or \
           search.lower() in (cmd.description or "").lower():

            result.append(cmd)

    return result


# ==========================================================
# PAGINATION ENGINE
# ==========================================================

class HelpPagination:

    def __init__(self, commands):

        self.commands = commands
        self.page = 0
        self.per_page = 6

    def max_pages(self):

        return max(1, (len(self.commands) - 1) // self.per_page + 1)

    def page_items(self):

        start = self.page * self.per_page
        end = start + self.per_page

        return self.commands[start:end]

    def next(self):

        if self.page < self.max_pages() - 1:
            self.page += 1

    def prev(self):

        if self.page > 0:
            self.page -= 1


# ==========================================================
# HELP VIEW WITH FULL CONTROL
# ==========================================================

class EnterpriseHelpView(View):

    def __init__(self, user_id):

        super().__init__(timeout=300)

        self.user_id = user_id
        self.session = get_help_session(user_id)

        self.categories = list(COMMAND_DATABASE.keys())

        if not self.session["category"]:
            self.session["category"] = self.categories[0]

        self.refresh()

        self.build_dropdown()
        self.build_search_button()

    # ======================================================
    # REFRESH DATA
    # ======================================================

    def refresh(self):

        category = self.session["category"]
        search = self.session["search"]

        commands = COMMAND_DATABASE.get(category, [])
        commands = filter_commands(commands, search)

        self.pagination = HelpPagination(commands)

    # ======================================================
    # BUILD CATEGORY DROPDOWN
    # ======================================================

    def build_dropdown(self):

        options = []

        for cat in self.categories:

            options.append(
                discord.SelectOption(
                    label=cat,
                    value=cat
                )
            )

        dropdown = Select(
            placeholder="📂 Switch Category",
            options=options
        )

        dropdown.callback = self.category_changed

        self.add_item(dropdown)

    # ======================================================
    # CATEGORY CHANGE
    # ======================================================

    async def category_changed(self, interaction):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Not your session",
                ephemeral=True
            )

        selected = interaction.data["values"][0]

        self.session["category"] = selected
        self.session["page"] = 0

        self.refresh()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # ======================================================
    # BUILD SEARCH BUTTON
    # ======================================================

    def build_search_button(self):

        button = Button(
            label="🔎 Search",
            style=discord.ButtonStyle.secondary
        )

        button.callback = self.search_popup

        self.add_item(button)

    async def search_popup(self, interaction):

        if interaction.user.id != self.user_id:
            return

        await interaction.response.send_modal(SearchModal(self))

    # ======================================================
    # BUILD EMBED
    # ======================================================

    def build_embed(self):

        cmds = self.pagination.page_items()

        embed = discord.Embed(
            title=f"🌌 Help – {self.session['category']}",
            color=discord.Color.gold()
        )

        if not cmds:

            embed.description = "No commands found."

        for cmd in cmds:

            embed.add_field(
                name=f"/{cmd.name}",
                value=cmd.description or "No description",
                inline=False
            )

        embed.set_footer(
            text=f"Page {self.pagination.page + 1} / {self.pagination.max_pages()}"
        )

        return embed

    # ======================================================
    # PAGINATION BUTTONS
    # ======================================================

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction, button):

        if interaction.user.id != self.user_id:
            return

        self.pagination.prev()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    @discord.ui.button(label="➡", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction, button):

        if interaction.user.id != self.user_id:
            return

        self.pagination.next()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    # ======================================================
    # COMMAND DETAIL POPUP
    # ======================================================

    @discord.ui.button(label="📖 View Command", style=discord.ButtonStyle.success)
    async def view_command(self, interaction, button):

        if interaction.user.id != self.user_id:
            return

        cmds = self.pagination.page_items()

        if not cmds:
            return

        command = cmds[0]

        embed = build_command_detail_embed(command)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ==========================================================
# SEARCH MODAL
# ==========================================================

class SearchModal(discord.ui.Modal, title="Search Commands"):

    def __init__(self, view):

        super().__init__()
        self.view = view

    search_input = discord.ui.TextInput(
        label="Keyword",
        placeholder="Type command name or keyword..."
    )

    async def on_submit(self, interaction):

        self.view.session["search"] = self.search_input.value
        self.view.session["page"] = 0
        self.view.refresh()

        await interaction.response.edit_message(
            embed=self.view.build_embed(),
            view=self.view
        )


# ==========================================================
# MAIN HELP COMMAND
# ==========================================================

@tree.command(
    name="help",
    description="Open Advanced Help System"
)
async def help_command(interaction):

    view = EnterpriseHelpView(interaction.user.id)

    embed = view.build_embed()

    await interaction.response.send_message(
        embed=embed,
        view=view
)

# ==========================================================
# 🌌 PART 4 – ENTERPRISE COMMAND INTELLIGENCE ENGINE
# FULL COMMAND ANALYSIS + AUTO DOCUMENT GENERATION
# ==========================================================

import json
from typing import Dict


# ==========================================================
# COMMAND INTROSPECTION ENGINE
# ==========================================================

class CommandIntrospector:

    def __init__(self, command):

        self.command = command
        self.name = command.name
        self.description = command.description or "No description"
        self.params = getattr(command, "parameters", [])
        self.group = self.get_group()
        self.aliases = getattr(command, "aliases", [])

    # ------------------------------------------------------
    # Detect Command Group
    # ------------------------------------------------------

    def get_group(self):

        if hasattr(self.command, "parent") and self.command.parent:
            return self.command.parent.name

        return "Standalone"

    # ------------------------------------------------------
    # Auto Permission Detection (Basic)
    # ------------------------------------------------------

    def detect_permissions(self):

        perms = []

        text = self.description.lower()

        if "ban" in text:
            perms.append("Ban Members")

        if "kick" in text:
            perms.append("Kick Members")

        if "manage" in text:
            perms.append("Manage Permissions")

        return perms or ["No specific permission detected"]

    # ------------------------------------------------------
    # Generate Example Usage
    # ------------------------------------------------------

    def generate_example(self):

        example = f"/{self.name}"

        for param in self.params:

            example += f" <{param.name}>"

        return example

    # ------------------------------------------------------
    # Build Detailed Embed
    # ------------------------------------------------------

    def build_embed(self):

        embed = discord.Embed(
            title=f"📖 /{self.name}",
            description=self.description,
            color=discord.Color.green()
        )

        embed.add_field(
            name="📂 Group",
            value=self.group,
            inline=False
        )

        embed.add_field(
            name="🔐 Required Permissions",
            value="\n".join(self.detect_permissions()),
            inline=False
        )

        embed.add_field(
            name="📝 Example",
            value=self.generate_example(),
            inline=False
        )

        if self.aliases:

            embed.add_field(
                name="🔁 Aliases",
                value=", ".join(self.aliases),
                inline=False
            )

        if self.params:

            param_text = ""

            for p in self.params:
                param_text += f"🔹 `{p.name}`\n"

            embed.add_field(
                name="📦 Parameters",
                value=param_text,
                inline=False
            )

        return embed

    # ------------------------------------------------------
    # Export as JSON
    # ------------------------------------------------------

    def export_json(self):

        return json.dumps({
            "name": self.name,
            "description": self.description,
            "group": self.group,
            "aliases": self.aliases,
            "parameters": [p.name for p in self.params],
            "permissions": self.detect_permissions()
        }, indent=4)

    # ------------------------------------------------------
    # Export as Markdown
    # ------------------------------------------------------

    def export_markdown(self):

        md = f"""
# /{self.name}

## Description
{self.description}

## Group
{self.group}

## Example
`{self.generate_example()}`

## Permissions
"""

        for perm in self.detect_permissions():
            md += f"- {perm}\n"

        return md


# ==========================================================
# COMMAND DETAIL POPUP USING INTROSPECTOR
# ==========================================================

class CommandDetailPopup(discord.ui.View):

    def __init__(self, command):

        super().__init__(timeout=120)
        self.introspector = CommandIntrospector(command)

    @discord.ui.button(label="📄 View JSON", style=discord.ButtonStyle.secondary)
    async def json_view(self, interaction, button):

        data = self.introspector.export_json()

        await interaction.response.send_message(
            f"```json\n{data}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="📝 View Markdown", style=discord.ButtonStyle.primary)
    async def markdown_view(self, interaction, button):

        data = self.introspector.export_markdown()

        await interaction.response.send_message(
            f"```md\n{data}\n```",
            ephemeral=True
        )


# ==========================================================
# FUNCTION USED BY HELP SYSTEM
# ==========================================================

def open_command_detail(command):

    return CommandDetailPopup(command)

# ==========================================================
# 🌌 PART 5 – HELP ANALYTICS & SMART SUGGESTION ENGINE
# DATA DRIVEN HELP SYSTEM
# ==========================================================

import time


# ==========================================================
# DATABASE TABLE REQUIRED
# help_stats
#  guild_id
#  command_name
#  usage_count
# ==========================================================


# ==========================================================
# TRACK COMMAND USAGE
# Call this inside every command
# ==========================================================

def track_command_usage(guild_id, command_name):

    row = db.fetch_one("help_stats", {
        "guild_id": guild_id,
        "command_name": command_name
    })

    if not row:

        db.insert("help_stats", {
            "guild_id": guild_id,
            "command_name": command_name,
            "usage_count": 1
        })

    else:

        db.update("help_stats",
                  {"usage_count": row["usage_count"] + 1},
                  {
                      "guild_id": guild_id,
                      "command_name": command_name
                  })


# ==========================================================
# GET POPULAR COMMANDS
# ==========================================================

def get_popular_commands(guild_id, limit=5):

    rows = db.fetch_all("help_stats", {
        "guild_id": guild_id
    })

    rows = sorted(rows,
                  key=lambda x: x["usage_count"],
                  reverse=True)

    return rows[:limit]


# ==========================================================
# SMART COMMAND SUGGESTION
# Based on keyword + usage
# ==========================================================

def smart_suggest(guild_id, keyword):

    popular = get_popular_commands(guild_id)

    suggestions = []

    for row in popular:

        if keyword.lower() in row["command_name"].lower():

            suggestions.append(row["command_name"])

    return suggestions


# ==========================================================
# HELP ANALYTICS EMBED
# ==========================================================

@tree.command(
    name="help_stats",
    description="Show popular commands in this server"
)
async def help_stats(interaction: discord.Interaction):

    popular = get_popular_commands(interaction.guild.id)

    embed = discord.Embed(
        title="📊 Popular Commands",
        color=discord.Color.blue()
    )

    for row in popular:

        embed.add_field(
            name=row["command_name"],
            value=f"Used {row['usage_count']} times",
            inline=False
        )

    await interaction.response.send_message(embed=embed)
# ==========================================================
# PHASE 13 – PRODUCTION ENGINE
# AUTO RECOVERY + HEALTH CHECK + BACKUP + CRASH HANDLING
# ==========================================================

import traceback
import sys
import platform

# ==========================================================
# CRASH LOGGER
# Logs unexpected errors into database
# ==========================================================

def log_crash(error: str):

    db.insert("enterprise_crash_logs", {
        "error": error,
        "timestamp": datetime.utcnow().isoformat(),
        "system": platform.system(),
        "python_version": sys.version
    })


# ==========================================================
# GLOBAL ERROR HANDLER
# Catches unhandled exceptions
# ==========================================================

@bot.event
async def on_error(event, *args, **kwargs):

    error = traceback.format_exc()

    print("🚨 CRITICAL ERROR DETECTED")
    print(error)

    log_crash(error)


# ==========================================================
# COMMAND ERROR HANDLER
# Logs command-level errors
# ==========================================================

@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error):

    error_trace = traceback.format_exception(type(error), error, error.__traceback__)

    log_crash("".join(error_trace))

    await interaction.response.send_message(
        "❌ Something went wrong. The error has been logged.",
        ephemeral=True
    )


# ==========================================================
# HEALTH CHECK ENGINE
# Runs system diagnostics every 5 minutes
# ==========================================================

async def health_monitor():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            process = psutil.Process(os.getpid())

            memory = round(process.memory_info().rss / 1024 ** 2, 2)
            cpu = process.cpu_percent()

            db.insert("enterprise_health", {
                "guild_count": len(bot.guilds),
                "memory_mb": memory,
                "cpu_percent": cpu,
                "latency": round(bot.latency * 1000, 2),
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            log_crash(str(e))

        await asyncio.sleep(300)


bot.loop.create_task(health_monitor())


# ==========================================================
# AUTO BACKUP SYSTEM
# Backups system configuration daily
# ==========================================================

async def auto_backup():

    await bot.wait_until_ready()

    while not bot.is_closed():

        try:

            backup_data = {

                "guilds": [g.id for g in bot.guilds],
                "timestamp": datetime.utcnow().isoformat()
            }

            db.insert("enterprise_backups", backup_data)

        except Exception as e:
            log_crash(str(e))

        await asyncio.sleep(86400)  # 24 hours


bot.loop.create_task(auto_backup())


# ==========================================================
# SYSTEM STATUS COMMAND
# Shows production health metrics
# ==========================================================

@tree.command(
    name="system_status",
    description="Show production system status"
)
async def system_status(interaction: discord.Interaction):

    process = psutil.Process(os.getpid())

    memory = round(process.memory_info().rss / 1024 ** 2, 2)
    cpu = process.cpu_percent()

    embed = discord.Embed(
        title="🚀 Production System Status",
        color=discord.Color.green()
    )

    embed.add_field(name="Guilds", value=len(bot.guilds))
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000, 2)} ms")
    embed.add_field(name="CPU", value=f"{cpu}%")
    embed.add_field(name="Memory", value=f"{memory} MB")

    await interaction.response.send_message(embed=embed)

bot.run(DISCORD_TOKEN)
