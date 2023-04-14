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
        self.user_collection = db.user

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def coin(self, inter):
        pass

    @coin.sub_command(description="Give coins to user")
    async def give(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User,
                   amount: int = commands.Param(gt=0, lt=100)):
        """
        Calls the function to give coins to the user.

        :param inter: the interaction object.
        :param amount: the number of coins to give the user.
        :param user: the user to give the coins to.

        Parameters
        ----------
        user: The user to give the coins to
        amount: The amount of coins to give
        """
        await inter.response.defer(ephemeral=True)
        status = await self.give_coins(self, user, amount)
        if status is False:
            desc = f"Failed to give <@{user.id}> **{amount} coin(s)**\nUser may not belong to a house yet."
            embed = await self.default_embed(desc, self.red)
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, "Opalcrest", inter.user,
                      f"FAILED: to give {user} {amount} coins. User may not belong to a house yet")
            return

        desc = f"Successfully given <@{user.id}> **{amount} coin(s)**"
        embed = await self.default_embed(desc, self.green)
        await inter.followup.send(embed=embed, ephemeral=True)
        await log(__name__, "Opalcrest", inter.user, f"gave {user} {amount} coins")

    @coin.sub_command(description="Remove coins from user")
    async def remove(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User,
                     amount: int = commands.Param(gt=0, lt=100)):
        """
        Calls the function to remove coins from the user.

        :param inter: the interaction object.
        :param user: the user to remove the coins from.
        :param amount: the number of coins to remove from the user.

        Parameters
        ----------
        user: The user to remove the coins from
        amount: The amount of coins to remove
        """
        await inter.response.defer(ephemeral=True)
        is_puchase = False
        status = await self.remove_coins(self, is_puchase, user, amount)
        if status is False:
            desc = f"Failed to remove <@{user.id}> **{amount} coin(s)**\nUser maybe not belong to a house yet."
            embed = await self.default_embed(desc, self.red)
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, "Opalcrest", inter.user,
                      f"FAILED: to remove {user} {amount} coins. User may not belong to a house yet.")
            return

        desc = f"Successfully removed **{amount} coin(s)** from <@{user.id}>"
        embed = await self.default_embed(desc, self.green)
        await inter.followup.send(embed=embed, ephemeral=True)
        await log(__name__, "Opalcrest", inter.user, f"removed {amount} coins from {user}")

    @staticmethod
    async def give_coins(self, user: disnake.User, coins: int):
        """
        Give coins to a specified user by updating the amount in the database.
        Returns True, if function successfully gives coins to the user.
        Otherwise, return False.

        :param self: the initialised variables.
        :param user: the user to give the coins to.
        :param coins: the amount of coins to give.
        :return: the boolean status.
        """
        user_bank = await self.get_coins(self, user)
        if user_bank is None:
            return False

        user_bank += coins

        search_query = {"user_id": f"{user.id}"}
        update_query = {"coins": user_bank}
        try:
            self.user_collection.update_one(search_query, {"$set": update_query}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

    @staticmethod
    async def remove_coins(self, is_purchase: bool, user: disnake.User, coins: int):
        """
        Remove coins from a specified user by updating the amount in the database.
        If is_admin is False, then it bypasses purchasing rules.
            Can remove any amount of coins until 0.

        If is_purchase is True, then the removal follows purchasing rules.
            Cannot remove coins if specified amount is more than user's current.

        Returns True if coins have been removed, otherwise False.

        :param self: the initialisation variables.
        :param is_purchase: the boolean for following purchasing rule.
        :param user: the user to remove the coins from.
        :param coins: the amount of coins to remove from the user.
        :return: the boolean status.
        """
        user_bank = await self.get_coins(self, user)
        if user_bank is None:
            return False

        if is_purchase:
            if coins > user_bank:
                return False  # User doesn't have enough coins to purchase.
            user_bank -= coins
        else:
            if coins > user_bank:
                user_bank = 0
            else:
                user_bank -= coins

        search_query = {"user_id": f"{user.id}"}
        update_query = {"coins": user_bank}
        try:
            self.user_collection.update_one(search_query, {"$set": update_query}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

    @staticmethod
    async def get_coins(self, user: disnake.User):
        """
        Gets the amount of coins a user has in their bank.
        If user is not found, returns None.

        :param self: the initialised variables.
        :param user: the user to get the amount of coins.
        :return: amount of coins the user has.
        """
        user_col = self.user_collection.find_one({"user_id": f"{user.id}"})

        if user_col is None:
            return None
        user_bank = user_col["coins"]
        return user_bank

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
