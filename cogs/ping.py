from quart import Quart
from discord.ext import commands
import discord
import aiohttp
import asyncio
import bot as customBot
from config import config


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shutdown_event = asyncio.Event()

    def _signal_handler(self, *_) -> None:
        shutdown_event.set()

    @commands.Cog.listener()
    async def on_ready(self):
        if self.bot.runningPing:
            return
        self.bot.runningPing = True

        app = Quart(__name__)

        @app.route("/")
        async def ping():
            return str(self.bot.latency)

        @app.route("/stage")
        async def stage():
            return str(config.stage.name)

        @app.route("/role/gid/<string:guild>/rid/<string:role>/user/<string:user>/secret/<string:secret>/code/<string:code>")
        async def role(guild, role, user, secret, code):
            try:
                if secret != config.urlsecret:
                    return "403"
                g = self.bot.get_guild(int(guild))
                mem = await g.fetch_member(int(user))

                await mem.add_roles(g.get_role(int(role)))
                await mem.send(embed=discord.Embed(
                    title=f"<:Tick:729064531107774534> Verified",
                    description=f"You are now verified in {g.name}. The `@{self.bot.get_guild(int(guild)).get_role(int(role)).name}` role has now been given.",
                    color=0x68D49E
                ))
                return "200"
            except Exception as e:
                print(e)
                return "400"

        self.bot.server_teardown = self._signal_handler
        task = await app.run_task(
            "0.0.0.0",
            10000,
            None,
            True,
            None,
            None,
            None,
            shutdown_trigger=self.shutdown_event.wait
        )


def setup(bot):
    bot.add_cog(Ping(bot))


def teardown(bot):
    bot.server_teardown()
