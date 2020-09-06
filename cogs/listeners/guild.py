import copy, discord, json, humanize, aiohttp, traceback, typing, time

from datetime import datetime
from discord.ext import commands
from textwrap import shorten
from discord.ext import menus

from cogs.consts import *

class NotLogging:
    def __init__(self, etype, reason, details="No Further Info", *, cog, guild):
        self.etype = etype
        self.reason = reason
        self.details = details
        if cog and guild:
            cog.bot.loop.create_task(cog.vbl(guild, self))
        else:
            self.cog = None
            self.guild = None

    def __str__(self):
        return f"Not logging event \"{self.etype}\" for reason: {self.reason}. See extra details in __repr__."""

    def __repr__(self):
        return f"NotLogging(etype={self.etype} reason={self.reason} details={self.details})"

    def __bool__(self):
        return False

async def get_alog_entry(ctx, *, type: discord.AuditLogAction, check = None):
    """Retrieves the first matching audit log entry for the specified type.
    
    If you provide a check it MUST take an auditLogEntry as its only argument."""
    if not ctx.guild.me.guild_permissions.view_audit_log:
        raise commands.BotMissingPermissions("view_audit_log")
    async for log in ctx.guild.audit_logs(action=type):
        if check:
            if check(log):
                return log
            else:
                continue
        else:
            return log
    else:
        return None


