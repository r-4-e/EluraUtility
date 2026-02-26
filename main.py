# ==========================================================
# ELURA — SECTION 1
# CORE FOUNDATION & BOOTSTRAP
# ==========================================================

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

import discord
from discord import app_commands
from discord.ui import View

from supabase import create_client, Client
import google.generativeai as genai
from dotenv import load_dotenv


# ==========================================================
# 1. ENVIRONMENT VALIDATION
# ==========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials are missing.")


# ==========================================================
# 2. LOGGING CONFIGURATION (PRODUCTION SAFE)
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("Elura")


# ==========================================================
# 3. SUPABASE INITIALIZATION
# ==========================================================

class SupabaseManager:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    async def health_check(self):
        try:
            self.client.table("GUILDS").select("guild_id").limit(1).execute()
            logger.info("Supabase connection successful.")
        except Exception as e:
            logger.critical(f"Database connection failed: {e}")
            raise


db = SupabaseManager()


# ==========================================================
# 4. GEMINI AI INITIALIZATION
# ==========================================================

class GeminiManager:
    def __init__(self):
        self.enabled = False
        self.model = None

        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel("gemini-pro")
                self.enabled = True
                logger.info("Gemini AI initialized.")
            except Exception as e:
                logger.error(f"Gemini initialization failed: {e}")
                self.enabled = False


ai_engine = GeminiManager()


# ==========================================================
# 5. GLOBAL CACHE SYSTEM (MULTI-GUILD ISOLATION)
# ==========================================================

class GuildCache:
    def __init__(self):
        self.guild_configs: Dict[int, Dict[str, Any]] = {}
        self.staff_tiers: Dict[int, Dict[int, int]] = {}

    async def warm_cache(self):
        logger.info("Warming guild cache...")

        try:
            guilds = db.client.table("GUILDS").select("*").execute()
            tiers = db.client.table("STAFF_TIERS").select("*").execute()

            # Load guild configs
            for row in guilds.data:
                self.guild_configs[row["guild_id"]] = row

            # Load staff tiers
            for row in tiers.data:
                guild_id = row["guild_id"]
                role_id = row["role_id"]
                tier = row["tier_level"]

                if guild_id not in self.staff_tiers:
                    self.staff_tiers[guild_id] = {}

                self.staff_tiers[guild_id][role_id] = tier

            logger.info("Cache warmup completed.")

        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")

    def get_guild_config(self, guild_id: int):
        return self.guild_configs.get(guild_id)

    def get_guild_tiers(self, guild_id: int):
        return self.staff_tiers.get(guild_id, {})

    def refresh_guild(self, guild_id: int):
        self.guild_configs.pop(guild_id, None)
        self.staff_tiers.pop(guild_id, None)


cache = GuildCache()


# ==========================================================
# 6. BACKGROUND TASK MANAGER (RESTART SAFE)
# ==========================================================

async def expired_punishment_checker():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            expired = db.client.table("CASES") \
                .select("*") \
                .eq("active", True) \
                .lte("expires_at", now) \
                .execute()

            for case in expired.data:
                db.client.table("CASES") \
                    .update({"active": False}) \
                    .eq("case_id", case["case_id"]) \
                    .execute()

            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Expiration task error: {e}")
            await asyncio.sleep(30)


async def start_background_tasks(client: discord.Client):
    asyncio.create_task(expired_punishment_checker())


# ==========================================================
# 7. DISCORD CLIENT (SLASH ONLY, NO COGS)
# ==========================================================

intents = discord.Intents.all()

class EluraClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        logger.info("Running setup_hook...")
        await db.health_check()
        await cache.warm_cache()
        await start_background_tasks(self)
        await self.tree.sync()
        logger.info("Slash commands synced.")

    async def on_ready(self):
        logger.info(f"Elura is online as {self.user}.")


bot = EluraClient()


# ==========================================================
# 8. GLOBAL ERROR HANDLER
# ==========================================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    logger.error(f"Command error: {error}")

    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "An unexpected error occurred.",
        ephemeral=True
    )


# ==========================================================
# SECTION 2 — DATABASE LAYER (ENTERPRISE WRAPPER)
# ==========================================================

