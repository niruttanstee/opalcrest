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
        await log(__name__, f"{inter.guild.name}", f"{inter.user.name}",
                  f"requests to give {user.name} the role: {role.name}")
        await inter.response.defer(ephemeral=True)

        status = await self.give_role(role, user)

        if status is False:
            embed = disnake.Embed(
                description=f"<@&{role.id}> failed to be added to <@{user.id}>.",
                colour=self.red
            )
            await inter.followup.send(embed=embed, ephemeral=True)
        else:
            embed = disnake.Embed(
                description=f"<@&{role.id}> was added to <@{user.id}>.",
                colour=self.green
            )
            await inter.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    async def give_role(role: disnake.Role, user: disnake.User):
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
