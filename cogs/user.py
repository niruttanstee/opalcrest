import disnake
from disnake.ext import commands

import logger


class User(commands.Cog):
    """Commands regarding users and its database in the server."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def house_sort(self, inter):
        pass


def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
