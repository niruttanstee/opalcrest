import asyncio

import disnake
from disnake.ext import commands

import json


class HouseSort(commands.Cog):
    """Sort members into houses."""

    def __init__(self, bot):
        self.bot: commands.Bot = bot

        with open('./content/house_sort.json', 'r') as f:
            self.content = json.load(f)

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
            description="**(Please check your dms)**",
            colour=disnake.Colour.blue()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        # Send a story-introduction dm
        weights = await self.dm_interaction(user)

    async def dm_interaction(self, user: disnake.User):
        """
        Asks users a number of questions and returns the weighted results.

        :param user: the user object.
        :return weights: the weighted house dictionary.
        """
        # send the introduction dm embed, request member to react to embed to begin
        # send introduction dm embed
        title = self.content['dm_interaction']['introduction']['title']
        description = self.content['dm_interaction']['introduction']['desc']
        embed = disnake.Embed(
            title=title,
            description=description,
            colour=disnake.Colour.blue()
        )
        embed.set_image(url="https://disnake.dev/assets/disnake-thin-banner.png")
        components = [
            disnake.ui.Button(label='Respond: "I am ready"',
                              style=disnake.ButtonStyle.primary,
                              custom_id="accept_introduction")
        ]
        await user.send(embed=embed, components=components)

        def check_dm_intro(x: disnake.MessageInteraction):
            return x.user == user and x.component.custom_id == "accept_introduction"

        try:
            x = await self.bot.wait_for('button_click', timeout=60, check=check_dm_intro)
        except asyncio.TimeoutError:
            await user.send("Timed out")
            return

        await x.response.send_message('You responded with "I am ready"', ephemeral=True)

        # send the first question and await reaction, add weights
        # send the second question and await reaction, add weights
        # send the third question and await reaction, add weights
        # send the fourth question and await reaction, add weights
        # send the closing embed guiding user back to server_guide channel
        # return the weighed results


def setup(bot: commands.Bot):
    bot.add_cog(HouseSort(bot))
