import copy
import discord
import json
import humanize
import aiohttp
import traceback
import typing
import requests
import cv2
import pytesseract
import os
import random
import re
import time
import shutil

from datetime import datetime
from discord.ext import commands
from textwrap import shorten
from colorthief import ColorThief as cf

from cogs.consts import *
from config import config
deepAIkey = config.deepAIkey


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


class ImageDetect(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))

    def tohex(self, i):
        return hex(i).split('x')[-1]

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

    def is_logging(self, guild: discord.Guild, *, channel=None, member: discord.Member = None, eventname):
        if not os.path.exists(f'data/guilds/{guild.id}.json'):
            return bool(NotLogging(eventname, "Guild not configured.", cog=self, guild=guild))
        if eventname not in events.keys():
            return bool(NotLogging(eventname, "Event Name is not in registered events.", cog=self, guild=guild))
        if not guild:
            return bool(NotLogging(eventname, "Event occurred in DMs, thus has no targeted channel.", cog=self, guild=guild))

        try:
            with open(f"data/guilds/{guild.id}.json") as entry:
                entry = json.load(entry)
                if member:
                    if member.bot and entry["ignore_info"]["ignore_bots"] is True:
                        bool(NotLogging(eventname, f"You are ignoring bots.", cog=self, guild=guild))
                    if member.id in entry["ignore_info"]["members"]:
                        return bool(NotLogging(eventname, f"Member \"{member}\" is being ignored.", cog=self, guild=guild))
                    if member == self.bot.user:
                        return bool(NotLogging(eventname, f"Not logging bot actions", cog=self, guild=guild))

                if channel:
                    if channel.id in entry["ignore_info"]["channels"]:
                        return bool(NotLogging(eventname, f"Channel \"{channel}\" is being ignored.", cog=self, guild=guild))
                    if channel.id == entry["log_info"]["log_channel"]:
                        return bool(NotLogging(eventname, f"This is the log channel.", cog=self, guild=guild))
                if eventname.lower() not in entry["log_info"]["to_log"]:
                    return bool(NotLogging(eventname, f"Guild is ignoring event \"{eventname}\".", cog=self, guild=guild))
                if not entry["enabled"]:
                    return bool(NotLogging(eventname, f"This guild has disabled logs.", cog=self, guild=guild))
                return True
        except Exception as e:
            print(e)

    def get_log(self, guild: discord.Guild):
        with open(f"data/guilds/{guild.id}.json") as f:
            entry = json.load(f)
            return self.bot.get_channel(entry["log_info"]["log_channel"])

    async def vbl(self, guild, e: NotLogging):
        """VerboseLog: Log NotLogging events if verbose is enabled"""
        return True

    async def log(self, logType: str, guild: int, occurredAt: int, content: dict):
        pass
        # try:
        #     with open(f"data/guilds/{guild}.json", 'r') as entry:
        #         entry = json.load(entry)
        #         logID = len(entry)-4
        #         entry[logID] = {"logType": logType, "occurredAt": occurredAt, "content": content}
        #     with open(f"data/guilds/{guild}.json", 'w') as f:
        #         json.dump(entry, f, indent=2)
        #     try:
        #         json.loads(f"data/guilds/{guild}.json")
        #     except ValueError:
        #         with open(f"data/guilds/{guild}.json", 'w') as f:
        #             json.dump(entry, f, indent=2)
        # except Exception as e:
        #     print(e)

    @commands.Cog.listener()
    async def on_message(self, message: discord.message):
        if message.guild is None:
            return

        if message.guild.id != 684492926528651336:
            return
        att = [a.url for a in message.attachments]
        att += re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message.content)

        with open(f"data/guilds/{message.guild.id}.json") as entry:
            entry = json.load(entry)

        if len(att):
            for attachment in att:
                page = requests.get(attachment)
                f_name = f'tmp/{message.channel.id}{message.id}.png'
                with open(f_name, 'wb') as f:
                    f.write(page.content)
                try:
                    # OCR
                    img = cv2.imread(f_name)
                    low_thresh = 16
                    up_thresh = 4097
                    try:
                        dimensions = [img.shape[0], img.shape[1]]
                    except Exception as e:
                        print(e)
                        return
                    if min(dimensions) < low_thresh:
                        await message.channel.send('Too small')
                    # if max(dimensions) > up_thresh:
                    #     await message.channel.send('Too large')

                    if dimensions[1] > dimensions[0]:
                        w = 5000
                        h = (w//(dimensions[1] if dimensions[1] != 0 else 10)) * dimensions[0]
                    else:
                        h = 5000
                        w = (h//(dimensions[0] if dimensions[0] != 0 else 10)) * dimensions[1]

                    dim = (w, h)
                    img = cv2.resize(img, dim)
                    custom_config = r'--oem 3 --psm 6'

                    read_start = time.time()
                    try:
                        text = pytesseract.image_to_string(img, config=custom_config).lower()
                    except Exception as e:
                        print(e)
                        text = 'No text found'
                    if "wordfilter" in entry:
                        if message.author.id not in entry["wordfilter"]["ignore"]["members"] and message.channel.id not in entry["wordfilter"]["ignore"]["channels"]:
                            passed = False
                            for role in message.author.roles:
                                if role.id in entry["wordfilter"]["ignore"]["roles"]:
                                    passed = True
                            if not passed:
                                for word in [x.group().lower() for x in re.finditer( r'[a-zA-Z]+', text)]:
                                    if word in entry["wordfilter"]["banned"]:
                                        await message.delete()
                                        break
                    # read_end = time.time()

                    # cfimg = cf(f_name)
                    # try:
                    #     dc = cfimg.get_color(quality=2)
                    # except Exception as e:
                    #     print(e)
                    #     dc = (0, 0, 0)

                    # try:
                    #     if dc == (52, 60, 60):
                    #         blank = True
                    #     else:
                    #         blank = False
                    # except Exception as e:
                    #     print(e)
                    #     blank = True

                    # # NSFW
                    # start = time.time()
                    # reason = None
                    # confidence = "90"
                    # async with self.session.post("https://api.deepai.org/api/nsfw-detector", data={'image': page.url}, headers={'api-key': deepAIkey}) as r:
                    #     try:
                    #         resp = await r.json()
                    #         if len(resp['output']['detections']):
                    #             nsfw = True
                    #         else:
                    #             nsfw = False
                    #         try:
                    #             reason = ",".join([x['name']] for x in resp['output']['detections'])
                    #             detections = len(resp['output']['detections'])
                    #             score = resp['output']['nsfw_score'] * 100
                    #         except Exception as e:
                    #             print(e)
                    #         if "Exposed" in reason:
                    #             nsfw = True
                    #         else:
                    #             nsfw = False
                    #     except Exception as e:
                    #         pass
                    #     conf = str(resp['output'])
                    # end = time.time()

                    # e = discord.Embed(
                    #     title="Image sent",
                    #     description=f"**Size:** {dimensions[0]}x{dimensions[1]}\n"
                    #                 f"**NSFW:** {emojis['tick'] if nsfw else emojis['cross']}\n"
                    #                 f"**Reason:** {reason} ({detections} detections, {round(score, 2)}% NSFW)\n"
                    #                 f"**Text:** {text}\n"
                    #                 f"**RGB Colour:** {dc}\n"
                    #                 f"**Blank Image:** {emojis['tick'] if blank else emojis['cross']}\n"
                    #                 f"**Image Read Time Taken:** {round(read_end - read_start, 2)}s\n"
                    #                 f"**Web Request Time Taken:** {round(end - start, 2)}s",
                    #     color=discord.Color(0x00ff00)
                    # )
                    # if message.author.bot is False:
                    #     await message.channel.send(embed=e)
                    # if nsfw:
                    #     await message.delete()
                    #     await message.send(embed=discord.Embed(
                    #         title="Your message was NSFW",
                    #         description="If you believe this was a mistake, please let us know. Just DM a member of Clicks Leadership with"
                    #                     f" the image, along with this:\n```{await resp.json()}```",
                    #         color=colours["delete"]
                    #     ))
                except Exception as e:
                    print(e)

                try:
                    os.remove(f_name)
                except Exception as e:
                    print(e)


def setup(bot):
    bot.add_cog(ImageDetect(bot))
