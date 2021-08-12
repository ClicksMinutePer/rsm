import asyncio
import datetime
import typing
import humanize
from collections import OrderedDict

import aiohttp
import discord
from cogs.consts import *
from cogs.handlers import Failed, Handlers
from discord.ext import commands


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emojis = Emojis
        self.colours = Cols()
        self.handlers = Handlers(self.bot)

    @commands.command()
    @commands.guild_only()
    async def purge(self, ctx, amount: typing.Optional[str]):
        try:
            amount = int(amount)
            if amount < 1:
                amount = "a"
        except ValueError:
            pass
        m = await ctx.send(embed=loading_embed)
        extra = 0

        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_messages", self.emojis().channel.purge, "purge the channel"), Failed):
            return

        if not isinstance(amount, int):
            amount = await self.handlers.intHandler(ctx, m, self.emojis().channel.purge, "Purge", "How many messages should be cleared?", default=50)
            if isinstance(amount, Failed):
                return
            extra = 1

        try:
            deleted = await ctx.channel.purge(limit=amount+2+extra, check=lambda message: not message.pinned)
            mlist = "\n\n".join([self.handlers.convertMessage(message) for message in deleted])
            async with aiohttp.ClientSession() as session:
                async with session.post('https://hastebin.com/documents', data=mlist) as r:
                    s = '"'
                    url = f'https://hastebin.com/{(await r.text()).split(s)[3]}'
            await self.handlers.sendLog(
                emoji=self.emojis().channel.purge,
                type="Messages purged",
                server=ctx.guild.id,
                colour=self.colours.red,
                data={
                    "Amount": len(deleted),
                    "Sent in": deleted[0].channel.mention,
                    "Purged by": ctx.author.mention,
                    "Purged": self.handlers.strf(datetime.datetime.utcnow()),
                    "Messages": url
                }
            )
            return await ctx.send(embed=discord.Embed(
                title=f"{self.emojis().channel.purge} Purge",
                description=f"Successfully purged {len(deleted)-2-extra} messages",
                colour=self.colours.green
            ), delete_after=10)
        except discord.errors.Forbidden:
            return await m.edit(embed=discord.Embed(
                title=f"{self.emojis().channel.purge} Purge",
                description=f"An error occurred while purging {ctx.channel.mention}",
                colour=self.colours.red
            ).set_footer(text="403 Forbidden"))

    @commands.command()
    @commands.guild_only()
    async def unban(self, ctx, member: typing.Optional[discord.User]):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "ban_members", self.emojis().member.unban, "unban someone"), Failed):
            return

        if not member:
            member = await self.handlers.memberHandler(
                ctx=ctx,
                m=m,
                emoji=str(self.emojis().member.unban),
                title="Unban",
                description="Who would you like to unban?"
            )
            if isinstance(member, Failed):
                return

        try:
            await ctx.guild.unban(member, reason="RSM Unban")
            return await m.edit(embed=discord.Embed(
                title=f"{self.emojis().member.unban} Unban",
                description=f"{member.mention} was successfully unbanned",
                colour=self.colours.green
            ))
        except discord.errors.Forbidden:
            return await m.edit(embed=discord.Embedgreen(
                title=f"{self.emojis().member.unban} Unban",
                description=f"An error occurred while unbanning {member.mention}",
                colour=self.colours.red
            ).set_footer(text="403 Forbidden"))

    async def setSlowmode(self, ctx, m, speed):
        speed = max(0, min(speed, 21600))
        await ctx.channel.edit(slowmode_delay=speed)
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().slowmode.on} Slowmode enabled" if ctx.channel.slowmode_delay else f"{self.emojis().slowmode.off} Slowmode disabled",
            description=f"Slowmode has been set to {ctx.channel.slowmode_delay}s",
            colour=self.colours.red if ctx.channel.slowmode_delay else self.colours.green
        ))

    @commands.command()
    @commands.guild_only()
    async def slowmode(self, ctx, speed: typing.Optional[str] = ""):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_channels", self.emojis().slowmode.on, "change slowmode"), Failed):
            return
        if speed.isdigit():
            await self.setSlowmode(ctx, m, int(speed))
        elif len(speed) and speed[-1] in ["s", "m", "h"]:
            match speed[-1]:
                case "s": speed = int(speed[:-1])
                case "m": speed = int(speed[:-1]) * 60
                case "h": speed = int(speed[:-1]) * 60 * 60
            await self.setSlowmode(ctx, m, speed)
        elif speed == "on":
            await self.setSlowmode(ctx, m, 10)
        elif speed == "off":
            await self.setSlowmode(ctx, m, 0)
        else:
            match ctx.channel.slowmode_delay:
                case 0: await self.setSlowmode(ctx, m, 10)
                case _: await self.setSlowmode(ctx, m, 0)

    @commands.command(aliases=["viewfrom", "serveras", "serverfrom"])
    @commands.guild_only()
    async def viewas(self, ctx, target: typing.Union[discord.Member, discord.Role, None]):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_permissions", self.emojis().channel.text.create, "view as someone else", me=False), Failed):
            return
        if not target:
            target = await self.handlers.memberHandler(ctx, m, emoji=self.emojis().channel.text.create, title="View as", description="Who would you like to view the server as?")
            if isinstance(target, Failed):
                return
        visible = {}
        if isinstance(target, discord.Member):
            for channel in ctx.guild.channels:
                if (
                    (channel.type in [discord.ChannelType.text, discord.ChannelType.store, discord.ChannelType.news] and channel.permissions_for(target).read_messages) or
                    (channel.type in [discord.ChannelType.voice, discord.ChannelType.stage_voice] and channel.permissions_for(target).connect)
                ) and (channel.type is not discord.ChannelType.category):
                    if channel.category not in visible:
                        visible[channel.category] = []
                    visible[channel.category].append(channel)
        elif isinstance(target, discord.Role):
            for channel in ctx.guild.channels:
                if (
                    (channel.type in [discord.ChannelType.text, discord.ChannelType.store] and (channel.overwrites_for(target).read_messages)) or
                    (channel.type in [discord.ChannelType.voice, discord.ChannelType.stage_voice] and (channel.overwrites_for(target).connect)) or
                    (target.permissions.administrator)
                ) and (channel.type is not discord.ChannelType.category):
                    if channel.category not in visible:
                        visible[channel.category] = []
                    visible[channel.category].append(channel)
        page = 0
        if not len(visible):
            return await m.edit(embed=discord.Embed(
                title=f"{self.emojis().channel.text.create} View as",
                description=f"*No visible channels*",
                colour=self.colours.yellow
            ))
        task = asyncio.create_task(self.handlers.reactionCollector(
            ctx,
            m,
            reactions=[
                "control.cross",
                "control.left",
                "control.right"
            ],
            collect=False
        ))
        ordered = OrderedDict(sorted(visible.items(), key=lambda x: (x[0].position if hasattr(x[0], "position") else -1) if isinstance(x, tuple) else -1))
        visible = {k: ordered[k] for k in ordered}
        for k in visible.keys():
            visible[k] = sorted(visible[k], key=lambda x: x.position if x.type.name == "text" else x.position + 50)
        while True:
            page = max(0, min(page, len(visible)-1))
            description = []
            if list(visible.keys())[page] is None:
                name = "Uncategorised"
            else:
                name = list(visible.keys())[page].name
            for channel in visible[list(visible.keys())[page]]:
                icon = ""
                match channel.type.name:
                    case "text": icon = self.emojis().icon.text_channel
                    case "voice": icon = self.emojis().icon.voice_channel
                    case "news": icon = self.emojis().icon.announcement_channel
                    case "store": icon = self.emojis().icon.store_channel
                    case "stage_voice": icon = self.emojis().icon.stage_channel
                    case _: icon = self.emojis().icon.text_channel
                description.append((icon, channel.mention))
            await m.edit(embed=discord.Embed(
                title=f"{self.emojis().channel.category.create} {name} ({page + 1}/{len(visible)})",
                description="\n".join([f"{c[0]} {c[1]}" for c in description]),
                colour=self.colours.green
            ))
            reaction = await self.handlers.reactionCollector(ctx, m, [])
            if isinstance(reaction, Failed):
                break
            match reaction.emoji.name:
                case "Left": page -= 1
                case "Right": page += 1
                case _: break
        await asyncio.sleep(0.1)
        await asyncio.wait_for(task, timeout=10)
        await m.clear_reactions()
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().channel.category.create} {name} ({page + 1}/{len(visible)})",
            description="\n".join([f"{c[0]} {c[1]}" for c in description]),
            colour=self.colours.red
        ))

    @commands.command()
    @commands.guild_only()
    async def setlog(self, ctx, channel: typing.Optional[discord.TextChannel]):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(
            ctx,
            m,
            permission="manage_guild",
            action="change the log channel",
            emoji=self.emojis().channel.text.create,
            me=False
        ), Failed):
            return

        if not channel:
            channel = await self.handlers.channelHandler(
                ctx,
                m,
                emoji=self.emojis().channel.text.create,
                title="Setlog",
                description="Where should logs be sent",
                optional=True, accepted=["text"]
            )
            if isinstance(channel, Failed):
                return

        data = self.handlers.fileManager(ctx.guild)
        if not channel:
            data["log_info"]["log_channel"] = None
        else:
            data["log_info"]["log_channel"] = channel.id
        self.handlers.fileManager(ctx.guild, action="w", data=data)
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().channel.text.create} Setlog",
            description=f"Your log channel has been set to {channel.mention if channel else 'None'}",
            colour=self.colours.green
        ))

    @commands.command()
    @commands.guild_only()
    async def stafflog(self, ctx, channel: typing.Optional[discord.TextChannel]):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(
            ctx,
            m,
            permission="manage_guild",
            action="change the staff log channel",
            emoji=self.emojis().channel.text.create,
            me=False
        ), Failed):
            return

        if not channel:
            channel = await self.handlers.channelHandler(
                ctx,
                m,
                emoji=self.emojis().channel.text.create,
                title="Stafflog",
                description="Where should logs be sent",
                optional=True, accepted=["text"]
            )
            if isinstance(channel, Failed):
                return

        data = self.handlers.fileManager(ctx.guild)
        if not channel:
            data["log_info"]["staff"] = None
        else:
            data["log_info"]["staff"] = channel.id
        self.handlers.fileManager(ctx.guild, action="w", data=data)
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().channel.text.create} Stafflog",
            description=f"Your staff log channel has been set to {channel.mention if channel else 'None'}",
            colour=self.colours.green
        ))

    @commands.command()
    @commands.guild_only()
    async def settings(self, ctx):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_guild", self.emojis().guild.settings, "view server log settings", me=False), Failed):
            return
        page = 0
        data = self.handlers.fileManager(ctx.guild)
        emojis = ["control.left", "control.right", "role.messages", "channel.text.create", "guild.settings", "member.join", "voice.connect"]
        task = asyncio.create_task(self.handlers.reactionCollector(ctx, m, reactions=emojis, collect=False))
        emojis = emojis[2:]
        while True:
            pages = [
                {
                    "name": "Messages", "logs": [
                        ("message_delete", "Message deleted"), ("message_edit", "Message edited"), ("bulk_message_delete", "Messages purged"),
                        ("channel_pins_update", "Message pinned"), ("reaction_clear", "Reactions cleared"), ("everyone_here", "@everyone or @here mentioned"),
                        ("mass_mention", "5+ mentions"), ("role_mention", "Role mentioned")
                    ]
                },
                {
                    "name": "Channels", "logs": [
                        ("channel_create", "Channel created"), ("channel_delete", "Channel deleted"), ("nsfw_update", "Channel NSFW changed"),
                        ("channel_title_update", "Channel title changed"), ("channel_desc_update", "Channel description changed"),
                        ("webhook_updated", "Webhooks updated")
                    ]
                },
                {
                    "name": "Server", "logs": [
                        ("guild_role_create", "Role created"), ("guild_role_delete", "Role deleted"), ("guild_emojis_update", "Emojis updated"),
                        ("invite_create", "Invite created"), ("invite_delete", "Invite deleted"), ("icon_update", "Server icon changed"),
                        ("mod_changed", "Server mod level changed"), ("name_changed", "Server name changed")
                    ]
                },
                {
                    "name": "Members", "logs": [
                        ("member_join", "Member joins"), ("member_leave", "Member leaves"), ("member_kick", "Member kicked"), ("member_ban", "Member banned"),
                        ("member_unban", "Member unbanned"), ("nickname_change", "Nickname changed"), ("user_role_update", "Nickname changed")
                    ]
                },
                {
                    "name": "Voice", "logs": [
                        ("connect", "Joined voice channel"), ("disconnect", "Left voice channel"), ("mute", "Member muted"), ("deafen", "Member deafened"),
                        ("unmute", "Member unmuted"), ("undeafen", "Member undeafened"), ("server_mute", "Member server muted"),
                        ("server_deafen", "Member server deafened"), ("server_unmute", "Member server unmuted"), ("server_undeafen", "Member server undeafened"),
                        ("move", "Member moved VC")
                    ]
                }
            ]
            desc = "\n".join([f"{(self.emojis().control.tick if p[0] in data['log_info']['to_log'] else self.emojis().control.cross)} {p[1]}" for p in pages[page]['logs']])
            await m.edit(embed=discord.Embed(
                title=f"{self.emojis().guild.settings} Settings",
                description=f"{self.bot.get_emoji(self.emojis(idOnly=True)(emojis[page]))} **{pages[page]['name']}**\n\n" + desc,
                colour=self.colours.green
            ))
            reaction = await self.handlers.reactionCollector(ctx, m, [], task=task)
            if isinstance(reaction, Failed):
                break
            match reaction.emoji.name:
                case "Left": page -= 1
                case "Right": page += 1
                case "MessagesRole": page = 0
                case "ChannelCreate": page = 1
                case "ServerRole": page = 2
                case "MemberJoin": page = 3
                case "Connect": page = 4
                case _: break
            page = max(0, min(page, 4))
        embed = m.embeds[0]
        embed.colour = self.colours.red
        await m.clear_reactions()
        await m.edit(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def roleall(self, ctx, role: typing.Optional[discord.Role]):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_roles", emoji=self.emojis().role.edit, action="role everyone"), Failed):
            return
        if not role:
            role = await self.handlers.roleHandler(ctx, m, emoji=self.emojis().role.edit, title="Roleall", description="What role should be given?")
            if isinstance(role, Failed):
                return
        bots = False
        members = False
        add = True
        tick = self.emojis().control.tick
        cross = self.emojis().control.cross
        task = asyncio.create_task(self.handlers.reactionCollector(
            ctx,
            m,
            reactions=["member.bot.join", "member.join", "icon.add", "control.cross", "control.tick"],
            collect=False
        ))
        apply = False
        while True:
            await m.edit(embed=discord.Embed(
                title=f"{self.emojis().role.edit} Roleall",
                description=f"Who should be affected?\n"
                            f"{self.emojis().member.bot.join} {tick if bots else cross} Bots\n"
                            f"{self.emojis().member.join} {tick if members else cross} Humans\n"
                            f"{self.emojis().icon.add} Members will {'be given' if add else f'lose'} the {role.mention} role",
                colour=self.colours.green
            ))
            reaction = await self.handlers.reactionCollector(ctx, m, [], collect=True, task=task)
            if isinstance(reaction, Failed):
                break
            match reaction.emoji.name:
                case "MemberJoin":
                    members = not members
                case "BotJoin":
                    bots = not bots
                case "add":
                    add = not add
                case "Cross":
                    break
                case "Tick":
                    apply = True
                    break
        if not apply:
            embed = m.embeds[0]
            embed.colour = self.colours.red
            await asyncio.sleep(0.1)
            await m.clear_reactions()
            return await m.edit(embed=embed)
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().icon.loading} Roleall",
            description=f"Updating roles\n\n0/{len(ctx.guild.members)} processed\nCalculating remaining time",
            colour=self.colours.green
        ))
        await m.clear_reactions()
        count = 0
        success = 0
        failed = 0
        t = datetime.datetime.utcnow()
        for member in ctx.guild.members:
            await asyncio.sleep(0.05)
            if not ((member.bot and not bots) or (not member.bot and not members)) and member in ctx.guild.members:
                if add and role.id not in [r.id for r in member.roles]:
                    try:
                        await asyncio.sleep(0.05)
                        await member.add_roles(role, reason="RSM Roleall")
                        success += 1
                    except discord.HTTPException:
                        failed += 1
                elif not add and role.id in [r.id for r in member.roles]:
                    try:
                        await asyncio.sleep(0.05)
                        await member.remove_roles(role, reason="RSM Roleall")
                        success += 1
                    except discord.HTTPException:
                        failed += 1
            if count % 10 == 9:
                av = int((datetime.datetime.utcnow() - t).total_seconds()) / count
                await m.edit(embed=discord.Embed(
                    title=f"{self.emojis().icon.loading} Roleall",
                    description=f"Updating roles\n\n{count+1}/{len(ctx.guild.members)} processed\n"
                                f"Estimated time remaining: {humanize.naturaldelta(datetime.datetime.now() + datetime.timedelta(seconds=len(ctx.guild.members) - count) * av)}",
                    colour=self.colours.green
                ))
            count += 1
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().role.edit} Roleall",
            description=f"Finished updating roles\n{success} roles updated\n{failed} roles failed",
            colour=self.colours.green
        ))

    @commands.command()
    @commands.guild_only()
    async def ignore(self, ctx):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_guild", emoji=self.emojis().role.edit, action="change ignored settings"), Failed):
            return
        while True:
            data = self.handlers.fileManager(ctx.guild)
            await m.clear_reactions()
            await m.edit(embed=discord.Embed(
                title=f"{self.emojis().channel.text.create} Ignore",
                description=f"You are ignoring the following things:\n\n"
                            f"{self.emojis().channel.text.create} **Channels:**\n> {' '.join([self.bot.get_channel(c).mention for c in data['log_info']['ignore']['channels']])}\n"
                            f"{self.emojis().role.create} **Roles:**\n> {' '.join([ctx.guild.get_role(r).mention for r in data['log_info']['ignore']['roles']])}\n"
                            f"{self.emojis().member.join} **Members:**\n> {' '.join([self.bot.get_user(m).mention for m in data['log_info']['ignore']['members']])}\n"
                            f"*Type all you wish to ignore when choosing*",
                colour=self.colours.green
            ))
            reaction = await self.handlers.reactionCollector(ctx, m, reactions=["channel.text.create", "role.create", "member.join", "control.cross"])
            if isinstance(reaction, Failed):
                break
            await asyncio.sleep(0.1)
            await m.clear_reactions()
            match reaction.emoji.name:
                case "Cross": break
                case "ChannelCreate":
                    channels = await self.handlers.channelHandler(
                        ctx,
                        m,
                        emoji=self.emojis().channel.text.create,
                        title="Ignore",
                        description="What channels should be ignored?",
                        optional=True,
                        accepted=["text", "annnouncement"],
                        multiple=True
                    )
                    if isinstance(channels, Failed):
                        continue
                    if channels:
                        channels = [c.id for c in channels]
                    else:
                        channels = []
                    data["log_info"]["ignore"]["channels"] = channels
                    self.handlers.fileManager(ctx.guild, "w", data=data)
                case "RoleCreate":
                    roles = await self.handlers.roleHandler(
                        ctx,
                        m,
                        emoji=self.emojis().role.create,
                        title="Ignore",
                        description="What roles should be ignored?",
                        optional=True,
                        multiple=True
                    )
                    if isinstance(roles, Failed):
                        continue
                    if roles:
                        roles = [r.id for r in roles]
                    else:
                        roles = []
                    data["log_info"]["ignore"]["roles"] = roles
                    self.handlers.fileManager(ctx.guild, "w", data=data)
                case "MemberJoin":
                    members = await self.handlers.memberHandler(
                        ctx,
                        m,
                        emoji=self.emojis().member.join,
                        title="Ignore",
                        description="What members should be ignored?",
                        optional=True,
                        multiple=True
                    )
                    if isinstance(members, Failed):
                        continue
                    if members:
                        members = [r.id for r in members]
                    else:
                        members = []
                    data["log_info"]["ignore"]["members"] = members
                    self.handlers.fileManager(ctx.guild, "w", data=data)
        embed = m.embeds[0]
        embed.colour = self.colours.red
        await m.edit(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def ignored(self, ctx):
        m = await ctx.send(embed=loading_embed)
        if isinstance(await self.handlers.checkPerms(ctx, m, "manage_guild", emoji=self.emojis().role.edit, action="view ignored settings"), Failed):
            return
        data = self.handlers.fileManager(ctx.guild)
        await m.edit(embed=discord.Embed(
            title=f"{self.emojis().channel.text.create} Ignored",
            description=f"You are ignoring the following things:\n\n"
                        f"{self.emojis().channel.text.create} **Channels:**\n> {' '.join([self.bot.get_channel(c).mention for c in data['log_info']['ignore']['channels']])}\n"
                        f"{self.emojis().role.create} **Roles:**\n> {' '.join([ctx.guild.get_role(r).mention for r in data['log_info']['ignore']['roles']])}\n"
                        f"{self.emojis().member.join} **Members:**\n> {' '.join([self.bot.get_user(m).mention for m in data['log_info']['ignore']['members']])}\n"
                        f"_ _",
            colour=self.colours.green
        ))

    @commands.command(aliases=["roles"])
    @commands.guild_only()
    async def role(self, ctx, target: typing.Union[discord.Role, discord.Member, None]):
        m = await ctx.send(embed=loading_embed)
        if not target:
            target = ctx.author
        if isinstance(target, discord.Member):
            guildRoles = [r.id for r in ctx.guild.roles]
            page = 0
            cut = [[]]
            for role in reversed(guildRoles[1:]):
                if len(cut[-1]) >= 10:
                    cut.append([])
                cut[-1].append(role)
            extra = []
            if not isinstance(await self.handlers.checkPerms(ctx, m, "manage_roles", "", "", edit=False), Failed):
                extra = [f"numbers.{n}.normal" for n in range(0, 10)]
            task = await self.handlers.reactionCollector(ctx, m, ["control.cross", "control.left", "control.right"] + extra, collect=False)
            targetRoles = {r: [ctx.guild.get_role(r), ctx.guild.get_role(r) in target.roles] for r in guildRoles}
            while True:
                d = []
                count = 0
                for role in cut[page]:
                    e = self.emojis().control.pill.tick if targetRoles[role][1] else self.emojis().control.pill.cross
                    n = self.emojis()(f"numbers.{count}.{'green' if targetRoles[role][1] else 'red'}")
                    d.append(f"{e}{n} {ctx.guild.get_role(role).name} ({ctx.guild.get_role(role).mention})")
                    count += 1
                await m.edit(embed=discord.Embed(
                    title=f"{self.emojis().role.create} Roles",
                    description=f"Page {page + 1} of {len(cut)}\n" +
                                ("\n".join(d)),
                    colour=self.colours.green
                ))
                reaction = await self.handlers.reactionCollector(ctx, m, task=task)
                if isinstance(reaction, Failed):
                    break
                match reaction.emoji.name:
                    case "Cross": break
                    case "Left": page -= 1
                    case "Right": page += 1
                    case _:
                        if len(reaction.emoji.name) == 2 and reaction.emoji.name[-1] == "_" and reaction.emoji.name[0].isdigit():
                            if isinstance(await self.handlers.checkPerms(ctx, m, "manage_roles", self.emojis().role.create, "edit someones roles"), Failed):
                                break
                            try:
                                toChange = cut[page][int(reaction.emoji.name[0])]
                            except IndexError:
                                continue
                            if ctx.guild.get_role(toChange).position >= ctx.me.top_role.position:
                                continue
                            try:
                                if not targetRoles[toChange][1]:
                                    await target.add_roles(ctx.guild.get_role(toChange), reason="RSM Role")
                                    targetRoles[role][1] = True
                                else:
                                    await target.remove_roles(ctx.guild.get_role(toChange), reason="RSM Role")
                                    targetRoles[role][1] = False
                            except discord.HTTPException:
                                continue
                page = max(0, min(page, len(cut) - 1))
            await asyncio.sleep(0.1)
            await m.clear_reactions()
            embed = m.embeds[0]
            embed.colour = self.colours.red
            await m.edit(embed=embed)

        elif isinstance(target, discord.Role):
            task = asyncio.create_task(self.handlers.reactionCollector(
                ctx,
                m,
                reactions=[
                    "control.cross", "control.left", "control.right",
                    "role.create", "member.join", "guild.settings",
                    "role.messages", "member.bot.join", "channel.voice.create"
                ],
                collect=False
            ))
            page = 0
            while True:
                permList = dict(target.permissions)
                page = max(0, min(page, 5))
                match page:
                    case 0:
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().role.create} Role info",
                            description=f"**Role:** {target.name} ({target.mention})\n"
                                        f"**Permissions:** [[View here]](https://discordapi.com/permissions.html#{target.permissions.value})\n"
                                        f"**Colour:** #{str(hex(target.colour.value))[2:]}\n"
                                        f"**Position:** {target.position}\n"
                                        f"**Show in member list:** {'Yes' if target.hoist else 'No'}\n"
                                        f"**Mentionable by anyone:** {'Yes' if target.mentionable else 'No'}\n"
                                        f"**Members who have this role:** {len(target.members)}\n"
                                        f"**ID:** `{target.id}`\n"
                                        f"**Created:** {self.handlers.betterDelta(target.created_at)}",
                            colour=self.colours.green
                        ))
                    case 1:
                        count = 0
                        d = f"**Role:** {target.name} ({target.mention})\n" + f"**Members with this role:** ({len(target.members)})\n> "
                        for member in target.members:
                            count += 1
                            if len(d) + len(member.mention) > 1500:
                                break
                            d += member.mention + ", "
                        if len(target.members):
                            d = d[:-2]
                        d += f" and {len(target.members) - count} more" if len(target.members) > count else ""
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().role.create} Role info",
                            description=d,
                            colour=self.colours.green
                        ))
                    case 2:
                        perms = [
                            "view_audit_log", ("view_guild_insights", "View server insights"), ("manage_guild", "Manage server"),
                            "manage_roles", "manage_channels", "manage_webhooks",
                            "manage_emojis", ("create_instant_invite", "Create invite")
                        ]
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().member.join} User info",
                            description=f"**Role:** {target.name} ({target.mention})\n"
                                        f"**Server**\n"
                                        f"{self.handlers.genPerms(perms, permList)}",
                            colour=self.colours.green
                        ))
                    case 3:
                        perms = [
                            "read_messages", "send_messages", ("send_tts_messages", "Send TTS messages"),
                            "manage_messages", "embed_links", "attach_files",
                            "read_message_history", ("mention_everyone", "Mention @everyone, @here and @roles"), ("external_emojis", "Use nitro emojis"),
                            "add_reactions"
                        ]
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().member.join} User info",
                            description=f"**Role:** {target.name} ({target.mention})\n"
                                        f"**Messages**\n"
                                        f"{self.handlers.genPerms(perms, permList)}",
                            colour=self.colours.green
                        ))
                    case 4:
                        perms = [
                            "kick_members", "ban_members",
                            "change_nickname", ("manage_nicknames", "Change other people's nicknames")
                        ]
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().member.join} User info",
                            description=f"**Role:** {target.name} ({target.mention})\n"
                                        f"**Members**\n"
                                        f"{self.handlers.genPerms(perms, permList)}",
                            colour=self.colours.green
                        ))
                    case 5:
                        perms = [
                            ("connect", "Join voice chats"), ("speak", "Talk in voice chats"), ("stream", "Stream in voice chats"),
                            ("mute_members", "Server mute members"), ("deafen_members", "Server deafen members"),
                            "move_members", ("use_voice_activation", "Use voice activity"), "priority_speaker"
                        ]
                        await m.edit(embed=discord.Embed(
                            title=f"{self.emojis().member.join} User info",
                            description=f"**Role:** {target.name} ({target.mention})\n"
                                        f"**Voice**\n"
                                        f"{self.handlers.genPerms(perms, permList)}",
                            colour=self.colours.green
                        ))
                reaction = await self.handlers.reactionCollector(
                    ctx,
                    m,
                    task=task
                )
                if isinstance(reaction, Failed):
                    break
                match reaction.emoji.name:
                    case "Left": page -= 1
                    case "Right": page += 1
                    case "RoleCreate": page = 0
                    case "MemberJoin": page = 1
                    case "ServerRole": page = 2
                    case "MessagesRole": page = 3
                    case "BotJoin": page = 4
                    case "VoiceCreate": page = 5
                    case _: break
            await asyncio.sleep(0.1)
            await m.clear_reactions()
            embed = m.embeds[0]
            embed.colour = self.colours.red
            await m.edit(embed=embed)


def setup(bot):
    bot.add_cog(Misc(bot))
