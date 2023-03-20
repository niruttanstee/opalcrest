import disnake
from disnake.ext import commands
from connect_db import db_client
from logger import log

import logger


class Role(commands.Cog):
    """Commands regarding roles in the server."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.red = disnake.Colour.red()
        self.green = disnake.Colour.green()

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def role(self, inter):
        pass

    @role.sub_command(description="Gives role to user")
    async def give(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role, user: disnake.User):
        """
        Gives role to a user.

        :param role: the role object to give.
        :param user: the user object to give role to.
        :param inter: the interaction object.

        Parameters
        ----------
        role: The role to give
        user: The user to give the role to
        """
        await inter.response.defer(ephemeral=True)
        try:
            await user.add_roles(role)
        except disnake.HTTPException:
            embed = disnake.Embed(
                description=f"<@&{role.id}> failed to be added to <@{user.id}>.",
                colour=self.red
            )
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, inter.guild.name, inter.user.name, f"FAILED: to give {user.name} the role: {role.name}")
            return
        embed = disnake.Embed(
            description=f"<@&{role.id}> was added to <@{user.id}>.",
            colour=self.green
        )
        await log(__name__, inter.guild.name, inter.user.name, f"gave {user.name} the role: {role.name}")
        await inter.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    async def give_in_sys(role: disnake.Role, user: disnake.User):
        """
        Gives role to a user within the system.

        :param role: the role object to give.
        :param user: the user object to give role to.

        Parameters
        ----------
        role: The role to give
        user: The user to give the role to
        """
        try:
            await user.add_roles(role)
            await log(__name__, "Opalcrest", "system", f"gave {user.name} the role: {role.name}")
        except disnake.HTTPException:
            await log(__name__, "Opalcrest", "system", f"FAILED: to give {user.name} the role: {role.name}")
            return False
        return True


def setup(bot: commands.Bot):
    bot.add_cog(Role(bot))
