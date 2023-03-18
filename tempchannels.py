import disnake
from disnake.ext import commands
from connect_db import db_client
from bson.objectid import ObjectId

import json
import asyncio
import logger

class Tempchannels(commands.Cog):
    """Creates and removes temporary channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Import embed content.
        with open('./embed_content.json', 'r') as f:
            self.content = json.load(f)

    # Setup parent command.
    @commands.slash_command()
    @commands.default_member_permissions(manage_channels=True)
    async def tempchannel(self, inter):
        pass

    @commands.Cog.listener()
    async def on_voice_state_update(self,
        member: disnake.Member,
        before: disnake.VoiceState,
        after: disnake.VoiceState):
        """
        Check if member joined or left a temporary channel.

        Args:
            member (discord.Member): The member that has joined a voice channel.
        """
        guild = member.guild

        # Connect db to check id
        client = await db_client()
        db = client["caretaker"]
        tempchannel_coll = db.tempchannel
        tempchannel_live_coll = db.tempchannel_live

        # Check member left creation channel.
        if before.channel:
            channel = before.channel
            category = channel.category

            query = {"guild_id": f"{guild.id}",
                    "category_id": f"{category.id}",
                    "channel_id": f"{channel.id}"}
            tempchannel_doc = tempchannel_live_coll.find_one(query)

            if tempchannel_doc != None:
                # Check temporary channel population.
                channel_population = len(channel.members)
                if not channel_population:
                    # Remove channel.
                    object_id = tempchannel_doc["_id"]
                    await self.remove_channel(channel, tempchannel_live_coll, object_id)
                    await logger.log(__name__, guild.name, member.name, f"[{channel.name}] deleted as its empty")

        # Check member joined creation channel.
        if after.channel:
            channel = after.channel
            category = channel.category

            query = {"guild_id": f"{guild.id}",
                    "category_id": f"{category.id}",
                    "creation_channel_id": f"{channel.id}"}
            tempchannel_doc = tempchannel_coll.find_one(query)

            if tempchannel_doc == None:
                return

            if str(channel.id) == tempchannel_doc['creation_channel_id']:
                await logger.log(__name__, guild.name, member.name, f"requests a temporary channel")
                default_name = tempchannel_doc['default_name']
                await self.create_temporary_channel(member, category, guild, default_name, tempchannel_live_coll)

    async def create_temporary_channel(self, member: disnake.Member, category: disnake.CategoryChannel,
                                       guild: disnake.Guild, default_name: str, collection):
        """Create a temporary channel."""
        # Create voice channel.
        if "[name]" in default_name:
            default_name = default_name.replace("[name]", member.name)

        if "[count]" in default_name:
            guild_details = {"guild_id": f"{guild.id}",
                             "category_id": f"{category.id}"}
            tempchannel_live_coll = tempchannel_live_coll.find(guild_details)

            total_tempchannels = len(list(tempchannel_live_coll))
            default_name = default_name.replace("[count]", total_tempchannels)

        temporary_channel = await guild.create_voice_channel(name=default_name, category=category)
        await logger.log(__name__, guild.name, member.name, f"channel created [{temporary_channel.name}]")
        # Move member.
        await self.move_member(member, temporary_channel)

        # Store ids in database.
        setup_doc = {
            "guild_id": f"{guild.id}",
            "category_id": f"{category.id}",
            "channel_id": f"{temporary_channel.id}"
        }
        try:
            result = collection.insert_one(setup_doc)
        except Exception:
            return

    # Move member to created channel.
    async def move_member(self, member: disnake.Member, channel: disnake.VoiceChannel):
        """
        Moves member from creation channel to the created temporary channel.

        Args:
            member (disnake.Member): The member object.
            channel (disnake.Member): The voice channel object.
        """
        await member.move_to(channel)
        await logger.log(__name__, channel.guild.name, member.name, f"moved to {channel.name}")

    # Remove temporary channel.
    async def remove_channel(self, channel: disnake.VoiceChannel, collection, object_id):
        """
        Deletes temporary voice channel.

        Args:
            channel (disnake.VoiceChannel): The voice channel object.
        """
        await channel.delete()
        query = { "_id": ObjectId(f"{object_id}")}
        collection.delete_one(query)

    @tempchannel.sub_command(description="Creates a temporary channel")
    async def create(self, inter: disnake.ApplicationCommandInteraction):
        """
        Creates temporary channel.

        Args:
            inter (disnake.ApplicationCommandInteraction): Interaction object.
        """
        guild_id = inter.guild_id
        channel = inter.channel
        member = inter.user

        await logger.log(__name__, inter.guild.name, member.name, "requests to create tempchannel")

        # Import embed content
        with open('./embed_content.json', 'r') as f:
            content = json.load(f)

        # Respond to slash command
        await inter.response.send_message(f"<@{member.id}>")

        # Check if member reached cap, if not create new file.
        client = await db_client()
        db = client["caretaker"]
        tempchannel_coll = db.tempchannel

        guild_details = {"guild_id": f"{guild_id}"}
        tempchannel_doc = tempchannel_coll.find(guild_details)

        total_tempchannels = len(list(tempchannel_doc))

        # Check member donator tier for the cap limit
        guild_coll = db.guild
        guild_doc = guild_coll.find_one(guild_details)

        tier = guild_doc["donation_rank"]

        # Import donation settings
        with open('./donation.json', 'r') as f:
            donation = json.load(f)

        cap_limit = donation[f"{tier}"]["tempchannel_cap"]

        if total_tempchannels >= cap_limit:
            embed = await self.cap_limit_exceeded_embed()
            await channel.send(embed=embed)
            return

        # Create a new document in db
        setup_doc = {
            "guild_id": f"{guild_id}"
        }
        try:
            result = tempchannel_coll.insert_one(setup_doc)
        except Exception:
            return

        object_id = result.inserted_id

        # Save settings for review
        def save_settings(collection, object_id, category, default_name):
            """
            Saves tempchannel settings to presave database for reviews
            interactions.

            Args:
                collection PyMongo: MongoDB collection
                guild_id Int: The guild ID
                category Object: Category object
                default_name String: The channel default name
            """
            query = {"_id": ObjectId(f"{object_id}")}
            settings_doc = {
                            "category_id": f"{category.id}",
                            "default_name": default_name
                            }
            collection.update_one(query, {"$set": settings_doc}, upsert=True)


        def delete_settings(collection, object_id):
            """
            Deletes tempchannel settings from database.

            Args:
                collection PyMongo: MongoDB collection
                document PyMongo: MongoDB document
                guild_id Int: The guild ID
                category Object: Category object
                default_name String: The channel default name
            """
            query = { "_id": ObjectId(f"{object_id}")}
            collection.delete_one(query)

        # Step 1: Send introduction embed
        message = await self.get_member_reaction(channel, member)
        if message == None:
            delete_settings(tempchannel_coll, object_id)
            return

        await message.clear_reactions()
        # Step 2: Ask for channel category id
        category = await self.get_channel_category_id(channel, member, message)
        if category == None:
            delete_settings(tempchannel_coll, object_id)
            return

        # Step 3: Ask for default channel name
        default_name = await self.get_default_channel_name(channel, member, message)
        if default_name == None:
            delete_settings(tempchannel_coll, object_id)
            return

        save_settings(tempchannel_coll, object_id, category, default_name)

        # Step 4: Review all settings
        while True:

            saved_data = tempchannel_coll.find_one({ "_id": ObjectId(f"{object_id}")})

            category_id = saved_data["category_id"]
            default_name = saved_data["default_name"]

            await message.clear_reactions()
            reaction = await self.review_settings(member, message, category_id, default_name)

            if reaction == None:
                delete_settings(tempchannel_coll, object_id)
                return

            elif str(reaction) == "✅":
                await message.clear_reactions()
                break

            elif str(reaction) == "1️⃣": # edit category id
                await message.clear_reactions()
                category = await self.get_channel_category_id(channel, member, message)
                if category == None:
                    delete_settings(tempchannel_coll, object_id)
                    return

                save_settings(tempchannel_coll, object_id, category, default_name)
                continue

            elif str(reaction) == "2️⃣": # edit default name
                await message.clear_reactions()
                default_name = await self.get_default_channel_name(channel, member, message)
                if default_name == None:
                    delete_settings(tempchannel_coll, object_id)
                    return

                save_settings(tempchannel_coll, object_id, category, default_name)
                continue

        # Member confirmed review
        await self.setup_automator(category, message, tempchannel_coll, object_id, member)

    async def review_settings(self, member: disnake.Member, message: disnake.Message, category_id, default_name):
        """
        Gets the review reaction from the member.

        Args:
            channel (disnake.TextChannel): TextChannel object
            member (disnake.Member): Member object
            message (disnake.Message): Message object

        Returns:
            reaction: reaction emoji
        """
        embed = await self.review_settings_embed(category_id, default_name)
        await message.edit(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("1️⃣")
        await message.add_reaction("2️⃣")

        # Check for member reaction
        def check_reaction(reaction, user):
            return user.id == member.id and reaction.message.id == message.id
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check_reaction, timeout=60.0)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            embed = await self.reaction_timeout_embed()
            await message.edit(embed=embed)
            return
        return reaction

    async def get_member_reaction(self, channel: disnake.TextChannel, member: disnake.Member):
        """
        Sends an introduction embed to member.

        Returns:
            message: message object
        """
        embed = await self.introduction_embed()
        message = await channel.send(embed=embed)
        await message.add_reaction("✅")

        # Check for member reaction
        def check_reaction(reaction, user):
            return ((user.id == member.id)
                    and (str(reaction.emoji) == "✅")
                    and (reaction.message.id == message.id))
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check_reaction, timeout=60.0)
        except asyncio.TimeoutError:
            # Timed out embed
            await message.clear_reactions()
            embed = await self.reaction_timeout_embed()
            await message.edit(embed=embed)
            return

        return message

    async def get_channel_category_id(self, channel: disnake.TextChannel, member: disnake.Member,
                                      message: disnake.Message):
        """
        Gets the channel category id from the member.

        Args:
            channel (disnake.TextChannel): TextChannel object
            member (disnake.Member): Member object
            message (disnake.Message): Message object

        Returns:
            category: Category object
        """
        embed = await self.request_categoryid_embed()
        await message.edit(embed=embed)

        tries = 1
        max_tries = 5
        while tries <= max_tries:
            # Check for member message
            def check_message(m: disnake.Message):
                return m.author.id == member.id and m.channel.id == channel.id
            try:
                response: disnake.Message = await self.bot.wait_for('message', check=check_message, timeout=60.0)
            except asyncio.TimeoutError:
                # Timed out embed
                embed = await self.message_timeout_embed()
                await message.edit(embed=embed)
                return
            try:
                response_content = response.content[:]
                await response.delete()
                category = self.bot.get_channel(int(response_content))
            except ValueError:
                embed = await self.categoryid_not_found(tries, max_tries)
                await message.edit(embed=embed)
                tries += 1
                continue
            if category == None or str(category.type) != "category":
                embed = await self.categoryid_not_found(tries, max_tries)
                await message.edit(embed=embed)
                tries += 1
                continue
            else:
                return category

        embed = await self.out_of_tries()
        await message.edit(embed=embed)

    async def get_default_channel_name(self, channel: disnake.TextChannel, member: disnake.Member,
                                       message: disnake.Message):
        """Gets the default channel name from member.

        Args:
            channel (disnake.TextChannel): TextChannel object
            member (disnake.Member): Member object
            message (disnake.Message): Message object
        """
        embed = await self.request_channel_name_embed()
        await message.edit(embed=embed)

        tries = 1
        max_tries = 5
        while tries <= max_tries:
            def check_message(m: disnake.Message):
                return m.author.id == member.id and m.channel.id == channel.id

            try:
                response: disnake.Message = await self.bot.wait_for('message', check=check_message, timeout=60.0)
            except asyncio.TimeoutError:
                embed = await self.message_timeout_embed()
                await message.edit(embed=embed)
                return

            default_name = response.content[:]
            await response.delete()

            char_length = len(default_name)

            if char_length > 25:
                embed = await self.default_name_too_long_embed(tries, max_tries, char_length)
                await message.edit(embed=embed)
                tries += 1
                continue
            else:
                return default_name

        embed = await self.out_of_tries()
        await message.edit(embed=embed)

    async def setup_automator(self, category: disnake.CategoryChannel, message: disnake.Message, collection, object_id, member):
        """
        Sets up the tempchannel:
            Creates the creator channels
            Stores creator channel_id in db
            Sends progressive embeds to channel
        Args:
            category (disnake.CategoryChannel): The category object
            message (disnake.Message): The message object
            collection (PyMongo.collection): db collection
            object_id (int): object id of document
        """
        # Setup 1/5
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][8]['title']}",
            description=f"{self.content['tempchannel_create'][8]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)
        await asyncio.sleep(2)

        # Setup 2/5
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][9]['title']}",
            description=f"{self.content['tempchannel_create'][9]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)
        await asyncio.sleep(2)

        # Setup 3/5
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][10]['title']}",
            description=f"{self.content['tempchannel_create'][10]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)
        creation_channel = await category.create_voice_channel(name="👋 Create channel", bitrate=8000)
        await asyncio.sleep(2)

        # Setup 4/5
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][11]['title']}",
            description=f"{self.content['tempchannel_create'][11]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)
        await asyncio.sleep(2)

        # Setup 5/5
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][12]['title']}",
            description=f"{self.content['tempchannel_create'][12]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)
        await asyncio.sleep(2)

        # Store in database
        query = { "_id": ObjectId(f"{object_id}")}
        add_doc = {
            "creation_channel_id": f"{creation_channel.id}"
        }
        try:
            collection.update_one(query, {"$set": add_doc}, upsert=True)
        except Exception:
            return

        # Process complete
        embed = disnake.Embed(
        title=f"{self.content['tempchannel_create'][13]['title']}",
        description=f"{self.content['tempchannel_create'][13]['description']}\n\n<#{creation_channel.id}>\n\nFeel free to edit the name of the Creation Channel to whatever you fancy. Thanks for using Tempchannels.",
        color=disnake.Colour.green(),
        )
        embed.set_footer(
        text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        await message.edit(embed=embed)

        await logger.log(__name__, category.guild.name, member.name, "created a tempchannel")

    async def introduction_embed(self):
        """
        Sends the first introduction embed for /tempchannel create command.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][1]['title']}",
            description=f"{self.content['tempchannel_create'][1]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def cap_limit_exceeded_embed(self):
        """
        Sends an error cap limit exceeded embed for /tempchannel create command.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][2]['title']}",
            description=f"{self.content['tempchannel_create'][2]['description']}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def request_categoryid_embed(self):
        """
        An embed requesting the member to enter the category channel id.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][3]['title']}",
            description=f"{self.content['tempchannel_create'][3]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def categoryid_not_found(self, tries, max_tries):
        """
        Sends an error embed as channel category is not found.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"({tries}/{max_tries}) {self.content['tempchannel_create'][4]['title']}",
            description=f"{self.content['tempchannel_create'][4]['description']}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def request_channel_name_embed(self):
        """
        Sends an embed requesting the default channel name.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][5]['title']}",
            description=f"{self.content['tempchannel_create'][5]['description']}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed


    async def default_name_too_long_embed(self, tries, max_tries, length):
        """
        Sends an error embed for default name being too long.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"({tries}/{max_tries}) {self.content['tempchannel_create'][6]['title']}",
            description=f"{self.content['tempchannel_create'][6]['description']} `{length}/30` characters.",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def review_settings_embed(self, category_id, default_name):
        """
        Sends an embed to review all member settings.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{self.content['tempchannel_create'][7]['title']}",
            description=f"{self.content['tempchannel_create'][7]['description']}\n1**(1)** > Voice Creation Category <#{category_id}>\n**(2️)** > Default Channel Name > `{default_name}`\n\nComplete the setup by reacting to the tick emoji.",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def reaction_timeout_embed(self):
        """
        Sends an error timed out embed for member not reacting within a certain
        timeframe.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            description=f"{self.content['timeout']['reaction_timeout']['description']}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def message_timeout_embed(self):
        """
        Sends an error timed out embed for member not responding within a
        certain timeframe.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            description=f"{self.content['timeout']['message_timeout']['description']}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def out_of_tries(self):
        """
        Sends an error out of tries embed for member ran out of tries.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            description=f"{self.content['error']['out_of_tries']['description']}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed


    @tempchannel.sub_command(description="Deletes a temporary channel")
    async def delete(self, inter: disnake.ApplicationCommandInteraction):
        """
        Enables member to get a list of active temporary channels and delete them.

        Args:
            inter (disnake.ApplicationCommandInteraction): Interaction object.
        """
        guild = inter.guild
        channel = inter.channel
        member = inter.user

        await inter.response.send_message(f"<@{member.id}>")

        client = await db_client()
        db = client["caretaker"]
        tempchannel_coll = db.tempchannel
        guild_details = {"guild_id": f"{guild.id}"}

        total_doc = 0
        description = ""
        object_id_storage = []

        for doc in tempchannel_coll.find(guild_details):
            description = description + f"**({total_doc})** > <#{doc['creation_channel_id']}>\n"
            object_id_storage.append(doc['_id'])
            total_doc += 1

        if total_doc == 0:
            description = "`None`"
            return

        embed = await self.delete_embed(description)
        message = await channel.send(embed=embed)

        tries = 1
        max_tries = 5
        while tries < max_tries:
            def check_message(m: disnake.Message):
                return m.author.id == member.id and m.channel.id == channel.id
            try:
                response: disnake.Message = await self.bot.wait_for('message', check=check_message, timeout=60.0)
            except asyncio.TimeoutError:
                # Timed out embed
                embed = await self.message_timeout_embed()
                await message.edit(embed=embed)
                return
            try:
                response = int(response.content)
            except Exception:
                embed = await self.tempchannel_not_found_embed(tries, max_tries, description)
                await message.edit(embed=embed)
                tries += 1
                continue

            if response > total_doc:
                embed = await self.tempchannel_not_found_embed(tries, max_tries, description)
                await message.edit(embed=embed)
                tries += 1
                continue

            object_id = object_id_storage[response - 1]
            query = { "_id": ObjectId(f"{object_id}")}
            tempchannel_coll.delete_one(query)

            embed = await self.tempchannel_removed_embed()
            await message.edit(embed=embed)
            return

        await self.out_of_tries()
        return

    async def delete_embed(self, description: str):
        """
        Sends embed regarding tempchannel deletion.

        Returns:
            embed (disnake.Embed): embed object
        """
        embed = disnake.Embed(
            title=f"Delete a temporary channel",
            description=f"Enter the number corresponding to the Temporary channel listed:\n\n{description}",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def tempchannel_not_found_embed(self, tries, max_tries, description):
        """
        Sends an error when user entered deletion number that cannot be found.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"{tries}/{max_tries} Temporary channel not found",
            description=f"Please enter the number corresponding to the temporary channel to delete:\n\n{description}",
            color=disnake.Colour.red(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    async def tempchannel_removed_embed(self):
        """
        Sends sucessful embed for a tempchannel that has been removed.

        Returns:
            embed (disnake.Embed): Embed object.
        """
        embed = disnake.Embed(
            title=f"Temporary channel removed",
            color=disnake.Colour.green(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )
        return embed

    @tempchannel.sub_command(description="Get the tempchannel cap limit in this server")
    async def cap(self, inter: disnake.ApplicationCommandInteraction):
        """
        Sends embed to member of the current cap limit of the server.

        Args:
            inter (disnake.ApplicationCommandInteraction): Interaction object.
        """
        guild = inter.guild
        channel = inter.channel
        member = inter.user

        await inter.response.defer()

            # Check if member reached cap, if not create new file.
        client = await db_client()
        db = client["caretaker"]
        tempchannel_coll = db.tempchannel

        guild_details = {"guild_id": f"{guild.id}"}
        tempchannel_doc = tempchannel_coll.find(guild_details)

        total_tempchannels = len(list(tempchannel_doc))

        # Check member donator tier for the cap limit
        guild_coll = db.guild
        guild_doc = guild_coll.find_one(guild_details)

        tier = guild_doc["donation_rank"]

        # Import donation settings
        with open('./donation.json', 'r') as f:
            donation = json.load(f)

        cap_limit = donation[f"{tier}"]["tempchannel_cap"]

        embed = disnake.Embed(
            title=f"({total_tempchannels}/{cap_limit}) temporary channel slots used",
            color=disnake.Colour.blurple(),
        )
        embed.set_footer(
            text=f"{self.content['tempchannel_create'][0]['version']}",
        )

        await inter.followup.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Tempchannels(bot))
