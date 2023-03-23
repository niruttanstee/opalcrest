import asyncio
import pymongo.errors
import random

import disnake
from disnake.ext import commands
from connect_db import db_client
from cogs.role import Role
from cogs.house import House
from logger import log

import json


class HouseSort(commands.Cog):
    """Sort members into houses."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot

        self.blue = disnake.Colour.blue()
        self.dark_blue = disnake.Colour.dark_blue()
        self.red = disnake.Colour.red()
        self.otterpaw_colour = disnake.Colour.from_rgb(148, 94, 231)
        self.elkbarrow_colour = disnake.Colour.from_rgb(249, 211, 113)
        self.otterpaw_role = 1087146529959198861
        self.elkbarrow_role = 1087146748465659986
        self.otterpaw_common_room = 1087148966325534882
        self.elkbarrow_common_room = 1087149068280664095

        with open("./content/house_sort.json", 'r') as f:
            self.content = json.load(f)

        client = db_client()
        db = client["opalcrest"]
        self.house_collection = db.house
        self.user_collection = db.user
        self.user_profile_collection = db.user_profile_log

    # parent command
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def house_sort(self, inter):
        pass

    @house_sort.sub_command(description="Creates the house sorting button")
    async def button(self, inter: disnake.ApplicationCommandInteraction):
        """
        Creates and sends a house sorting message for users to interact.

        :param inter: the interaction object.
        """
        channel = inter.channel
        message = self.content["button"]
        components = [
            disnake.ui.Button(label="Hold onto the book (Get sorted into a house)",
                              style=disnake.ButtonStyle.primary,
                              custom_id="house_sort")
        ]
        await channel.send(message, components=components)
        await inter.response.send_message("Button sent", ephemeral=True)

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        """
        Sends a dm quiz to the user and sorts them into a house.

        :param inter: the message interaction object.
        :return:
        """
        await inter.response.defer(ephemeral=True)
        guild = inter.guild
        user = inter.user
        # filter out and process only the button we intend
        if inter.component.custom_id != "house_sort":
            return

        # process only users without a house
        user_profile = self.user_collection.find_one({"user_id": f"{user.id}"})
        if user_profile is not None:
            embed = disnake.Embed(
                description="You have already completed, or currently doing **Chapter 1**.",
                colour=self.red
            )
            await inter.followup.send(embed=embed, ephemeral=True)
            return

        await log(__name__, "Opalcrest", user.name, "requests to be sorted into a house")

        # check if user already doing the chapter
        doing_chapter = self.user_collection.find_one({"user_id": f"{user.id}"})
        if doing_chapter is not None:
            embed = disnake.Embed(
                description="Please continue **Chapter 1** in your dms.",
                colour=self.red
            )
            await inter.followup.send(embed=embed, ephemeral=True)
            return

        self.user_collection.insert_one({"user_id": f"{user.id}"})

        # let user know to check their dm
        embed = disnake.Embed(
            description="Continue your story within your DMs.",
            colour=self.blue
        )
        await inter.followup.send(embed=embed, ephemeral=True)

        # send the dm interactions and get the weights
        final_weight = await self.dm_interaction(user)
        if final_weight is None:
            return

        # store final_weight records
        self.user_profile_collection.insert_one({"user_id": f"{user.id}", "weights": final_weight})

        # pre-sort embed
        title = self.content['pre_sort']['title']
        description = self.content['pre_sort']['desc']
        embed = await self.default_embed(title, description, self.blue)
        embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
        message = await user.send(embed=embed)
        await asyncio.sleep(25)
        await message.delete()

        # sort embed
        house, status = await self.sort(guild, user, final_weight)
        if status is True:
            await log(__name__, "Opalcrest", user.name, f"sorted into house {house}")
        else:
            await log(__name__, "Opalcrest", user.name, "FAILED: to be sorted into house")

    async def dm_interaction(self, user: disnake.User):
        """
        Asks users a number of questions and returns the weighted results.

        :param user: the user object.
        :return weights: the weighted house dictionary.
        """
        # introduction dm embed
        title = self.content['dm_interaction']['title']
        description = self.content['dm_interaction']['desc']
        embed = await self.default_embed(title, description, self.blue)
        embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
        components = [
            disnake.ui.Button(label='Respond: "I am ready"',
                              style=disnake.ButtonStyle.primary,
                              custom_id="accept_introduction")
        ]
        message = await user.send(embed=embed, components=components)

        def check_dm_intro(x: disnake.MessageInteraction):
            return x.user == user and message.channel == user.dm_channel \
                and x.component.custom_id == "accept_introduction"

        try:
            x = await self.bot.wait_for('button_click', timeout=60, check=check_dm_intro)
        except asyncio.TimeoutError:
            self.user_collection.delete_one({"user_id": f"{user.id}"})
            await message.delete()
            title = self.content['timeout_error_message']['title']
            description = self.content['timeout_error_message']['desc']
            embed = await self.default_embed(title, description, self.dark_blue)
            await user.send(embed=embed)
            await log(__name__, "Opalcrest", user.name, "timed out")
            return

        weight = {"otterpaw": 0, "elkbarrow": 0}
        current_question = 1
        while current_question <= 4:
            weight, message = await self.questions(user, message, current_question, weight)
            if weight is None or message is None:
                return
            current_question += 1

        # fetch house population and calculate the final weight
        otterpaw_pop = self.house_collection.find_one({"house_name": "otterpaw"})
        elkbarrow_pop = self.house_collection.find_one({"house_name": "elkbarrow"})

        otterpaw_pop = otterpaw_pop["population"]
        elkbarrow_pop = elkbarrow_pop["population"]

        if elkbarrow_pop > otterpaw_pop:
            weight["otterpaw"] = weight["otterpaw"] + 1
        elif otterpaw_pop > elkbarrow_pop:
            weight["elkbarrow"] = weight["elkbarrow"] + 1

        await message.delete()
        return weight

    async def questions(self, user: disnake.User, message: disnake.Message, question_num: int, weight: dict):
        """
        Sends the first question to the user and returns the weighed result.

        :param user: the user object.
        :param message: the message object.
        :param question_num: the current question number.
        :param weight: the weight dictionary.
        :return weight: the updated weight dictionary.
        :return message: the new message object.
        """
        await message.delete()

        title = self.content[f'question_{question_num}']['title']
        description = self.content[f'question_{question_num}']['desc']
        embed = await self.default_embed(title, description, self.blue)

        field_1_title = self.content[f'question_{question_num}']['field_1']['title']
        field_1_desc = self.content[f'question_{question_num}']['field_1']['desc']

        field_2_title = self.content[f'question_{question_num}']['field_2']['title']
        field_2_desc = self.content[f'question_{question_num}']['field_2']['desc']

        embed.add_field(field_1_title, field_1_desc, inline=True)
        embed.add_field(field_2_title, field_2_desc, inline=True)
        embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
        components = [
            disnake.ui.Button(label='Option 1',
                              style=disnake.ButtonStyle.secondary,
                              custom_id="option_1"),
            disnake.ui.Button(label='Option 2',
                              style=disnake.ButtonStyle.secondary,
                              custom_id="option_2"),
        ]
        message = await user.send(embed=embed, components=components)

        def check_options(x: disnake.MessageInteraction):
            return (x.user == user and message.channel == user.dm_channel and x.component.custom_id == "option_1") \
                or (x.user == user and message.channel == user.dm_channel and x.component.custom_id == "option_2")

        try:
            x = await self.bot.wait_for('button_click', timeout=120, check=check_options)
        except asyncio.TimeoutError:
            self.user_collection.delete_one({"user_id": f"{user.id}"})
            await message.delete()
            title = self.content['timeout_error_message']['title']
            description = self.content['timeout_error_message']['desc']
            embed = await self.default_embed(title, description, self.dark_blue)
            await user.send(embed=embed)
            await log(__name__, "Opalcrest", user.name, "timed out")
            return None, None

        option = x.component.custom_id
        if option == "option_1":
            weight['otterpaw'] = weight['otterpaw'] + 1
        else:
            weight['elkbarrow'] = weight['elkbarrow'] + 1
        return weight, message

    async def sort(self, guild: disnake.Guild, user: disnake.User, weight: dict):
        """
        Sorts user into the house according to the weight.

        Returns a status boolean:
        if True, then user has been sorted.
        if False, then user has not been sorted.

        :param guild: the guild object to fetch the role.
        :param user: the user object.
        :param weight: the weight dictionary.
        :return: boolean.
        """
        otterpaw_weight = weight["otterpaw"]
        elkbarrow_weight = weight["elkbarrow"]

        query = {
            "house": "",
            "coins": 0,
            "house_points": 0
        }

        if otterpaw_weight > elkbarrow_weight:
            # sort into otterpaw
            query["house"] = "otterpaw"
            try:
                self.user_collection.update_one({"user_id": f"{user.id}"}, {"$set": query}, upsert=True)
            except pymongo.errors.Any:
                return False, False
            title = self.content["sort"]["otterpaw"]["title"]
            desc = self.content["sort"]["otterpaw"]["desc"]
            embed = await self.default_embed(title, desc, self.otterpaw_colour)
            embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
            await user.send(embed=embed)

        elif elkbarrow_weight > otterpaw_weight:
            # sort into elkbarrow
            query["house"] = "elkbarrow"
            try:
                self.user_collection.update_one({"user_id": f"{user.id}"}, {"$set": query}, upsert=True)
            except pymongo.errors.Any:
                return False, False
            title = self.content["sort"]["elkbarrow"]["title"]
            desc = self.content["sort"]["elkbarrow"]["desc"]
            embed = await self.default_embed(title, desc, self.elkbarrow_colour)
            embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
            await user.send(embed=embed)

        else:
            # random sort user into a house
            choice = random.choice(["otterpaw", "elkbarrow"])
            query["house"] = choice
            try:
                self.user_collection.update_one({"user_id": f"{user.id}"}, {"$set": query}, upsert=True)
            except pymongo.errors.Any:
                return False, False
            title = self.content["sort"][f"{choice}"]["title"]
            desc = self.content["sort"][f"{choice}"]["desc"]

            if choice == "otterpaw":
                colour = self.otterpaw_colour
                image = "https://disnake.dev/assets/disnake-thin-banner.png"
            else:
                colour = self.elkbarrow_colour
                image = "https://disnake.dev/assets/disnake-thin-banner.png"
            embed = await self.default_embed(title, desc, colour)
            embed.set_image(url=image)
            await user.send(embed=embed)

        # give house role to user and announce in common rooms
        desc = f"<@{user.id}> is now part of this illustrious house. Please give them a warm welcome!"
        house = query["house"]

        if house == "otterpaw":
            role = guild.get_role(self.otterpaw_role)
            channel = self.otterpaw_common_room
            embed = disnake.Embed(
                description=desc,
                colour=self.otterpaw_colour
            )
        else:
            role = guild.get_role(self.elkbarrow_role)
            channel = self.elkbarrow_common_room
            embed = disnake.Embed(
                description=desc,
                colour=self.elkbarrow_colour
            )
        status = await Role.give_role(role, user)
        if status is False:
            await log(__name__, "Opalcrest", user.name, "FAILED: to receive house role")

        # announce user in common rooms
        channel = guild.get_channel(channel)
        await channel.send(embed=embed)

        status = await House.update_house_pop(self)
        if status is False:
            await log(__name__, "Opalcrest", "system", "FAILED: to update house population")

        return house, True

    @staticmethod
    async def default_embed(title: str, desc: str, colour: disnake.Colour):
        """
        Returns a default embed template.

        :param title: the title string.
        :param desc: the description string.
        :param colour: the colour object.
        :return embed: the embed object.
        """
        embed = disnake.Embed(
            title=title,
            description=desc,
            colour=colour
        )
        return embed


def setup(bot: commands.Bot):
    bot.add_cog(HouseSort(bot))
