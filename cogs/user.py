import disnake
from disnake.ext import commands
from connect_db import db_client

import logger


class User(commands.Cog):
    """Commands regarding users and its database in the server."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.red = disnake.Colour.red()
        self.green = disnake.Colour.green()

        client = db_client()
        db = client["opalcrest"]
        self.user_collection = db.user

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def user(self, inter):
        pass

    @user.sub_command(description="Deletes the user from the database")
    async def delete(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """
        Deletes the user from the database if it exists.

        :param user: the user object to delete.
        :param inter: the interaction object.

        Parameters
        ----------
        user: The user to delete
        """
        await inter.response.defer(ephemeral=True)
        deleted = self.user_collection.delete_one({"user_id": f"{user.id}"})
        if deleted.deleted_count != 1:
            embed = disnake.Embed(
                description=f"<@{user.id}> was not deleted. No user found in database.",
                colour=self.red
            )
            await inter.followup.send(embed=embed, ephemeral=True)
            return

        embed = disnake.Embed(
            description=f"<@{user.id}> was deleted.",
            colour=self.green
        )
        await inter.followup.send(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(User(bot))
