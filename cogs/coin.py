import disnake
from disnake.ext import commands
from connect_db import db_client
from logger import log
import json
import pymongo


class Coin(commands.Cog):
    """Commands regarding roles in the server."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.red = disnake.Colour.red()
        self.green = disnake.Colour.green()
        self.blue = disnake.Colour.blue()
        self.otterpaw_colour = disnake.Colour.from_rgb(148, 94, 231)
        self.elkbarrow_colour = disnake.Colour.from_rgb(249, 211, 113)
        self.otterpaw_role = 1087146529959198861
        self.elkbarrow_role = 1087146748465659986

        with open("./content/house.json", 'r') as f:
            self.content = json.load(f)

        client = db_client()
        db = client["opalcrest"]
        self.house_collection = db.house
        self.user_collection = db.user

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def coin(self, inter):
        pass

    @coin.sub_command(description="Give coins.")
    async def give(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User,
                   coins: int = commands.Param(gt=0, lt=100)):
        """
        Give coins to a user.

        :param inter: the interaction object.
        :param coins: the number of coins to give the user.
        :param user: the user to give the coins to.

        Parameters
        ----------
        user: The user to give the coins to
        points: The amount of coins to give
        """
        await inter.response.defer(ephemeral=True)
        guild = inter.guild

        status = await self.give_coins(self, user, coins)
        if status is False:
            desc = f"Failed to give <@{user.id}> **{coins} coin(s)**\nUser may not belong to a house yet."
            embed = await self.default_embed(desc, self.red)
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, "Opalcrest", inter.user,
                      f"FAILED: to give {user} {coins} coins. User may not belong to a house yet")
            return

        desc = f"Successfully given <@{user.id}> **{coins} coin(s)**"
        embed = await self.default_embed(desc, self.green)
        await inter.followup.send(embed=embed, ephemeral=True)
        await log(__name__, "Opalcrest", inter.user, f"gave {user} {coins} coins")

    @staticmethod
    async def default_embed(desc: str, colour: disnake.Colour):
        """
        Returns a simple description only embed.

        :param desc: the description for the embed.
        :param colour: the colour object.
        :return embed: the embed object.
        """
        embed = disnake.Embed(
            description=desc,
            colour=colour
        )
        return embed


def setup(bot: commands.Bot):
    bot.add_cog(Coin(bot))
