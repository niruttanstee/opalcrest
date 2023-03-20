import json

import disnake
from disnake.ext import commands
from connect_db import db_client
from logger import log

import logger
import pymongo


class House(commands.Cog):
    """Commands regarding roles in the server."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.red = disnake.Colour.red()
        self.green = disnake.Colour.green()
        self.otterpaw_colour = disnake.Colour.from_rgb(148, 94, 231)
        self.elkbarrow_colour = disnake.Colour.from_rgb(249, 211, 113)
        self.blue = disnake.Colour.blue()

        with open("./content/house.json", 'r') as f:
            self.content = json.load(f)

        client = db_client()
        db = client["opalcrest"]
        self.house_collection = db.house

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def house(self, inter):
        pass

    # standings subcommand
    @house.sub_command_group()
    async def standings(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @standings.sub_command(description="Posts the house standings message")
    async def post(self, inter: disnake.ApplicationCommandInteraction):
        channel = inter.channel
        await inter.response.defer(ephemeral=True)
        standings, draw = await self.get_house_standings(self)
        # post standings embed
        if draw:
            embed = await self.standings_draw_embed(self, standings)
            await channel.send(embed=embed)
            await inter.followup.send("Done!", ephemeral=True)
        else:
            embed = await self.standings_embed(self, standings)
            await channel.send(embed=embed)
            await inter.followup.send("Done!", ephemeral=True)

        # store standings embed in database
        pass

    @staticmethod
    async def update_post(self):
        # updates the existing standings embed as a logger of activities
        pass

    @staticmethod
    async def get_house_standings(self):
        """
        Fetches the total house points and population from the database and
        returns a dictionary and a boolean signifying whether it is a draw.

        :return standings: the standings' dict.
        :return draw: a boolean signifying if the standings is a draw.
        """
        standings = {
            "first": {
                "house_name": "",
                "points": "",
                "population": ""
            },
            "second": {
                "house_name": "",
                "points": "",
                "population": ""
            }
        }
        otterpaw = self.house_collection.find_one({"house_name": "otterpaw"})
        elkbarrow = self.house_collection.find_one({"house_name": "elkbarrow"})

        if otterpaw["points"] > elkbarrow["points"]:
            standings["first"]["house_name"] = otterpaw["house_name"]
            standings["first"]["points"] = otterpaw["points"]
            standings["first"]["population"] = otterpaw["population"]

            standings["second"]["house_name"] = elkbarrow["house_name"]
            standings["second"]["points"] = elkbarrow["points"]
            standings["second"]["population"] = elkbarrow["population"]
            return standings, False

        elif elkbarrow["points"] > otterpaw["points"]:
            standings["first"]["house_name"] = elkbarrow["house_name"]
            standings["first"]["points"] = elkbarrow["points"]
            standings["first"]["population"] = elkbarrow["population"]

            standings["second"]["house_name"] = otterpaw["house_name"]
            standings["second"]["points"] = otterpaw["points"]
            standings["second"]["population"] = otterpaw["population"]
            return standings, False

        else:
            standings["first"]["house_name"] = otterpaw["house_name"]
            standings["first"]["points"] = otterpaw["points"]
            standings["first"]["population"] = otterpaw["population"]

            standings["second"]["house_name"] = elkbarrow["house_name"]
            standings["second"]["points"] = elkbarrow["points"]
            standings["second"]["population"] = elkbarrow["population"]
            return standings, True

    # points subcommand
    @house.sub_command_group()
    async def points(self, inter):
        pass

    @staticmethod
    async def update_house(self):
        # updates the house population and points calling the below
        pass

    @staticmethod
    async def update_house_pop(self):
        """
        Updates the house population in the database.

        Returns boolean status:
        if True, the house has been updated.
        if False, the house has not been updated.

        :return: boolean.
        """
        otterpaw_pop = self.user_collection.find({"house": "otterpaw"})
        elkbarrow_pop = self.user_collection.find({"house": "elkbarrow"})
        otterpaw_pop = len(list(otterpaw_pop))
        elkbarrow_pop = len(list(elkbarrow_pop))

        query_0 = {"house_name": "otterpaw"}
        population_query_0 = {"population": otterpaw_pop}
        query_1 = {"house_name": "elkbarrow"}
        population_query_1 = {"population": elkbarrow_pop}

        try:
            self.house_collection.update_one(query_0, {"$set": population_query_0}, upsert=True)
            self.house_collection.update_one(query_1, {"$set": population_query_1}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

    @staticmethod
    async def update_house_points(self):
        # updates the house points
        pass

    @staticmethod
    async def standings_embed(self, standings: dict):
        """
        Creates a standings embed and returns it.

        :param self: json referencing.
        :param standings: the standing dict.
        :return embed: the embed to return.
        """
        title = self.content["standings"]["title"]
        desc = self.content["standings"]["desc"]
        url = self.content["standings"]["image"]

        first, second = await self.extract_standings(standings)

        if first[0] == "otterpaw":
            colour = self.otterpaw_colour
        else:
            colour = self.elkbarrow_colour

        embed = disnake.Embed(
            title=title,
            description=desc,
            colour=colour
        )
        embed.add_field(name=f"(1) {first[0]}",
                        value=f"{first[1]} points\n{first[2]} members",
                        inline=True)
        embed.add_field(name=f"(2) {second[0]}",
                        value=f"{second[1]} points\n{second[2]} members",
                        inline=True)
        embed.set_image(url=url)

        return embed

    @staticmethod
    async def standings_draw_embed(self, standings: dict):
        """
        Creates a draw standings embed and returns it.

        :param self: json referencing.
        :param standings: the standing dict.
        :return embed: the embed to return.
        """
        title = self.content["standings"]["title"]
        desc = self.content["standings"]["desc"]
        colour = self.blue
        url = self.content["standings"]["image"]

        first, second = await self.extract_standings(standings)

        embed = disnake.Embed(
            title=title,
            description=desc,
            colour=colour
        )
        embed.add_field(name=f"(1) {first[0]}",
                        value=f"{first[1]} points\n{first[2]} members",
                        inline=True)
        embed.add_field(name=f"(1) {second[0]}",
                        value=f"{second[1]} points\n{second[2]} members",
                        inline=True)
        embed.set_image(url=url)
        return embed

    @staticmethod
    async def extract_standings(standings: dict):
        """
        Extracts the standings dictionary and returns the content.

        :return first: the highest scoring house list.
        :return second: the second scoring house list.
        """
        first_name = standings["first"]["house_name"]
        first_points = standings["first"]["points"]
        first_pop = standings["first"]["population"]

        second_name = standings["second"]["house_name"]
        second_points = standings["second"]["points"]
        second_pop = standings["second"]["population"]

        first = [first_name, first_points, first_pop]
        second = [second_name, second_points, second_pop]

        return first, second


def setup(bot: commands.Bot):
    bot.add_cog(House(bot))