class DatabaseLayer:
    def __init__(self, supabase_manager: SupabaseManager):
        self.client = supabase_manager.client

    # ------------------------------------------------------
    # SAFE EXECUTION WRAPPER
    # ------------------------------------------------------

    def _safe(self, func):
        try:
            return func()
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            return None
    # ======================================================
    # GUILD CONFIGURATION
    # ======================================================

    async def get_guild(self, guild_id: int):
        return await self._safe(
            lambda: self.client.table("GUILDS")
            .select("*")
            .eq("guild_id", guild_id)
            .single()
            .execute()
        )

    async def create_guild_if_missing(self, guild_id: int):
        existing = await self.get_guild(guild_id)
        if existing and existing.data:
            return existing

        return await self._safe(
            lambda: self.client.table("GUILDS")
            .insert({
                "guild_id": guild_id,
                "ai_enabled": False,
                "economy_enabled": False,
                "automod_enabled": False,
                "setup_completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )

    async def update_guild_field(self, guild_id: int, field: str, value):
        return await self._safe(
            lambda: self.client.table("GUILDS")
            .update({field: value})
            .eq("guild_id", guild_id)
            .execute()
        )

    # ======================================================
    # STAFF TIERS
    # ======================================================

    async def get_staff_tiers(self, guild_id: int):
    return self._safe(
        lambda: self.client.table("STAFF_TIERS")
        .select("*")
        .eq("guild_id", guild_id)
        .execute()
    )

async def assign_staff_tier(self, guild_id: int, role_id: int, tier: int):
    return self._safe(
        lambda: self.client.table("STAFF_TIERS")
        .upsert({
            "guild_id": guild_id,
            "role_id": role_id,
            "tier_level": tier,
            "assigned_at": datetime.now(timezone.utc).isoformat()
        })
        .execute()
    )

async def remove_staff_tier(self, guild_id: int, role_id: int):
    return self._safe(
        lambda: self.client.table("STAFF_TIERS")
        .delete()
        .eq("guild_id", guild_id)
        .eq("role_id", role_id)
        .execute()
    )

    # ======================================================
    # USER MANAGEMENT
    # ======================================================

    async def ensure_user(self, guild_id: int, user_id: int):
        existing = await self._safe(
            lambda: self.client.table("USERS")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        if existing and existing.data:
            return existing

        return await self._safe(
            lambda: self.client.table("USERS")
            .insert({
                "guild_id": guild_id,
                "user_id": user_id,
                "warnings_count": 0,
                "total_cases": 0,
                "economy_balance": 0,
                "economy_xp": 0,
                "level": 1,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )

    async def update_user_field(self, guild_id: int, user_id: int, field: str, value):
        return await self._safe(
            lambda: self.client.table("USERS")
            .update({field: value})
            .eq("guild_id", guild_id)
            .eq("user_id", user_id)
            .execute()
        )

    # ======================================================
    # MODERATION CASES
    # ======================================================

    async def create_case(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        moderator_tier: int,
        action_type: str,
        reason: str,
        duration_minutes: int | None = None
    ):
        expires_at = None
        if duration_minutes:
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(minutes=duration_minutes)
            ).isoformat()

        return await self._safe(
            lambda: self.client.table("CASES")
            .insert({
                "guild_id": guild_id,
                "user_id": user_id,
                "moderator_id": moderator_id,
                "moderator_tier": moderator_tier,
                "action_type": action_type,
                "reason": reason,
                "duration_minutes": duration_minutes,
                "expires_at": expires_at,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )

    async def deactivate_case(self, case_id: int):
        return await self._safe(
            lambda: self.client.table("CASES")
            .update({"active": False})
            .eq("case_id", case_id)
            .execute()
        )

    async def get_expired_cases(self):
        now = datetime.now(timezone.utc).isoformat()
        return await self._safe(
            lambda: self.client.table("CASES")
            .select("*")
            .eq("active", True)
            .lte("expires_at", now)
            .execute()
        )

    # ======================================================
    # AUTOMOD SETTINGS
    # ======================================================

    async def get_automod(self, guild_id: int):
        return await self._safe(
            lambda: self.client.table("AUTOMOD_SETTINGS")
            .select("*")
            .eq("guild_id", guild_id)
            .single()
            .execute()
        )

    async def update_automod(self, guild_id: int, data: dict):
        return await self._safe(
            lambda: self.client.table("AUTOMOD_SETTINGS")
            .upsert({"guild_id": guild_id, **data})
            .execute()
        )

    # ======================================================
    # ECONOMY TRANSACTIONS
    # ======================================================

    async def log_transaction(
        self,
        guild_id: int,
        user_id: int,
        tx_type: str,
        amount: int
    ):
        return await self._safe(
            lambda: self.client.table("ECONOMY_TRANSACTIONS")
            .insert({
                "guild_id": guild_id,
                "user_id": user_id,
                "type": tx_type,
                "amount": amount,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )

    # ======================================================
    # AI USAGE TRACKING
    # ======================================================

    async def log_ai_usage(self, guild_id: int, user_id: int, tokens: int):
        return await self._safe(
            lambda: self.client.table("AI_USAGE")
            .upsert({
                "guild_id": guild_id,
                "user_id": user_id,
                "total_tokens": tokens,
                "last_used_at": datetime.now(timezone.utc).isoformat()
            })
            .execute()
        )


# ----------------------------------------------------------
# Instantiate Global DB Layer
# ----------------------------------------------------------

database = DatabaseLayer(db)

# ==========================================================
# SECTION 3 — ENTERPRISE TIER PERMISSION SYSTEM
# ==========================================================

from datetime import timedelta


# ==========================================================
# PERMISSION MATRIX
# ==========================================================

TIER_PERMISSIONS = {
    1: {"warn"},
    2: {"warn", "unwarn", "history", "mute"},
    3: {"warn", "unwarn", "history", "mute", "unmute", "kick"},
    4: {
        "warn", "unwarn", "history", "mute", "unmute",
        "kick", "ban", "unban", "softban",
        "massban", "masskick", "clear", "slowmode",
        "lock", "unlock", "nick",
        "role_add", "role_remove"
    }
}


# ==========================================================
# STRUCTURED PERMISSION RESULT
# ==========================================================

class PermissionResult:
    def __init__(self, allowed: bool, reason: str | None = None):
        self.allowed = allowed
        self.reason = reason


# ==========================================================
# TIER MANAGER (CACHE-FIRST + AUTO REFRESH)
# ==========================================================

class TierManager:

    async def resolve_tier(self, member: discord.Member) -> int:
        guild_id = member.guild.id

        tier_map = cache.get_guild_tiers(guild_id)

        # Cache miss → refresh from DB
        if not tier_map:
            result = await database.get_staff_tiers(guild_id)
            tier_map = {}

            if result and result.data:
                for row in result.data:
                    tier_map[row["role_id"]] = row["tier_level"]

            cache.staff_tiers[guild_id] = tier_map

        highest = 0

        # Highest tier only (no stacking)
        for role in member.roles:
            if role.id in tier_map:
                highest = max(highest, tier_map[role.id])

        return highest

    async def refresh_guild(self, guild_id: int):
        cache.staff_tiers.pop(guild_id, None)
        await self.resolve_cache_refresh(guild_id)

    async def resolve_cache_refresh(self, guild_id: int):
        result = await database.get_staff_tiers(guild_id)
        tier_map = {}

        if result and result.data:
            for row in result.data:
                tier_map[row["role_id"]] = row["tier_level"]

        cache.staff_tiers[guild_id] = tier_map


tier_manager = TierManager()


# ==========================================================
# CORE PERMISSION ENGINE
# ==========================================================

async def permission_check(
    interaction: discord.Interaction,
    action: str,
    target: discord.Member | None = None,
    require_setup: bool = True,
    require_system: str | None = None
) -> PermissionResult:

    guild = interaction.guild
    user = interaction.user

    if guild is None:
        return PermissionResult(False, "Guild-only command.")

    # Ensure guild config exists
    guild_config = cache.get_guild_config(guild.id)

    if not guild_config:
        await database.create_guild_if_missing(guild.id)
        guild_config = cache.get_guild_config(guild.id)

    # Setup enforcement
    if require_setup and not guild_config.get("setup_completed", False):
        return PermissionResult(False, "Server setup not completed.")

    # System toggle enforcement (economy, ai, automod etc)
    if require_system:
        if not guild_config.get(require_system, False):
            return PermissionResult(False, f"{require_system} is disabled.")

    # Owner override
    if user.id == guild.owner_id:
        return PermissionResult(True)

    user_tier = await tier_manager.resolve_tier(user)
    allowed = TIER_PERMISSIONS.get(user_tier, set())

    if action not in allowed:
        return PermissionResult(
            False,
            f"Your tier does not allow `{action}`."
        )

    # Target checks
    if target:

        if target.id == user.id:
            return PermissionResult(False, "You cannot punish yourself.")

        if target.id == guild.owner_id:
            return PermissionResult(False, "You cannot punish the owner.")

        # Discord role hierarchy enforcement
        if target.top_role >= user.top_role:
            return PermissionResult(
                False,
                "Role hierarchy prevents this action."
            )

        target_tier = await tier_manager.resolve_tier(target)

        # Tier 4 restriction
        if user_tier == 4 and target_tier == 4:
            return PermissionResult(
                False,
                "Tier 4 cannot punish another Tier 4."
            )

        # Prevent lower tier punishing higher tier
        if target_tier > user_tier:
            return PermissionResult(
                False,
                "You cannot punish a higher tier staff member."
            )

    return PermissionResult(True)


# ==========================================================
# DECORATOR MIDDLEWARE
# ==========================================================

def require_tier(
    action: str,
    target_param: str | None = None,
    require_setup: bool = True,
    require_system: str | None = None
):

    async def predicate(interaction: discord.Interaction):

        target = None

        if target_param:
            try:
                target = getattr(interaction.namespace, target_param)
            except AttributeError:
                target = None

        result = await permission_check(
            interaction=interaction,
            action=action,
            target=target,
            require_setup=require_setup,
            require_system=require_system
        )

        if not result.allowed:
            raise app_commands.CheckFailure(result.reason)

        return True

    return app_commands.check(predicate)

# ==========================================================
# AUTOMOD BYPASS CHECK (FOR SECTION 5)
# ==========================================================

async def is_staff_bypass(member: discord.Member) -> bool:
    tier = await tier_manager.resolve_tier(member)
    return tier >= 2  # Example: Tier 2+ bypass automod


# ==========================================================
# AUDIT HOOK (OPTIONAL LOGGING INTEGRATION)
# ==========================================================

async def log_permission_attempt(
    interaction: discord.Interaction,
    action: str,
    allowed: bool,
    reason: str | None = None
):
    logger.info(
        f"PermissionCheck | Guild:{interaction.guild.id} "
        f"User:{interaction.user.id} "
        f"Action:{action} "
        f"Allowed:{allowed} "
        f"Reason:{reason}"
    )

# ==========================================================
# SECTION 4 — FULL ENTERPRISE MODERATION SYSTEM
# ==========================================================

from datetime import timedelta
import math


# ==========================================================
# HELPER — CREATE CASE + AUTO ESCALATION
# ==========================================================

async def create_mod_case(
    interaction: discord.Interaction,
    target: discord.Member,
    action: str,
    reason: str,
    duration_minutes: int | None = None
):
    guild_id = interaction.guild.id
    moderator_tier = await tier_manager.resolve_tier(interaction.user)

    # Ensure user exists
    await database.ensure_user(guild_id, target.id)

    # Create moderation case
    await database.create_case(
        guild_id=guild_id,
        user_id=target.id,
        moderator_id=interaction.user.id,
        moderator_tier=moderator_tier,
        action_type=action,
        reason=reason,
        duration_minutes=duration_minutes
    )

    # Auto escalation example (3 warns → auto mute 10m)
    cases = database.client.table("CASES") \
        .select("*") \
        .eq("guild_id", guild_id) \
        .eq("user_id", target.id) \
        .eq("action_type", "warn") \
        .eq("active", True) \
        .execute()

    if cases.data and len(cases.data) >= 3:
        try:
            await target.timeout(timedelta(minutes=10), reason="Auto escalation (3 warns)")
        except:
            pass

    # DM user safely
    try:
        await target.send(
            f"You have been **{action}** in **{interaction.guild.name}**.\nReason: {reason}"
        )
    except:
        pass


# ==========================================================
# WARN
# ==========================================================

@bot.tree.command(name="warn")
@require_tier("warn", target_param="member")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await create_mod_case(interaction, member, "warn", reason)
    await interaction.response.send_message(
        f"{member.mention} warned.",
        ephemeral=True
    )


# ==========================================================
# UNWARN
# ==========================================================

@bot.tree.command(name="unwarn")
@require_tier("unwarn", target_param="member")
async def unwarn(interaction: discord.Interaction, member: discord.Member):
    database.client.table("CASES") \
        .update({"active": False}) \
        .eq("guild_id", interaction.guild.id) \
        .eq("user_id", member.id) \
        .eq("action_type", "warn") \
        .eq("active", True) \
        .execute()

    await interaction.response.send_message(
        f"Warnings cleared for {member.mention}.",
        ephemeral=True
    )


# ==========================================================
# HISTORY (PAGINATED BASIC)
# ==========================================================

@bot.tree.command(name="history")
@require_tier("history", target_param="member")
async def history(interaction: discord.Interaction, member: discord.Member):

    result = database.client.table("CASES") \
        .select("*") \
        .eq("guild_id", interaction.guild.id) \
        .eq("user_id", member.id) \
        .execute()

    data = result.data or []

    if not data:
        await interaction.response.send_message("No cases found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Case History — {member}",
        color=discord.Color.orange()
    )

    for case in data[:5]:
        embed.add_field(
            name=f"{case['action_type']} | ID {case['case_id']}",
            value=case["reason"],
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==========================================================
# TIMEOUT / UNTIMEOUT
# ==========================================================

@bot.tree.command(name="timeout")
@require_tier("mute", target_param="member")
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str
):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await create_mod_case(interaction, member, "timeout", reason, minutes)
    await interaction.response.send_message(
        f"{member.mention} timed out for {minutes} minutes.",
        ephemeral=True
    )


@bot.tree.command(name="untimeout")
@require_tier("unmute", target_param="member")
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(
        f"{member.mention} timeout removed.",
        ephemeral=True
    )


# ==========================================================
# KICK
# ==========================================================

@bot.tree.command(name="kick")
@require_tier("kick", target_param="member")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str):
    await member.kick(reason=reason)
    await create_mod_case(interaction, member, "kick", reason)
    await interaction.response.send_message(
        f"{member.mention} kicked.",
        ephemeral=True
    )


# ==========================================================
# BAN / UNBAN / SOFTBAN
# ==========================================================

@bot.tree.command(name="ban")
@require_tier("ban", target_param="member")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.guild.ban(member, reason=reason)
    await create_mod_case(interaction, member, "ban", reason)
    await interaction.response.send_message("User banned.", ephemeral=True)


@bot.tree.command(name="softban")
@require_tier("softban", target_param="member")
async def softban(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.guild.ban(member, reason=reason, delete_message_days=1)
    await interaction.guild.unban(member)
    await create_mod_case(interaction, member, "softban", reason)
    await interaction.response.send_message("User softbanned.", ephemeral=True)


@bot.tree.command(name="unban")
@require_tier("unban")
async def unban(interaction: discord.Interaction, user_id: int):
    user = await bot.fetch_user(user_id)
    await interaction.guild.unban(user)
    await interaction.response.send_message("User unbanned.", ephemeral=True)


# ==========================================================
# MASSBAN / MASSKICK
# ==========================================================

@bot.tree.command(name="massban")
@require_tier("massban")
async def massban(interaction: discord.Interaction, user_ids: str, reason: str):
    ids = [int(x.strip()) for x in user_ids.split(",")]

    for uid in ids:
        try:
            user = await bot.fetch_user(uid)
            await interaction.guild.ban(user, reason=reason)
        except:
            continue

    await interaction.response.send_message("Mass ban completed.", ephemeral=True)


@bot.tree.command(name="masskick")
@require_tier("masskick")
async def masskick(interaction: discord.Interaction, members: str, reason: str):
    ids = [int(x.strip()) for x in members.split(",")]

    for uid in ids:
        member = interaction.guild.get_member(uid)
        if member:
            try:
                await member.kick(reason=reason)
            except:
                continue

    await interaction.response.send_message("Mass kick completed.", ephemeral=True)


# ==========================================================
# CHANNEL CONTROLS
# ==========================================================

@bot.tree.command(name="lock")
@require_tier("lock")
async def lock(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )
    await interaction.response.send_message("Channel locked.", ephemeral=True)


@bot.tree.command(name="unlock")
@require_tier("unlock")
async def unlock(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )
    await interaction.response.send_message("Channel unlocked.", ephemeral=True)


@bot.tree.command(name="slowmode")
@require_tier("slowmode")
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(
        f"Slowmode set to {seconds}s.",
        ephemeral=True
    )


# ==========================================================
# NICK CHANGE
# ==========================================================

@bot.tree.command(name="nick")
@require_tier("nick", target_param="member")
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message("Nickname changed.", ephemeral=True)


# ==========================================================
# ROLE ADD / REMOVE
# ==========================================================

@bot.tree.command(name="role_add")
@require_tier("role_add", target_param="member")
async def role_add(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message("Role added.", ephemeral=True)


@bot.tree.command(name="role_remove")
@require_tier("role_remove", target_param="member")
async def role_remove(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message("Role removed.", ephemeral=True)


# ==========================================================
# CLEAR MESSAGES
# ==========================================================

@bot.tree.command(name="clear")
@require_tier("clear")
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(
        f"{amount} messages deleted.",
        ephemeral=True
    )

# ==========================================================
# SECTION 5 — ENTERPRISE AUTOMOD ENGINE (PRODUCTION SCALE)
# ==========================================================

import re
import time
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# ==========================================================
# GLOBAL AUTOMOD CONSTANTS
# ==========================================================

INVITE_REGEX = r"(discord\.gg\/|discord\.com\/invite\/)"
URL_REGEX = r"https?:\/\/[^\s]+"
TOKEN_SPAM_REGEX = r"(free nitro|steam gift|airdrop|@everyone)"

DEFAULT_STRIKE_DECAY_MINUTES = 60
DEFAULT_ESCALATION = {
    1: {"action": "warn"},
    2: {"action": "timeout", "duration": 300},
    3: {"action": "timeout", "duration": 1800},
    4: {"action": "kick"},
    5: {"action": "ban"}
}

# ==========================================================
# RUNTIME MEMORY STRUCTURES
# ==========================================================

class RuntimeState:
    def __init__(self):
        self.message_burst: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=15))
        self.duplicate_cache: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=6))
        self.strike_counts: Dict[tuple, int] = defaultdict(int)
        self.last_message_time: Dict[tuple, float] = {}
        self.join_burst: Dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
        self.raid_mode: Dict[int, bool] = defaultdict(bool)
        self.cooldowns: Dict[tuple, float] = {}
        self.shadow_muted: Dict[tuple, bool] = defaultdict(bool)

runtime = RuntimeState()

# ==========================================================
# AUTOMOD CONFIG MANAGER
# ==========================================================

class AutomodManager:

    def __init__(self):
        self.cache: Dict[int, dict] = {}

    async def load_guild(self, guild_id: int):
        result = database.client.table("AUTOMOD_SETTINGS") \
            .select("*") \
            .eq("guild_id", guild_id) \
            .execute()

        if result.data:
            self.cache[guild_id] = result.data[0]
        else:
            self.cache[guild_id] = self.default_config()

    def default_config(self):
        return {
            "enabled": True,
            "anti_spam": True,
            "anti_duplicate": True,
            "anti_invite": True,
            "anti_links": False,
            "anti_caps": True,
            "anti_mentions": True,
            "anti_emoji": True,
            "anti_token_spam": True,
            "anti_profanity": True,
            "ai_filter": False,
            "raid_detection": True,
            "join_burst_limit": 5,
            "spam_threshold": 6,
            "spam_interval": 5,
            "duplicate_threshold": 3,
            "caps_ratio": 0.7,
            "emoji_threshold": 10,
            "strike_decay_minutes": DEFAULT_STRIKE_DECAY_MINUTES,
            "whitelist_roles": [],
            "whitelist_channels": [],
            "log_channel": None
        }

    def get(self, guild_id: int):
        return self.cache.get(guild_id, self.default_config())

automod = AutomodManager()

# ==========================================================
# STRIKE SYSTEM WITH DECAY
# ==========================================================

async def add_strike(guild_id: int, user_id: int):
    runtime.strike_counts[(guild_id, user_id)] += 1

    # Persist strike
    database.client.table("AUTOMOD_STRIKES").upsert({
        "guild_id": guild_id,
        "user_id": user_id,
        "strikes": runtime.strike_counts[(guild_id, user_id)],
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).execute()

async def decay_strikes_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await asyncio.sleep(300)

        for (guild_id, user_id), strikes in list(runtime.strike_counts.items()):
            config = automod.get(guild_id)
            decay_time = config.get("strike_decay_minutes", 60)

            runtime.strike_counts[(guild_id, user_id)] = max(0, strikes - 1)

# Background task
bot.loop.create_task(decay_strikes_loop())

# ==========================================================
# ESCALATION ENGINE
# ==========================================================

async def escalate(member: discord.Member, strike_level: int, reason: str):

    guild_id = member.guild.id
    config = automod.get(guild_id)

    rule = DEFAULT_ESCALATION.get(strike_level, DEFAULT_ESCALATION[5])

    try:
        if rule["action"] == "warn":
            await member.send(f"Warning: {reason}")

        elif rule["action"] == "timeout":
            await member.timeout(
                timedelta(seconds=rule["duration"]),
                reason="Automod escalation"
            )

        elif rule["action"] == "kick":
            await member.kick(reason="Automod escalation")

        elif rule["action"] == "ban":
            await member.guild.ban(member, reason="Automod escalation")

    except:
        pass

# ==========================================================
# MESSAGE ANALYSIS FUNCTIONS
# ==========================================================

def check_caps(content: str, ratio: float):
    if len(content) < 10:
        return False
    uppercase = sum(1 for c in content if c.isupper())
    return (uppercase / len(content)) >= ratio

def check_emojis(content: str, threshold: int):
    emojis = re.findall(r"[^\w\s,]", content)
    return len(emojis) >= threshold

def check_duplicate(key: tuple, content: str, threshold: int):
    cache = runtime.duplicate_cache[key]
    cache.append(content)
    return cache.count(content) >= threshold

def check_spam(key: tuple, interval: int, threshold: int):
    now = time.time()
    timestamps = runtime.message_burst[key]
    timestamps.append(now)
    if len(timestamps) < threshold:
        return False
    return (now - timestamps[0]) <= interval

# ==========================================================
# ADVANCED VIOLATION PROCESSOR
# ==========================================================

async def process_violation(
    message: discord.Message,
    violation_type: str,
    severity: int = 1
):
    guild_id = message.guild.id
    user_id = message.author.id
    key = (guild_id, user_id)

    # Delete message safely
    try:
        await message.delete()
    except:
        pass

    # Add weighted strikes
    for _ in range(severity):
        await add_strike(guild_id, user_id)

    strike_level = runtime.strike_counts[key]

    # Escalate
    await escalate(message.author, strike_level, violation_type)

    # Log case to DB
    await database.create_case(
        guild_id=guild_id,
        user_id=user_id,
        moderator_id=0,
        moderator_tier=0,
        action_type="automod",
        reason=f"{violation_type} | Strikes: {strike_level}",
        duration_minutes=None
    )

    # Log to mod channel
    config = automod.get(guild_id)
    log_channel_id = config.get("log_channel")

    if log_channel_id:
        channel = message.guild.get_channel(log_channel_id)
        if channel:
            embed = discord.Embed(
                title="Automod Violation",
                description=f"{message.author.mention}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Type", value=violation_type)
            embed.add_field(name="Strike Level", value=str(strike_level))
            embed.add_field(name="Channel", value=message.channel.mention)
            await channel.send(embed=embed)


# ==========================================================
# SHADOW MUTE SYSTEM
# ==========================================================

async def apply_shadow_mute(member: discord.Member):
    runtime.shadow_muted[(member.guild.id, member.id)] = True


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):

    if after.author.bot or not after.guild:
        return

    config = automod.get(after.guild.id)

    if not config.get("enabled", True):
        return

    # Re-run same checks
    await on_message(after)


# ==========================================================
# MAIN MESSAGE PIPELINE (FULL ENGINE)
# ==========================================================

@bot.event
async def on_message(message: discord.Message):

    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    user_id = message.author.id
    key = (guild_id, user_id)

    config = automod.get(guild_id)

    if not config.get("enabled", True):
        return

    # Whitelist channels
    if message.channel.id in config.get("whitelist_channels", []):
        return

    # Whitelist roles
    if any(role.id in config.get("whitelist_roles", []) for role in message.author.roles):
        return

    # Shadow mute
    if runtime.shadow_muted[key]:
        try:
            await message.delete()
        except:
            pass
        return

    score = 0

    # Spam
    if config["anti_spam"]:
        if check_spam(key, config["spam_interval"], config["spam_threshold"]):
            score += 2

    # Duplicate
    if config["anti_duplicate"]:
        if check_duplicate(key, message.content, config["duplicate_threshold"]):
            score += 2

    # Invite
    if config["anti_invite"] and re.search(INVITE_REGEX, message.content):
        score += 3

    # Links
    if config["anti_links"] and re.search(URL_REGEX, message.content):
        score += 2

    # Token spam
    if config["anti_token_spam"] and re.search(TOKEN_SPAM_REGEX, message.content.lower()):
        score += 4

    # Caps
    if config["anti_caps"]:
        if check_caps(message.content, config["caps_ratio"]):
            score += 1

    # Emoji
    if config["anti_emoji"]:
        if check_emojis(message.content, config["emoji_threshold"]):
            score += 1

    # Profanity (DB list)
    if config["anti_profanity"]:
        banned = config.get("banned_words", [])
        if any(word.lower() in message.content.lower() for word in banned):
            score += 2

    # AI Toxicity
    if config["ai_filter"]:
        try:
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content(
                f"Rate toxicity 0-10 only number.\nMessage: {message.content}"
            )
            toxicity_score = int(re.findall(r"\d+", response.text)[0])
            score += toxicity_score // 3
        except:
            pass

    # Attachment scanner
    if message.attachments:
        for attachment in message.attachments:
            if attachment.filename.endswith((".exe", ".bat", ".scr", ".js")):
                score += 4

    # Final decision
    if score >= 3:
        await process_violation(message, "Automod Violation", severity=score // 2)
        return

    await bot.process_commands(message)


# ==========================================================
# RAID DETECTION (JOIN BURST)
# ==========================================================

@bot.event
async def on_member_join(member: discord.Member):

    guild_id = member.guild.id
    config = automod.get(guild_id)

    if not config.get("raid_detection", True):
        return

    joins = runtime.join_burst[guild_id]
    now = time.time()
    joins.append(now)

    if len(joins) >= config["join_burst_limit"]:
        if (now - joins[0]) < 10:
            runtime.raid_mode[guild_id] = True

            # Lock all channels
            for channel in member.guild.text_channels:
                overwrite = channel.overwrites_for(member.guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(member.guild.default_role, overwrite=overwrite)


# ==========================================================
# USERNAME FILTER
# ==========================================================

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):

    banned_patterns = ["discord.gg", "nitro", "airdrop"]

    for pattern in banned_patterns:
        if pattern in after.display_name.lower():
            try:
                await after.edit(nick="Filtered Username")
            except:
                pass


# ==========================================================
# ADMIN CONFIG COMMANDS
# ==========================================================

@bot.tree.command(name="automod_toggle")
@require_tier("ban")
async def automod_toggle(interaction: discord.Interaction, state: bool):
    database.client.table("AUTOMOD_SETTINGS").upsert({
        "guild_id": interaction.guild.id,
        "enabled": state
    }).execute()

    await automod.load_guild(interaction.guild.id)

    await interaction.response.send_message(
        f"Automod set to {state}",
        ephemeral=True
    )


@bot.tree.command(name="automod_log_channel")
@require_tier("ban")
async def automod_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):

    database.client.table("AUTOMOD_SETTINGS").upsert({
        "guild_id": interaction.guild.id,
        "log_channel": channel.id
    }).execute()

    await automod.load_guild(interaction.guild.id)

    await interaction.response.send_message(
        "Log channel updated.",
        ephemeral=True
    )

# ==========================================================
# SECTION 6 — ENTERPRISE LOGGING & ANALYTICS ENGINE
# ==========================================================

from collections import defaultdict
from datetime import datetime, timezone
import asyncio

# ==========================================================
# LOG CONFIG MANAGER
# ==========================================================

class LogManager:

    def __init__(self):
        self.cache: Dict[int, dict] = {}

    async def load_guild(self, guild_id: int):
        result = database.client.table("LOG_SETTINGS") \
            .select("*") \
            .eq("guild_id", guild_id) \
            .execute()

        if result.data:
            self.cache[guild_id] = result.data[0]
        else:
            self.cache[guild_id] = {
                "modlog_channel": None,
                "automod_channel": None,
                "economy_channel": None,
                "ai_channel": None,
                "use_webhook": False,
                "webhook_url": None,
                "enabled": True
            }

    def get(self, guild_id: int):
        return self.cache.get(guild_id, {})


log_manager = LogManager()

# ==========================================================
# ANALYTICS RUNTIME TRACKERS
# ==========================================================

analytics_actions = defaultdict(int)
analytics_staff_actions = defaultdict(lambda: defaultdict(int))
analytics_daily = defaultdict(lambda: defaultdict(int))


# ==========================================================
# GENERIC EMBED BUILDER
# ==========================================================

def build_log_embed(
    title: str,
    description: str,
    color: discord.Color,
    fields: list = None
):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    if fields:
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)

    return embed


# ==========================================================
# CORE LOG DISPATCHER
# ==========================================================

async def dispatch_log(
    guild: discord.Guild,
    category: str,
    embed: discord.Embed
):
    config = log_manager.get(guild.id)

    if not config.get("enabled", True):
        return

    channel_id = config.get(f"{category}_channel")

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    try:
        await channel.send(embed=embed)
    except:
        pass


# ==========================================================
# UNIFIED MODERATION LOGGER
# ==========================================================

async def log_moderation_action(
    guild: discord.Guild,
    moderator: discord.Member,
    target_id: int,
    action: str,
    reason: str,
    case_id: int = None
):

    analytics_actions[(guild.id, action)] += 1
    analytics_staff_actions[guild.id][moderator.id] += 1
    analytics_daily[guild.id][datetime.utcnow().date()] += 1

    embed = build_log_embed(
        title="Moderation Action",
        description=f"Action: **{action.upper()}**",
        color=discord.Color.orange(),
        fields=[
            ("Moderator", moderator.mention),
            ("Target ID", str(target_id)),
            ("Reason", reason),
            ("Case ID", str(case_id) if case_id else "N/A")
        ]
    )

    await dispatch_log(guild, "modlog", embed)


# ==========================================================
# AUTOMOD LOGGER
# ==========================================================

async def log_automod_action(
    guild: discord.Guild,
    user: discord.Member,
    violation: str,
    strike_level: int
):

    embed = build_log_embed(
        title="Automod Triggered",
        description=f"{user.mention}",
        color=discord.Color.red(),
        fields=[
            ("Violation", violation),
            ("Strike Level", str(strike_level))
        ]
    )

    await dispatch_log(guild, "automod", embed)


# ==========================================================
# ECONOMY LOGGER (SECTION 7 READY)
# ==========================================================

async def log_economy_action(
    guild: discord.Guild,
    user: discord.Member,
    action: str,
    amount: int,
    balance: int
):

    embed = build_log_embed(
        title="Economy Transaction",
        description=user.mention,
        color=discord.Color.green(),
        fields=[
            ("Action", action),
            ("Amount", str(amount)),
            ("New Balance", str(balance))
        ]
    )

    await dispatch_log(guild, "economy", embed)


# ==========================================================
# AI LOGGER
# ==========================================================

async def log_ai_usage(
    guild: discord.Guild,
    user: discord.Member,
    prompt_length: int
):

    embed = build_log_embed(
        title="AI System Used",
        description=user.mention,
        color=discord.Color.blurple(),
        fields=[
            ("Prompt Length", str(prompt_length))
        ]
    )

    await dispatch_log(guild, "ai", embed)


# ==========================================================
# BACKGROUND DAILY SUMMARY TASK
# ==========================================================

async def daily_summary_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = datetime.utcnow()
        if now.hour == 0 and now.minute < 5:
            for guild in bot.guilds:
                date = now.date()
                total = analytics_daily[guild.id].get(date, 0)

                embed = build_log_embed(
                    title="Daily Moderation Summary",
                    description=f"Total actions today: {total}",
                    color=discord.Color.gold()
                )

                await dispatch_log(guild, "modlog", embed)

        await asyncio.sleep(300)


bot.loop.create_task(daily_summary_loop())


# ==========================================================
# STAFF PERFORMANCE COMMAND
# ==========================================================

@bot.tree.command(name="staff_stats")
@require_tier("history")
async def staff_stats(interaction: discord.Interaction):

    guild_id = interaction.guild.id
    staff_data = analytics_staff_actions[guild_id]

    if not staff_data:
        await interaction.response.send_message("No staff data.", ephemeral=True)
        return

    embed = build_log_embed(
        title="Staff Performance",
        description="Action counts",
        color=discord.Color.blue()
    )

    for staff_id, count in staff_data.items():
        member = interaction.guild.get_member(staff_id)
        if member:
            embed.add_field(
                name=member.display_name,
                value=str(count),
                inline=False
            )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==========================================================
# CONFIGURATION COMMANDS
# ==========================================================

@bot.tree.command(name="set_modlog")
@require_tier("ban")
async def set_modlog(interaction: discord.Interaction, channel: discord.TextChannel):

    database.client.table("LOG_SETTINGS").upsert({
        "guild_id": interaction.guild.id,
        "modlog_channel": channel.id
    }).execute()

    await log_manager.load_guild(interaction.guild.id)

    await interaction.response.send_message("Modlog channel set.", ephemeral=True)


@bot.tree.command(name="set_automod_log")
@require_tier("ban")
async def set_automod_log(interaction: discord.Interaction, channel: discord.TextChannel):

    database.client.table("LOG_SETTINGS").upsert({
        "guild_id": interaction.guild.id,
        "automod_channel": channel.id
    }).execute()

    await log_manager.load_guild(interaction.guild.id)

    await interaction.response.send_message("Automod log channel set.", ephemeral=True)


@bot.tree.command(name="set_economy_log")
@require_tier("ban")
async def set_economy_log(interaction: discord.Interaction, channel: discord.TextChannel):

    database.client.table("LOG_SETTINGS").upsert({
        "guild_id": interaction.guild.id,
        "economy_channel": channel.id
    }).execute()

    await log_manager.load_guild(interaction.guild.id)

    await interaction.response.send_message("Economy log channel set.", ephemeral=True)

# ==========================================================
# SECTION 7 — ENTERPRISE ECONOMY & GAMBLING SYSTEM
# ==========================================================

import random
from datetime import datetime, timedelta

# ==========================================================
# ECONOMY MANAGER
# ==========================================================

class EconomyManager:

    def __init__(self):
        self.cooldowns = {}

    async def ensure_wallet(self, guild_id: int, user_id: int):
        result = database.client.table("ECONOMY").select("*") \
            .eq("guild_id", guild_id) \
            .eq("user_id", user_id).execute()

        if not result.data:
            database.client.table("ECONOMY").insert({
                "guild_id": guild_id,
                "user_id": user_id,
                "wallet": 0,
                "bank": 0,
                "last_daily": None,
                "last_work": None
            }).execute()

    async def get_balance(self, guild_id: int, user_id: int):
        await self.ensure_wallet(guild_id, user_id)
        result = database.client.table("ECONOMY").select("*") \
            .eq("guild_id", guild_id) \
            .eq("user_id", user_id).execute()
        return result.data[0]

    async def update_balance(self, guild_id: int, user_id: int, wallet=None, bank=None):
        data = {}
        if wallet is not None:
            data["wallet"] = wallet
        if bank is not None:
            data["bank"] = bank

        database.client.table("ECONOMY").update(data) \
            .eq("guild_id", guild_id) \
            .eq("user_id", user_id).execute()


economy = EconomyManager()

# ==========================================================
# BALANCE
# ==========================================================

@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):

    data = await economy.get_balance(interaction.guild.id, interaction.user.id)

    embed = discord.Embed(
        title="Your Balance",
        color=discord.Color.green()
    )
    embed.add_field(name="Wallet", value=str(data["wallet"]))
    embed.add_field(name="Bank", value=str(data["bank"]))

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================================
# DAILY
# ==========================================================

@bot.tree.command(name="daily")
async def daily(interaction: discord.Interaction):

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = await economy.get_balance(guild_id, user_id)

    now = datetime.utcnow()
    last_daily = data["last_daily"]

    if last_daily:
        last_daily = datetime.fromisoformat(last_daily)
        if now - last_daily < timedelta(hours=24):
            await interaction.response.send_message(
                "You already claimed daily reward.",
                ephemeral=True
            )
            return

    reward = random.randint(200, 500)

    await economy.update_balance(
        guild_id,
        user_id,
        wallet=data["wallet"] + reward
    )

    database.client.table("ECONOMY").update({
        "last_daily": now.isoformat()
    }).eq("guild_id", guild_id).eq("user_id", user_id).execute()

    await log_economy_action(
        interaction.guild,
        interaction.user,
        "Daily Reward",
        reward,
        data["wallet"] + reward
    )

    await interaction.response.send_message(
        f"You received {reward} coins!",
        ephemeral=True
    )

# ==========================================================
# WORK
# ==========================================================

@bot.tree.command(name="work")
async def work(interaction: discord.Interaction):

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = await economy.get_balance(guild_id, user_id)

    now = datetime.utcnow()
    last_work = data["last_work"]

    if last_work:
        last_work = datetime.fromisoformat(last_work)
        if now - last_work < timedelta(minutes=30):
            await interaction.response.send_message(
                "You must wait before working again.",
                ephemeral=True
            )
            return

    earnings = random.randint(100, 300)

    await economy.update_balance(
        guild_id,
        user_id,
        wallet=data["wallet"] + earnings
    )

    database.client.table("ECONOMY").update({
        "last_work": now.isoformat()
    }).eq("guild_id", guild_id).eq("user_id", user_id).execute()

    await log_economy_action(
        interaction.guild,
        interaction.user,
        "Work",
        earnings,
        data["wallet"] + earnings
    )

    await interaction.response.send_message(
        f"You worked and earned {earnings} coins.",
        ephemeral=True
    )

# ==========================================================
# COINFLIP
# ==========================================================

@bot.tree.command(name="coinflip")
async def coinflip(interaction: discord.Interaction, amount: int, choice: str):

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = await economy.get_balance(guild_id, user_id)

    if amount <= 0 or amount > data["wallet"]:
        await interaction.response.send_message("Invalid bet.", ephemeral=True)
        return

    result = random.choice(["heads", "tails"])

    if choice.lower() == result:
        new_balance = data["wallet"] + amount
        await economy.update_balance(guild_id, user_id, wallet=new_balance)
        outcome = f"You won! Coin was {result}."
    else:
        new_balance = data["wallet"] - amount
        await economy.update_balance(guild_id, user_id, wallet=new_balance)
        outcome = f"You lost! Coin was {result}."

    await log_economy_action(
        interaction.guild,
        interaction.user,
        "Coinflip",
        amount,
        new_balance
    )

    await interaction.response.send_message(outcome, ephemeral=True)

# ==========================================================
# GAMBLE (RISK BASED)
# ==========================================================

@bot.tree.command(name="gamble")
async def gamble(interaction: discord.Interaction, amount: int):

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = await economy.get_balance(guild_id, user_id)

    if amount <= 0 or amount > data["wallet"]:
        await interaction.response.send_message("Invalid amount.", ephemeral=True)
        return

    win = random.random() < 0.45

    if win:
        new_balance = data["wallet"] + amount
        result = "You won!"
    else:
        new_balance = data["wallet"] - amount
        result = "You lost!"

    await economy.update_balance(guild_id, user_id, wallet=new_balance)

    await log_economy_action(
        interaction.guild,
        interaction.user,
        "Gamble",
        amount,
        new_balance
    )

    await interaction.response.send_message(result, ephemeral=True)

# ==========================================================
# BLACKJACK (SIMPLE VERSION)
# ==========================================================

def draw_card():
    return random.randint(1, 11)

@bot.tree.command(name="blackjack")
async def blackjack(interaction: discord.Interaction, amount: int):

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    data = await economy.get_balance(guild_id, user_id)

    if amount <= 0 or amount > data["wallet"]:
        await interaction.response.send_message("Invalid bet.", ephemeral=True)
        return

    player = draw_card() + draw_card()
    dealer = draw_card() + draw_card()

    if player > 21:
        new_balance = data["wallet"] - amount
        result = "Bust! You lost."
    elif dealer > 21 or player > dealer:
        new_balance = data["wallet"] + amount
        result = "You won!"
    elif player == dealer:
        new_balance = data["wallet"]
        result = "Push."
    else:
        new_balance = data["wallet"] - amount
        result = "Dealer wins."

    await economy.update_balance(guild_id, user_id, wallet=new_balance)

    await log_economy_action(
        interaction.guild,
        interaction.user,
        "Blackjack",
        amount,
        new_balance
    )

    await interaction.response.send_message(result, ephemeral=True)

# ==========================================================
# LEADERBOARD
# ==========================================================

@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):

    result = database.client.table("ECONOMY") \
        .select("*") \
        .eq("guild_id", interaction.guild.id) \
        .order("wallet", desc=True) \
        .limit(10).execute()

    embed = discord.Embed(
        title="Top 10 Richest",
        color=discord.Color.gold()
    )

    for idx, row in enumerate(result.data, start=1):
        member = interaction.guild.get_member(row["user_id"])
        if member:
            embed.add_field(
                name=f"{idx}. {member.display_name}",
                value=f"{row['wallet']} coins",
                inline=False
            )

    await interaction.response.send_message(embed=embed)

# ==========================================================
# SECTION 8 — AI SYSTEM + WEBHOOKER SUBSYSTEM
# ==========================================================

from collections import defaultdict
import asyncio

# ==========================================================
# SUBSYSTEM MANAGER
# ==========================================================

class SubsystemManager:

    def __init__(self):
        self.cache = {}

    async def load_guild(self, guild_id: int):
        result = database.client.table("SUBSYSTEMS") \
            .select("*") \
            .eq("guild_id", guild_id) \
            .execute()

        if result.data:
            self.cache[guild_id] = result.data[0]
        else:
            self.cache[guild_id] = {
                "ai_enabled": False,
                "webhook_enabled": False,
                "ai_channel": None,
                "ai_daily_limit": 50
            }

    def get(self, guild_id: int):
        return self.cache.get(guild_id, {})


subsystems = SubsystemManager()

# ==========================================================
# AI RUNTIME TRACKING
# ==========================================================

ai_usage_tracker = defaultdict(int)
ai_cooldowns = {}
ai_memory = defaultdict(list)


# ==========================================================
# OWNER CHECK
# ==========================================================

def owner_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            raise app_commands.CheckFailure("Only server owner can use this.")
        return True
    return app_commands.check(predicate)


# ==========================================================
# AI COMMAND
# ==========================================================

@bot.tree.command(name="ai")
async def ai_chat(interaction: discord.Interaction, prompt: str):

    guild_id = interaction.guild.id
    config = subsystems.get(guild_id)

    if not config.get("ai_enabled"):
        await interaction.response.send_message(
            "AI system is disabled.",
            ephemeral=True
        )
        return

    # Channel restriction
    if config.get("ai_channel") and interaction.channel.id != config["ai_channel"]:
        await interaction.response.send_message(
            "AI can only be used in designated channel.",
            ephemeral=True
        )
        return

    # Daily limit
    ai_usage_tracker[(guild_id, interaction.user.id)] += 1
    if ai_usage_tracker[(guild_id, interaction.user.id)] > config.get("ai_daily_limit", 50):
        await interaction.response.send_message(
            "You reached daily AI limit.",
            ephemeral=True
        )
        return

    # Cooldown
    key = (guild_id, interaction.user.id)
    if key in ai_cooldowns:
        if asyncio.get_event_loop().time() - ai_cooldowns[key] < 5:
            await interaction.response.send_message(
                "Slow down.",
                ephemeral=True
            )
            return

    ai_cooldowns[key] = asyncio.get_event_loop().time()

    await interaction.response.defer()

    try:
        model = genai.GenerativeModel("gemini-pro")

        # Context memory (last 5 messages)
        history = ai_memory[(guild_id, interaction.channel.id)][-5:]
        context_text = "\n".join(history)

        full_prompt = f"{context_text}\nUser: {prompt}"

        response = model.generate_content(full_prompt)
        reply = response.text[:2000]

        ai_memory[(guild_id, interaction.channel.id)].append(f"User: {prompt}")
        ai_memory[(guild_id, interaction.channel.id)].append(f"AI: {reply}")

        await log_ai_usage(interaction.guild, interaction.user, len(prompt))

        await interaction.followup.send(reply)

    except Exception as e:
        await interaction.followup.send("AI error occurred.")


# ==========================================================
# ENABLE / DISABLE AI (OWNER ONLY)
# ==========================================================

@bot.tree.command(name="enable_ai")
@owner_only()
async def enable_ai(interaction: discord.Interaction, state: bool):

    database.client.table("SUBSYSTEMS").upsert({
        "guild_id": interaction.guild.id,
        "ai_enabled": state
    }).execute()

    await subsystems.load_guild(interaction.guild.id)

    await interaction.response.send_message(
        f"AI system set to {state}",
        ephemeral=True
    )


@bot.tree.command(name="set_ai_channel")
@owner_only()
async def set_ai_channel(interaction: discord.Interaction, channel: discord.TextChannel):

    database.client.table("SUBSYSTEMS").upsert({
        "guild_id": interaction.guild.id,
        "ai_channel": channel.id
    }).execute()

    await subsystems.load_guild(interaction.guild.id)

    await interaction.response.send_message(
        "AI channel updated.",
        ephemeral=True
    )


# ==========================================================
# WEBHOOKER SUBSYSTEM
# ==========================================================

@bot.tree.command(name="enable_webhooker")
@owner_only()
async def enable_webhooker(interaction: discord.Interaction, state: bool):

    database.client.table("SUBSYSTEMS").upsert({
        "guild_id": interaction.guild.id,
        "webhook_enabled": state
    }).execute()

    await subsystems.load_guild(interaction.guild.id)

    await interaction.response.send_message(
        f"Webhooker system set to {state}",
        ephemeral=True
    )


# ==========================================================
# WEBHOOK SEND COMMAND
# ==========================================================

@bot.tree.command(name="webhook_send")
@require_tier("ban")
async def webhook_send(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    username: str,
    message: str
):

    guild_id = interaction.guild.id
    config = subsystems.get(guild_id)

    if not config.get("webhook_enabled"):
        await interaction.response.send_message(
            "Webhooker disabled.",
            ephemeral=True
        )
        return

    try:
        webhook = await channel.create_webhook(name="Elura Webhook")

        await webhook.send(
            content=message,
            username=username
        )

        await log_moderation_action(
            interaction.guild,
            interaction.user,
            0,
            "Webhook Send",
            f"Sent as {username}"
        )

        await interaction.response.send_message(
            "Webhook message sent.",
            ephemeral=True
        )

    except:
        await interaction.response.send_message(
            "Failed to send webhook.",
            ephemeral=True
        )

# ==========================================================
# SECTION 9 — ADVANCED RUNTIME + OWNER PANEL + OPEN PORT
# ==========================================================

import os
import asyncio
import threading
import signal
import time
import logging
from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================================
# GLOBAL RUNTIME STATE
# ==========================================================

BOT_START_TIME = datetime.now(timezone.utc)
BOT_READY = False
SHUTTING_DOWN = False

# ==========================================================
# FLASK APP (OPEN PORT FOR HOSTING)
# ==========================================================

app = Flask(__name__)

@app.route("/")
def root():
    return "Elura Multi-Server System Online"

@app.route("/health")
def health():
    return jsonify({
        "status": "ready" if BOT_READY else "starting",
        "uptime_seconds": int((datetime.now(timezone.utc) - BOT_START_TIME).total_seconds()),
        "guilds": len(bot.guilds),
        "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else None
    })

@app.route("/metrics")
def metrics():
    return jsonify({
        "guild_count": len(bot.guilds),
        "user_cache": len(bot.users),
        "shutting_down": SHUTTING_DOWN
    })

def run_web_server():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ==========================================================
# OWNER TIER CONFIGURATION PANEL (EXPANDED)
# ==========================================================

class TierSelectionView(discord.ui.View):

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=600)
        self.guild = guild

    @discord.ui.select(
        placeholder="Select Tier Level",
        options=[
            discord.SelectOption(label="Tier 1 — Warn Only", value="1"),
            discord.SelectOption(label="Tier 2 — Mute Access", value="2"),
            discord.SelectOption(label="Tier 3 — Kick Access", value="3"),
            discord.SelectOption(label="Tier 4 — Ban Access", value="4"),
        ]
    )
    async def select_tier(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.guild.owner_id:
            await interaction.response.send_message(
                "Only server owner can configure tiers.",
                ephemeral=True
            )
            return

        tier_level = int(select.values[0])

        role_options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in self.guild.roles
            if not role.is_default() and not role.managed
        ]

        view = TierRoleAssignView(self.guild, tier_level, role_options[:25])

        await interaction.response.send_message(
            f"Assign role to Tier {tier_level}",
            view=view,
            ephemeral=True
        )


class TierRoleAssignView(discord.ui.View):

    def __init__(self, guild, tier_level, role_options):
        super().__init__(timeout=600)
        self.guild = guild
        self.tier_level = tier_level

        self.role_select = discord.ui.Select(
            placeholder="Choose Role",
            options=role_options
        )

        self.add_item(self.role_select)

    @discord.ui.button(label="Save Configuration", style=discord.ButtonStyle.green)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.guild.owner_id:
            await interaction.response.send_message(
                "Only server owner can save tier config.",
                ephemeral=True
            )
            return

        role_id = int(self.role_select.values[0])

        database.client.table("STAFF_TIERS").upsert({
            "guild_id": self.guild.id,
            "role_id": role_id,
            "tier_level": self.tier_level
        }).execute()

        await tier_manager.load_guild(self.guild.id)

        await interaction.response.send_message(
            f"Tier {self.tier_level} updated.",
            ephemeral=True
        )


@bot.tree.command(name="setup_panel")
async def setup_panel(interaction: discord.Interaction):

    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(
            "Only server owner can open setup panel.",
            ephemeral=True
        )
        return

    view = TierSelectionView(interaction.guild)

    await interaction.response.send_message(
        "Elura Owner Control Panel",
        view=view,
        ephemeral=True
    )

# ==========================================================
# BACKGROUND MAINTENANCE LOOP
# ==========================================================

async def maintenance_loop():
    await bot.wait_until_ready()

    while not SHUTTING_DOWN:
        try:
            # Reset AI daily limits every 24h
            global ai_usage_tracker
            ai_usage_tracker.clear()

            # Example maintenance hook
            print("[Maintenance] AI limits reset")

            await asyncio.sleep(86400)

        except Exception as e:
            print("[Maintenance Error]", e)
            await asyncio.sleep(60)

# ==========================================================
# STARTUP PRELOAD SYSTEM
# ==========================================================

@bot.event
async def on_ready():
    global BOT_READY

    print(f"[BOOT] Logged in as {bot.user}")
    print(f"[BOOT] Loading guild caches...")

    for guild in bot.guilds:
        await tier_manager.load_guild(guild.id)
        await subsystems.load_guild(guild.id)
        await automod.load_guild(guild.id)
        await log_manager.load_guild(guild.id)

    await bot.tree.sync()

    bot.loop.create_task(maintenance_loop())

    BOT_READY = True
    print("[BOOT] All systems loaded successfully.")

# ==========================================================
# GRACEFUL SHUTDOWN HANDLER
# ==========================================================

async def shutdown():
    global SHUTTING_DOWN
    SHUTTING_DOWN = True

    print("[SYSTEM] Shutting down gracefully...")

    await bot.close()


def handle_signal(sig, frame):
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown())

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ==========================================================
# RUN WEB + BOT
# ==========================================================

if __name__ == "__main__":

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    # Start Flask server in thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    # Run bot
    bot.run(TOKEN)
