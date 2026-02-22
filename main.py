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

