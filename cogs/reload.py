import disnake
from disnake.ext import commands

from logger import log


class Reload(commands.Cog):
    """Reloads a selected cog."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.dev_id = 241126463904940032
        self.red = disnake.Colour.red()
        self.green = disnake.Colour.green()

    @commands.slash_command(description="Reloads a cog")
    @commands.default_member_permissions(administrator=True)
    async def reload(self, inter: disnake.ApplicationCommandInteraction, name: str):
        """
        Reloads the selected Cog if exists.

        :param inter: the interaction object.
        :param name: the cog to reload.
        """
        if inter.user.id != self.dev_id:
            return

        embed = disnake.Embed(
            description=f"Attempting to reload **{name}** cog.",
            colour=self.green
        )
        await log(__name__, inter.guild.name, inter.user.name, f"reloading {name} cog")
        await inter.response.send_message(embed=embed)

        try:
            self.bot.reload_extension(f"cogs.{name}")
        except disnake.ext.commands.ExtensionNotFound:
            await log(__name__, inter.guild.name, inter.user.name, f"FAILED: to reload {name} cog")
            return




def setup(bot: commands.Bot):
    bot.add_cog(Reload(bot))
