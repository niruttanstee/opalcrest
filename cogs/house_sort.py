import asyncio
import pymongo.errors
import random

import disnake
from disnake.ext import commands
from connect_db import db_client
from logger import log

import json


class HouseSort(commands.Cog):
    """Sort members into houses."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot

        self.blue = disnake.Colour.blue()
        self.dark_blue = disnake.Colour.dark_blue()
        self.otterpaw_colour = disnake.Colour.from_rgb(136, 67, 242)
        self.elkbarrow_colour = disnake.Colour.from_rgb(249, 211, 113)

        with open('./content/house_sort.json', 'r') as f:
            self.content = json.load(f)

        client = db_client()
        db = client["opalcrest"]
        self.house_collection = db.house
        self.user_collection = db.user

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
        user = inter.user
        # filter out and process only the button we intend
        if inter.component.custom_id != "house_sort":
            return

        # let user know to check their dm
        embed = disnake.Embed(
            description="Continue your story within your DMs.",
            colour=disnake.Colour.blue()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        # send the dm interactions and get the weights
        final_weight = await self.dm_interaction(user)

        # pre-sort embed
        title = self.content['pre_sort']['title']
        description = self.content['pre_sort']['desc']
        embed = await self.default_embed()
        message = await user.send(embed=embed)
        await message.delete(20)

        # sort embed
        status = await self.sort(user, final_weight)
        if status is True:
            await log(__name__, "Opalcrest", user.name, "sorted into house")
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
            return x.user == user and x.component.custom_id == "accept_introduction"

        try:
            x = await self.bot.wait_for('button_click', timeout=60, check=check_dm_intro)
        except asyncio.TimeoutError:
            await message.delete()
            title = self.content['timeout_error_message']['title']
            description = self.content['timeout_error_message']['desc']
            embed = await self.default_embed(title, description, self.dark_blue)
            return await user.send(embed=embed)

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
            return x.user == user and x.component.custom_id == "option_1" or x.component.custom_id == "option_2"

        try:
            x = await self.bot.wait_for('button_click', timeout=60, check=check_options)
        except asyncio.TimeoutError:
            await message.delete()
            title = self.content['timeout_error_message']['title']
            description = self.content['timeout_error_message']['desc']
            embed = await self.default_embed(title, description, self.dark_blue)
            return await user.send(embed=embed)

        option = x.component.custom_id
        if option == "option_1":
            weight['otterpaw'] = weight['otterpaw'] + 1
        else:
            weight['elkbarrow'] = weight['elkbarrow'] + 1
        return weight, message

    async def sort(self, user: disnake.User, weight: dict):
        """
        Sorts user into the house according to the weight.

        Returns a status boolean:
        if True, then user has been sorted.
        if False, then user has not been sorted.

        :param user: the user object.
        :param weight: the weight dictionary.
        :return: boolean.
        """
        otterpaw_weight = weight["otterpaw"]
        elkbarrow_weight = weight["elkbarrow"]

        query = {
            "user_id": f"{user.id}",
            "house": "",
            "coins": 0,
            "house_points": 0
        }

        if otterpaw_weight > elkbarrow_weight:
            # sort into otterpaw
            query["house"] = "otterpaw"
            try:
                self.user_collection.insert_one(query)
            except pymongo.errors.Any:
                return False
            title = self.content["sort"]["otterpaw"]["title"]
            desc = self.content["sort"]["otterpaw"]["desc"]
            embed = await self.default_embed(title, desc, self.otterpaw_colour)
            await user.send(embed=embed)

        elif elkbarrow_weight > otterpaw_weight:
            # sort into elkbarrow
            query["house"] = "elkbarrow"
            try:
                self.user_collection.insert_one(query)
            except pymongo.errors.Any:
                return False
            title = self.content["sort"]["elkbarrow"]["title"]
            desc = self.content["sort"]["elkbarrow"]["desc"]
            embed = await self.default_embed(title, desc, self.elkbarrow_colour)
            await user.send(embed=embed)

        else:
            # random sort user into a house
            choice = random.choice(["otterpaw", "elkbarrow"])
            query["house"] = choice
            try:
                self.user_collection.insert_one(query)
            except pymongo.errors.Any:
                return False
            title = self.content["sort"][f"{choice}"]["title"]
            desc = self.content["sort"][f"{choice}"]["desc"]

            if choice is "otterpaw":
                colour = self.otterpaw_colour
            else:
                colour = self.elkbarrow_colour
            embed = await self.default_embed(title, desc, colour)
            await user.send(embed=embed)

        status = await self.update_house_pop()
        if status is True:
            await log(__name__, "Opalcrest", "system", "updated house population")
        else:
            await log(__name__, "Opalcrest", "system", "FAILED: to update house population")

        return True

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

        print(otterpaw_pop, elkbarrow_pop)

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
