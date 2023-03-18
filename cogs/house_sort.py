import asyncio

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

        with open('./content/house_sort.json', 'r') as f:
            self.content = json.load(f)

        client = await db_client()
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

        # Send the dm interactions and get the weights
        final_weight = await self.dm_interaction(user)

        # sort the user using the weights into the house & embed
        # update the user into the database
        # update the house total in the database

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
            return await self.timeout_error_message(user, message)

        weight = {"otterpaw": 0, "elkbarrow": 0}
        print(weight)
        current_question = 1
        while current_question <= 4:
            weight, message = await self.questions(user, message, current_question, weight)
            print(weight)
            if weight is None or message is None:
                return
            current_question += 1

        # fetch house population and calculate the final weight
        otterpaw_pop = self.house_collection.find_one({"house_name": "otterpaw"})
        elkbarrow_pop = self.house_collection.fine_one({"house_name": "elkbarrow"})

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
            return await self.timeout_error_message(user, message)

        option = x.component.custom_id
        if option == "option_1":
            weight['otterpaw'] = weight['otterpaw'] + 1
        else:
            weight['elkbarrow'] = weight['elkbarrow'] + 1
        return weight, message

    async def timeout_error_message(self, user: disnake.User, message: disnake.Message):
        """
        Sends a customised timeout error message when user does not respond within the timeframe.

        :param user: the user object.
        :param message: the message object.
        """
        await message.delete()
        title = self.content['timeout_error_message']['title']
        description = self.content['timeout_error_message']['desc']
        embed = await self.default_embed(title, description, self.dark_blue)

        await user.send(embed=embed)

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