class Guild(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open("./data/core.json") as rfile: self.data = json.load(rfile)
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))
    
    def cog_unload(self): 
        with open("./data/core.json", "w") as wfile: json.dump(self.data, wfile, indent=2)
        self.bot.loop.create_task(self.session.close())

    def is_logging(self, guild: discord.Guild, *, channel = None, member: discord.Member = None, eventname):
        if eventname not in events.keys():  # invalid event name
            return bool(NotLogging(eventname, "Event Name is not in registered events.", cog=self, guild=guild))
        if not guild:  # in DMs
            return bool(NotLogging(eventname, "Event occurred in DMs, thus has no targeted channel.", cog=self, guild=guild))
        if not self.data.get(str(guild.id)):
            return bool(NotLogging(eventname, "The guild where this event occured has not registered.", cog=self, guild=guild))
        
        try: entry = self.data[str(guild.id)]
        except: 
            json.dump(f"{guild.id}: {template}", open(f"data/core.json", "w+"), indent=2)
            entry = self.data[str(guild.id)]
        if member:
            if member.bot and entry["ignoreBots"] is True:
                return bool(NotLogging(eventname, f"You are ignoring bots.", cog=self, guild=guild))
            if member.id in entry["ignoredMembers"]:
                return bool(NotLogging(eventname, f"Member \"{member}\" is being ignored.", cog=self, guild=guild))
            if member == self.bot.user:
                return bool(NotLogging(eventname, f"Not logging bot actions", cog=self, guild=guild))
            
        if channel:
            if channel.id in entry["ignoredChannels"]:
                return bool(NotLogging(eventname, f"Channel \"{channel}\" is being ignored.", cog=self, guild=guild))
            if channel.id == entry["logChannel"]:
                return bool(NotLogging(eventname, f"This is the log channel.", cog=self, guild=guild))
        if eventname.lower() not in entry["toLog"]:
            return bool(NotLogging(eventname, f"Guild is ignoring event \"{eventname}\".", cog=self, guild=guild))
        return True
        
    def get_log(self, guild: discord.Guild): 
        return self.bot.get_channel(self.data[str(guild.id)]["logChannel"])

    async def vbl(self, guild, e: NotLogging):
        """VerboseLog: Log NotLogging events if verbose is enabled"""
        if not self.data[str(guild.id)]["verbose"]: return False
        # print(f"Not logging event {e.etype}:\n> {e.reason}\n\n> {e.details}")
        return True 
    
    async def log(self, logType:str, guild:int, occurredAt:int, content:dict):
        try: data = json.load(open(f"data/guilds/{guild}.json", 'r'))
        except Exception as e: data = {}
        logID = len(data)
        data[str(logID)] = {"logType": logType, "occurredAt": occurredAt, "content": content}
        try: json.dump(data, open(f"data/guilds/{guild}.json", "w+"), indent=2)
        except Exception as e: print(e)
    

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        self.guild = after
        if (before.name != after.name) and self.is_logging(after, eventname="name_changed"):
            audit = await get_alog_entry(self, type=discord.AuditLogAction.guild_update)
            log = self.get_log(before)
            e = discord.Embed(
                title=emojis['name_change'] + " Server Name Changed",
                description=f"**Before:** {discord.utils.escape_markdown(before.name)}\n"
                            f"**After:** {discord.utils.escape_markdown(after.name)}\n"
                            f"**By:** {audit.user.mention}",
                color=events["name_changed"][0],
                timestamp=datetime.utcnow()
            )
            await log.send(embed=e)
            return await self.log(
                logType="nameUpdate", 
                occurredAt=round(time.time()),
                guild=before.id,
                content={
                    "username": audit.user.id,
                    "was": discord.utils.escape_markdown(before.name),
                    "now": discord.utils.escape_markdown(after.name)
                }
            )
        if (before.verification_level.name != after.verification_level.name) and self.is_logging(after, eventname="mod_changed"):
            audit = await get_alog_entry(self, type=discord.AuditLogAction.guild_update)
            log = self.get_log(before)
            e = discord.Embed(
                title=emojis['mod_update'] + " Server Verification Level Changed",
                description=f"**Before:** {before.verification_level.name.capitalize()}\n"
                            f"**After:** {after.verification_level.name.capitalize()}\n"
                            f"**By:** {audit.user.mention}",
                color=events["name_changed"][0],
                timestamp=datetime.utcnow()
            )
            await log.send(embed=e)
            return await self.log(
                logType="verificationUpdate", 
                occurredAt=round(time.time()),
                guild=before.id,
                content={
                    "username": audit.user.id,
                    "was": before.verification_level.name.capitalize(),
                    "now": after.verification_level.name.capitalize()
                }
            )
        if (before.icon_url != after.icon_url) and self.is_logging(after, eventname="icon_update"):
            audit = await get_alog_entry(self, type=discord.AuditLogAction.guild_update)
            log = self.get_log(before)
            e = discord.Embed(
                title=emojis['icon_update'] + " Server Icon Changed",
                description=f"**Before:** [Click Here]({before.icon_url})\n"
                            f"**After:** [Click here]({after.icon_url})\n"
                            f"**By:** {audit.user.mention}",
                color=events["icon_update"][0],
                timestamp=datetime.utcnow()
            )
            await log.send(embed=e)
            return await self.log(
                logType="iconUpdate", 
                occurredAt=round(time.time()),
                guild=before.id,
                content={
                    "username": audit.user.id,
                    "was": before.icon_url,
                    "now": after.icon_url
                }
            )
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel): 
        if not self.is_logging(channel.guild, channel=channel, member=None, eventname="channel_create"): return
        else:
            audit = await get_alog_entry(channel, type=discord.AuditLogAction.channel_create)
            log = self.get_log(channel.guild)
            c_type = str(channel.type).split('.')[-1]
            e = discord.Embed(
                title=emojis["voice_create" if c_type == "voice" else "store_create" if c_type == "store" else "channel_create"] + " Channel Created",
                description=f"**Channel:**: {channel.mention}\n"
                            f"**Category**: {channel.category.name}\n"
                            f"**Created By:** {emojis[audit.user.status.value]} {audit.user.mention}\n",
                color=events["channel_create"][0],
                timestamp=datetime.utcnow()
            ) 
            await log.send(embed=e)
            return await self.log(
                logType="channelCreate", 
                occurredAt=round(time.time()),
                guild=channel.guild.id,
                content={
                    "username": audit.user.id,
                    "channel": channel.id,
                    "category": channel.category.id, 
                    "type": c_type
                }
            )
    
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel): 
        if not self.is_logging(channel.guild, channel=channel, member=None, eventname="webhook_create"): return
        else:
            auditCreate = await get_alog_entry(channel, type=discord.AuditLogAction.webhook_create)
            auditUpdate = await get_alog_entry(channel, type=discord.AuditLogAction.webhook_update)
            auditDelete = await get_alog_entry(channel, type=discord.AuditLogAction.webhook_delete)
            if   auditCreate.created_at > max(auditUpdate.created_at, auditDelete.created_at): audit = auditCreate; t = "create"
            elif auditUpdate.created_at > max(auditCreate.created_at, auditDelete.created_at): audit = auditUpdate; t = "update"
            elif auditDelete.created_at > max(auditUpdate.created_at, auditCreate.created_at): audit = auditDelete; t = "delete"
            else: return

            log = self.get_log(channel.guild)
            c_type = str(channel.type).split('.')[-1]
            if t == 'create':
                e = discord.Embed(
                    title=emojis["webhook_create"] + f" Webhook Created",
                    description=f"**Created By:** {emojis[audit.user.status.value]} {audit.user.mention}\n",
                    color=colours[t],
                    timestamp=datetime.utcnow()
                ) 
                await log.send(embed=e)
                return await self.log(
                    logType="webhookCreate", 
                    occurredAt=round(time.time()),
                    guild=channel.guild.id,
                    content={
                        "username": audit.user.id
                    }
                )
            elif t == 'update':
                before, after = audit.before, audit.after
                e = discord.Embed(
                    title=emojis["webhook_update"] + f" Webhook Updated",
                    description=f"**Edited By:** {emojis[audit.user.status.value]} {audit.user.mention}\n" +
                                f"**Changes:**\n" +
                                (f"{before.channel.mention} -> {after.channel.mention}\n" if before.channel != after.channel else "") +
                                (f"{before.name}` -> `{after.name}`\n" if before.name != after.name else "") +
                                (f"[Image before](https://cdn.discordapp.com/avatars/{audit.target.id}/{before.avatar}) -> [Image after](https://cdn.discordapp.com/avatars/{audit.target.id}/{after.avatar})\n" if before.avatar != after.avatar else ""),
                    color=colours[t],
                    timestamp=datetime.utcnow()
                ) 
                await log.send(embed=e)
                return await self.log(
                    logType="webhookUpdate", 
                    occurredAt=round(time.time()),
                    guild=channel.guild.id,
                    content={
                        "username":      audit.user.id,
                        "beforeChannel": before.channel.id,
                        "afterChannel":  after.channel.id,
                        "beforeName":    before.name,
                        "afterName":     after.name,
                        "beforeAvatar":  f"https://cdn.discordapp.com/avatars/{audit.target.id}/{before.avatar}",
                        "afterAvatar":   f"https://cdn.discordapp.com/avatars/{audit.target.id}/{after.avatar}"
                    }
                )
            elif t == 'delete':
                e = discord.Embed(
                    title=emojis["webhook_delete"] + f" Webhook Deleted",
                    description=f"**Deleted By:** {emojis[audit.user.status.value]} {audit.user.mention}\n"
                                f"**Name:** `{audit.action.name}`\n",
                    color=colours[t],
                    timestamp=datetime.utcnow()
                ) 
                await log.send(embed=e)
                return await self.log(
                    logType="webhookCreate", 
                    occurredAt=round(time.time()),
                    guild=channel.guild.id,
                    content={
                        "username": audit.user.id
                    }
                )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel): 
        if not self.is_logging(channel.guild, channel=channel, member=None, eventname="channel_delete"): return
        else:
            audit = await get_alog_entry(channel, type=discord.AuditLogAction.channel_delete)
            log = self.get_log(channel.guild)
            c_type = str(channel.type).split('.')[-1]
            e = discord.Embed(
                title=emojis["voice_delete" if c_type == "voice" else "store_delete" if c_type == "store" else "channel_delete"] + " Channel Deleted",
                description=f"**Channel deleted**: #{channel.name}\n"
                            f"**Category**: {channel.category.name}\n"
                            f"**Deleted By:** {emojis[audit.user.status.value]} {audit.user.mention}\n",
                color=events["channel_delete"][0],
                timestamp=datetime.utcnow()
            ) 
            await log.send(embed=e)
            return await self.log(
                logType="channelDelete", 
                occurredAt=round(time.time()),
                guild=channel.guild.id,
                content={
                    "username": audit.user.id,
                    "channel": channel.id,
                    "category": channel.category.id, 
                    "type": c_type
                }
            )
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if not isinstance(invite.guild, discord.Guild): return
        if not self.is_logging(invite.channel, channel=invite.channel, member=None, eventname="invite_create"): return
        else:
            log = self.get_log(invite.guild)
            e = discord.Embed(
                title=emojis["invite_create"] + " Invite Created",
                description=f"**Max Age:** {invite.max_age / 3600 if invite.max_age else 'Infinite'}\n"
                            f"**Max Uses:** {humanize.intcomma(invite.max_uses or 'infinite')}\n"
                            f"**Invite:** {invite.url}\n"
                            f"**Temporary:** {emojis['tick'] if invite.temporary else emojis['cross']}\n"
                            f"**Channel:** {invite.channel.mention}"
                            f"**Created By:** {emojis[invite.inviter.status.value]} {invite.inviter.mention}\n",
                color=events["invite_create"][0],
                timestamp=datetime.utcnow()
            )
            await log.send(embed=e)
            return await self.log(
                logType="inviteCreate", 
                occurredAt=round(time.time()),
                guild=invite.guild.id,
                content={
                    "username": invite.inviter.id,
                    "maxAge": invite.max_age / 3600 if invite.max_age else 'Infinite',
                    "maxUses": humanize.intcomma(invite.max_uses or 'infinite'),
                    "url": invite.url,
                    "temporary": 'true' if invite.temporary else 'false',
                    "channel": invite.channel.id
                }
            )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if not isinstance(invite.guild, discord.Guild): return
        if not self.is_logging(invite.guild, channel=invite.channel, member=None, eventname="invite_create"): return
        else:
            audit = await get_alog_entry(invite.channel, type=discord.AuditLogAction.invite_delete)
            log = self.get_log(invite.guild)
            e = discord.Embed(
                title=emojis["invite_delete"] + " Invite Deleted",
                description=f"**Max Age:** {invite.max_age / 3600 if invite.max_age else 'Infinite'}\n"
                            f"**Max Uses:** {humanize.intcomma(invite.max_uses or 'Infinite')}\n"
                            f"**Invite URL:** {invite.url}\n"
                            f"**Temporary:** {emojis['tick'] if invite.temporary else emojis['cross']}\n"
                            f"**Channel:** {invite.channel.mention}\n"
                            f"**Uses:** {humanize.intcomma(invite.uses)}\n"
                            f"**Deleted By:** {emojis[audit.user.status.value]} {audit.user.mention}",
                color=events["invite_delete"][0],
                timestamp=datetime.utcnow()
            )
            await log.send(embed=e)
            return await self.log(
                logType="inviteDelete", 
                occurredAt=round(time.time()),
                guild=invite.guild.id,
                content={
                    "username": invite.inviter.id,
                    "maxAge": invite.max_age / 3600 if invite.max_age else 'Infinite',
                    "maxUses": humanize.intcomma(invite.max_uses or 'infinite'),
                    "url": invite.url,
                    "temporary": 'true' if invite.temporary else 'false',
                    "channel": invite.channel.id,
                    "uses": humanize.intcomma(invite.uses)
                }
            )
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if not self.is_logging(role.guild, eventname="guild_role_create"): return
        else:
            audit = await get_alog_entry(role, type=discord.AuditLogAction.role_create)
            e = discord.Embed(
                title=emojis["role_create"] + f" Role Created",
                description=f"**Name:** {role.name}\n"
                            f"**ID:** `{role.id}`\n"
                            f"**Created By:** {audit.user.mention}",
                color=events["guild_role_create"][0], 
                timestamp=datetime.utcnow()
            )
            log = self.get_log(role.guild)
            await log.send(embed=e)
            return await self.log(
                logType="roleCreate", 
                occurredAt=round(time.time()),
                guild=role.guild.id,
                content={
                    "username": audit.user.id,
                    "name": role.name,
                    "id": role.id
                }
            )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        if not self.is_logging(role.guild, eventname="guild_role_create"): return
        else:
            audit = await get_alog_entry(role, type=discord.AuditLogAction.role_delete)
            dapi = f"https://discordapi.com/permissions.html#{role.permissions.value}"
            e = discord.Embed(
                title=emojis["role_delete"] + f" Role Deleted",
                description=f"**Name:** {role.name}\n"
                            f"**Permissions:** [Click here]({dapi})\n"
                            f"**Colour:** {role.color}\n"
                            f"**Position:** {role.position}\n"
                            f"**ID:** `{role.id}`\n**Hoisted:** {'yes' if role.hoist else 'No'}\n"
                            f"**Mentionable by everyone:** {'yes' if role.mentionable else 'no'}\n"
                            f"**Members:** {len(role.members)}\n"
                            f"**Created:** {humanize.naturaltime(role.created_at)}"
                            f"**Deleted By:** {audit.user.mention}",
                color=events["guild_role_delete"][0], 
                timestamp=datetime.utcnow()
            )
            log = self.get_log(role.guild)
            await log.send(embed=e)
            return await self.log(
                logType="roleDelete", 
                occurredAt=round(time.time()),
                guild=role.guild.id,
                content={
                    "username": audit.user.id,
                    "name": role.name,
                    "id": role.id,
                    "permissions": dapi,
                    "colour": role.colour,
                    "position": role.position,
                    "mentionableByEveryone": 'true' if role.mentionable else 'false',
                    "members": len(role.members),
                    "created": humanize.naturaltime(role.created_at)
                }
            )
    
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        audit = await get_alog_entry(after, type=discord.AuditLogAction.channel_update)
        if (before.is_nsfw() != after.is_nsfw()) and self.is_logging(after.guild, eventname="nsfw_update"):
            audit = await get_alog_entry(after, type=discord.AuditLogAction.channel_update)
            now = after.is_nsfw() > before.is_nsfw() # If the channel is now nsfw
            e = discord.Embed(
                title=emojis["nsfw_on" if now else "nsfw_off"] + f" Channel is {'now' if now else 'no longer'} NSFW",
                description=f"**Channel:** {after.mention}\n"
                            f"**Changed by:** {audit.user.mention}",
                color=events["nsfw_update"][0],
                timestamp=datetime.utcnow()
            )
            log = self.get_log(after.guild)
            await log.send(embed=e)
            return await self.log(
                logType="nsfwUpdate", 
                occurredAt=round(time.time()),
                guild=before.guild.id,
                content={
                    "username": audit.user.id,
                    "channel": after.id,
                    "was": before.is_nsfw(),
                    "now": after.is_nsfw()
                }
            )
        elif (before.name != after.name) and self.is_logging(after.guild, eventname="channel_title_update"):
            audit = await get_alog_entry(after, type=discord.AuditLogAction.channel_update)
            e = discord.Embed(
                title=emojis["TitleUpdate"] + f" Channel Renamed",
                description=f"**Before:** #{before.name}\n"
                            f"**Now:** {after.mention}\n"
                            f"**Changed by:** {audit.user.mention}",
                color=events["channel_title_update"][0],
                timestamp=datetime.utcnow()
            )
            log = self.get_log(after.guild)
            await log.send(embed=e)
            return await self.log(
                logType="titleUpdate", 
                occurredAt=round(time.time()),
                guild=before.guild.id,
                content={
                    "username": audit.user.id,
                    "channel": after.id,
                    "was": before.name,
                    "now": after.name
                }
            )
        elif (before.topic != after.topic) and self.is_logging(after.guild, eventname="channel_desc_update"):
            audit = await get_alog_entry(after, type=discord.AuditLogAction.channel_update)
            e = discord.Embed(
                title=emojis["TopicUpdate"] + f" Channel Topic Changed",
                description=f"**Before:** {before.topic}\n"
                            f"**Now:** {after.topic}\n"
                            f"**Changed by:** {audit.user.mention}",
                color=events["channel_desc_update"][0],
                timestamp=datetime.utcnow()
            )
            log = self.get_log(after.guild)
            await log.send(embed=e)
            return await self.log(
                logType="topicUpdate", 
                occurredAt=round(time.time()),
                guild=before.guild.id,
                content={
                    "username": audit.user.id,
                    "channel": after.id,
                    "was": before.topic,
                    "now": after.topic
                }
            )

def setup(bot):
    bot.add_cog(Guild(bot))