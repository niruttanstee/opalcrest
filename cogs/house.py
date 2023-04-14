import disnake
from disnake.ext import commands
from connect_db import db_client
from logger import log
import json
import pymongo


class House(commands.Cog):
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
            embed = await self.standings_draw_embed(self, standings, None)
            message = await channel.send(embed=embed)
            await inter.followup.send("Done!", ephemeral=True)
        else:
            embed = await self.standings_embed(self, standings, None)
            message = await channel.send(embed=embed)
            await inter.followup.send("Done!", ephemeral=True)

        # store message in database
        search_query = {"type": "standings"}
        standings = self.house_collection.find_one(search_query)
        if not standings:
            self.house_collection.insert_one({"type": "standings", "message_id": message.id, "channel_id": channel.id})
            return
        update_query = {"message_id": message.id, "channel_id": channel.id}
        self.house_collection.update_one(search_query, {"$set": update_query}, upsert=True)
        await log(__name__, "Opalcrest", inter.user, "posted a new house standings embed")

    # points subcommand
    @house.sub_command_group()
    async def points(self, inter):
        pass

    @points.sub_command(description="Give points to user")
    async def give(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User,
                   points: int = commands.Param(gt=0, lt=100)):
        """
        Give house points to user and updates the standings board.

        :param inter: the interaction object that has called.
        :param points: the number of points to give the user.
        :param user: the user to give points to.

        Parameters
        ----------
        user: The user to give the points to
        points: The number of points to give
        """
        await inter.response.defer(ephemeral=True)
        guild = inter.guild

        status = await self.give_points(self, user, points)
        if status is False:
            desc = f"Failed to give <@{user.id}> **{points} point(s)**\nUser may not have a house."
            embed = await self.default_embed(desc, self.red)
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, "Opalcrest", inter.user,
                      f"FAILED: to give {user} {points} points. User may not be in house")
            return

        # update standings board
        await self.activity(self, guild, user, points)

        desc = f"Successfully given <@{user.id}> **{points} point(s)**"
        embed = await self.default_embed(desc, self.green)
        await inter.followup.send(embed=embed, ephemeral=True)
        await log(__name__, "Opalcrest", inter.user, f"gave {user} {points} points")

    @points.sub_command(description="Remove points from user")
    async def remove(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User,
                     points: int = commands.Param(gt=0, lt=100)):
        """
        Remove house points from the user.

        :param inter: the interaction object that has called.
        :param points: the number of points to remove from the user.
        :param user: the user to remove points from.

        Parameters
        ----------
        user: The user to remove the points from
        points: The number of points to remove
        """
        await inter.response.defer(ephemeral=True)
        status = await self.remove_points(self, user, points)
        if status is False:
            desc = f"Failed to remove <@{user.id}> **{points} point(s)**\nUser may not have a house."
            embed = await self.default_embed(desc, self.red)
            await inter.followup.send(embed=embed, ephemeral=True)
            await log(__name__, "Opalcrest", inter.user,
                      f"FAILED: to remove {user} {points} points. User may not be in house")
            return

        desc = f"Successfully removed <@{user.id}> **{points} point(s)**"
        embed = await self.default_embed(desc, self.green)
        await inter.followup.send(embed=embed, ephemeral=True)
        await log(__name__, "Opalcrest", inter.user, f"removed {user} {points} points")

    @staticmethod
    async def give_points(self, user: disnake.User, points: int):
        """
        Gives house points to user.
        True, if successfully given points to user.
        False, if failed to give points to user.

        :param self: the collection.
        :param user: the user to give the points to.
        :param points: the number of points to give.
        :return: the boolean.
        """
        house_points = await self.get_house_points(self, user)

        if house_points is None:
            return False
        house_points += points
        search_query = {"user_id": f"{user.id}"}
        update_query = {"house_points": house_points}
        try:
            self.user_collection.update_one(search_query, {"$set": update_query}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

    @staticmethod
    async def remove_points(self, user: disnake.User, points: int):
        """
        Removes house points from user.
        True, if successfully given points to user.
        False, if failed to give points to user.

        :param self: the collection.
        :param user: the user to remove the points from.
        :param points: the number of points to remove.
        :return: the boolean.
        """
        house_points = await self.get_house_points(self, user)

        if house_points is None:
            return False
        house_points -= points
        if house_points < 0:
            house_points = 0
        search_query = {"user_id": f"{user.id}"}
        update_query = {"house_points": house_points}
        try:
            self.user_collection.update_one(search_query, {"$set": update_query}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

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

    @staticmethod
    async def activity(self, guild: disnake.Guild, user: disnake.User, points: int):
        """
        Calls the update house.
        Creates a list of top five most recent activities.
        Gets the house standings message and update the message.

        :param self:
        :param guild: the guild objects.
        :param user: the user object points given to.
        :param points: the amount of points given to user.
        """
        status = await self.update_house(self)
        if status is not True:
            return

        user_house = self.user_collection.find_one({"user_id": f"{user.id}"})
        user_house = user_house["house"]

        if user_house == "otterpaw":
            house_id = self.otterpaw_role
        else:
            house_id = self.elkbarrow_role

        activity = f"<@&{house_id}> <@{user.id}> has been given {points} pts"

        standings = self.house_collection.find_one({"type": "standings"})
        channel = guild.get_channel(standings["channel_id"])
        message = await channel.fetch_message(standings["message_id"])

        activities = message.embeds[0].fields[2].value
        activities = activities.split("\n")
        if len(activities) > 4:
            del activities[-1]
        activities.insert(0, activity)
        value = ""
        for activity in activities:
            if activity == "":
                continue
            value = value + activity + "\n"

        # update standings embed
        standings, draw = await self.get_house_standings(self)
        if draw:
            embed = await self.standings_draw_embed(self, standings, value)
            await message.edit(embed=embed)
        else:
            embed = await self.standings_embed(self, standings, value)
            await message.edit(embed=embed)

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
                "role_id": ""
            },
            "second": {
                "house_name": "",
                "points": "",
                "role_id": ""
            }
        }
        otterpaw = self.house_collection.find_one({"house_name": "otterpaw"})
        elkbarrow = self.house_collection.find_one({"house_name": "elkbarrow"})

        if otterpaw["points"] > elkbarrow["points"]:
            standings["first"]["house_name"] = otterpaw["house_name"]
            standings["first"]["points"] = otterpaw["points"]
            standings["first"]["role_id"] = self.otterpaw_role

            standings["second"]["house_name"] = elkbarrow["house_name"]
            standings["second"]["points"] = elkbarrow["points"]
            standings["second"]["role_id"] = self.elkbarrow_role
            return standings, False

        elif elkbarrow["points"] > otterpaw["points"]:
            standings["first"]["house_name"] = elkbarrow["house_name"]
            standings["first"]["points"] = elkbarrow["points"]
            standings["first"]["role_id"] = self.elkbarrow_role

            standings["second"]["house_name"] = otterpaw["house_name"]
            standings["second"]["points"] = otterpaw["points"]
            standings["second"]["role_id"] = self.otterpaw_role
            return standings, False

        else:
            standings["first"]["house_name"] = otterpaw["house_name"]
            standings["first"]["points"] = otterpaw["points"]
            standings["first"]["role_id"] = self.otterpaw_role

            standings["second"]["house_name"] = elkbarrow["house_name"]
            standings["second"]["points"] = elkbarrow["points"]
            standings["second"]["role_id"] = self.elkbarrow_role
            return standings, True

    @staticmethod
    async def get_house_points(self, user):
        """
        Gets the total amount of points from specified user in the database.
        If user is not in the database, returns None.

        :param self: the initialised variables.
        :param user: the user to get the house points from.
        :return: the amount of house points.
        """
        points = self.user_collection.find_one({"user_id": f"{user.id}"})

        if points is None:
            return None
        points = points["house_points"]
        return points

    @staticmethod
    async def update_house(self):
        """
        Calls update house population and update house points together.
        if True, the house has been updated.
        if False, the house has not been updated.

        :return: the boolean.
        """
        pop = await self.update_house_pop(self)
        points = await self.update_house_points(self)

        if (pop is False) or (points is False):
            return False
        return True

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
        """
        Updates the house points in the database.

        Returns boolean status:
        if True, the house has been updated.
        if False, the house has not been updated.
        :return: boolean.
        """
        otterpaw_points = 0
        elkbarrow_points = 0
        for user in self.user_collection.find({"house": "otterpaw"}):
            otterpaw_points += user["house_points"]

        for user in self.user_collection.find({"house": "elkbarrow"}):
            elkbarrow_points += user["house_points"]

        query_0 = {"house_name": "otterpaw"}
        points_query_0 = {"points": otterpaw_points}
        query_1 = {"house_name": "elkbarrow"}
        points_query_1 = {"points": elkbarrow_points}

        try:
            self.house_collection.update_one(query_0, {"$set": points_query_0}, upsert=True)
            self.house_collection.update_one(query_1, {"$set": points_query_1}, upsert=True)
        except pymongo.errors.Any:
            return False
        return True

    @staticmethod
    async def standings_embed(self, standings: dict, activity: str):
        """
        Creates a standings embed and returns it.

        :param self: json referencing.
        :param standings: the standing dict.
        :param activity: the top 5 most recent activities. Otherwise, None.
        :return embed: the embed to return.
        """
        if activity is None:
            activity = ""

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
        embed.add_field(name=f"First place",
                        value=f"<@&{first[2]}> **({first[1]} points)**\nㅤ",
                        inline=True)
        embed.add_field(name=f"Runner-up",
                        value=f"<@&{second[2]}> **({second[1]} points)**\nㅤ",
                        inline=True)
        embed.add_field(name="Recent house activities:",
                        value=activity,
                        inline=False)
        embed.set_image(url=url)

        return embed

    @staticmethod
    async def standings_draw_embed(self, standings: dict, activity: str):
        """
        Creates a draw standings embed and returns it.

        :param self: json referencing.
        :param standings: the standing dict.
        :param activity: the top 5 most recent activities. Otherwise, None.
        :return embed: the embed to return.
        """
        if activity is None:
            activity = ""

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
        embed.add_field(name=f"Draw",
                        value=f"<@&{first[2]}> **({first[1]} points)**\nㅤ",
                        inline=True)
        embed.add_field(name=f"Draw",
                        value=f"<@&{second[2]}> **({second[1]} points)**\nㅤ",
                        inline=True)
        embed.add_field(name="Recent house activities:",
                        value=activity,
                        inline=False)
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
        first_role_id = standings["first"]["role_id"]

        second_name = standings["second"]["house_name"]
        second_points = standings["second"]["points"]
        second_role_id = standings["second"]["role_id"]

        first = [first_name, first_points, first_role_id]
        second = [second_name, second_points, second_role_id]

        return first, second


def setup(bot: commands.Bot):
    bot.add_cog(House(bot))
