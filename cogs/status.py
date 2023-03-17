import disnake
from disnake.ext import commands

import logger


class Status(commands.Cog):
    """Gets bot latency response time."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.slash_command(description="Get response status from Opal Crest to you")
    @commands.default_member_permissions(manage_channels=True)
    async def status(self, inter: disnake.ApplicationCommandInteraction):
        """
        Sends a status embed message after fetching the latency of the bot to the server.

        :param inter: the interaction object.
        """
        latency = round(self.bot.latency * 1000, 0)
        latency = str(latency).split('.')[0]

        # Embed that changes colour depending on latency times.
        check_latency = int(latency)

        if check_latency <= 125:
            status = "All systems operational"
            status_colour = disnake.Colour.green()
        elif check_latency > 125 and latency <= 200:
            status = "Experiencing degraded performance"
            status_colour = disnake.Colour.yellow()
        else:
            status = "Outage - We're working to fix the problem"
            status_colour = disnake.Colour.red()

        embed = disnake.Embed(
            title=status,
            color=status_colour
        )

        await inter.response.send_message(embed=embed, ephemeral=True)
        await logger.log(__name__, inter.guild, inter.user, f"fetched a latency of {latency}ms")


def setup(bot: commands.Bot):
    bot.add_cog(Status(bot))
