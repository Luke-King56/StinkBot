import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json

# Retrieve the token from environment variables
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise ValueError("No token found in environment variables. Please set the 'TOKEN' environment variable.")

# Ensure the intents include members to count them
intents = discord.Intents.default()
intents.members = True

# Create an instance of the bot with the specified intents
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot is up")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.tree.command(name="members")
async def members(interaction: discord.Interaction):
    await interaction.response.send_message(f"Users: {interaction.guild.member_count}")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    latency = bot.latency * 1000
    await interaction.response.send_message(f"Pong! Latency is {latency:.2f}ms")

@bot.tree.command(name="userinfo")
async def userinfo(interaction: discord.Interaction, user: discord.User):
    embed = discord.Embed(title=f"User Info - {user.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=user.avatar.url)
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="Discriminator", value=user.discriminator, inline=True)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Bot", value=user.bot, inline=True)
    embed.add_field(name="Created At", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Server Name", value=guild.name, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner, inline=True)
    embed.add_field(name="Member Count", value=guild.member_count, inline=True)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userstats")
async def userstats(interaction: discord.Interaction, user: discord.User):
    stats = user_stats.get(user.id, {"messages": 0})
    await interaction.response.send_message(f"{user.name} has sent {stats['messages']} messages.")

@bot.tree.command(name="addcommand")
async def addcommand(interaction: discord.Interaction, command_name: str, response: str):
    custom_commands[command_name] = response
    with open("custom_commands.json", "w") as f:
        json.dump(custom_commands, f)
    await interaction.response.send_message(f"Custom command '{command_name}' added.")

@bot.tree.command(name="usecommand")
async def usecommand(interaction: discord.Interaction, command_name: str):
    response = custom_commands.get(command_name, "Command not found.")
    await interaction.response.send_message(response)

@bot.tree.command(name="setchannel")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    settings['scheduled_channel_id'] = channel.id
    with open("settings.json", "w") as f:
        json.dump(settings, f)
    await interaction.response.send_message(f"Scheduled messages will be sent to {channel.mention}")

def evaluate_expression(expression):
    try:
        result = eval(expression, {"__builtins__": None}, {})
        if isinstance(result, (int, float)) and result >= 0:
            return result
        else:
            return None
    except:
        return None

@bot.tree.command(name="setschedule")
async def setschedule(interaction: discord.Interaction, message_content: str, interval_expression: str, embed: bool = False, include_info: bool = False):
    interval_seconds = evaluate_expression(interval_expression)
    if interval_seconds is None:
        await interaction.response.send_message("Invalid interval expression. Please use a valid mathematical expression.")
        return
    
    settings['scheduled_message'] = {
        'content': message_content,
        'embed': embed,
        'include_info': include_info
    }
    settings['scheduled_interval'] = interval_seconds
    with open("settings.json", "w") as f:
        json.dump(settings, f)
    
    scheduled_message.change_interval(seconds=interval_seconds)
    await interaction.response.send_message(f"Scheduled message set with an interval of {interval_seconds} second(s).")

@bot.tree.command(name="purge")
async def purge(interaction: discord.Interaction, type: str = None, count: int = None):
    if type == "commands" or type is None:
        if count:
            to_delete = list(custom_commands.keys())[:count]
            for cmd in to_delete:
                del custom_commands[cmd]
        else:
            custom_commands.clear()
        with open("custom_commands.json", "w") as f:
            json.dump(custom_commands, f)

    if type == "userstats" or type is None:
        if count:
            to_delete = list(user_stats.keys())[:count]
            for user_id in to_delete:
                del user_stats[user_id]
        else:
            user_stats.clear()
    
    if type == "settings" or type is None:
        settings.pop('scheduled_message', None)
        settings.pop('scheduled_channel_id', None)
        settings.pop('scheduled_interval', None)
        with open("settings.json", "w") as f:
            json.dump(settings, f)
    
    if type == "messages" or type is None:
        await interaction.channel.purge()
        await interaction.response.send_message(f"Purged all messages from {interaction.channel.mention}.")

    await interaction.response.send_message(f"Purged {type if type else 'all data'}.")

@bot.tree.command(name="purge_messages")
async def purge_messages(interaction: discord.Interaction, channel: discord.TextChannel, number: int = None):
    if number is None:
        await channel.purge()
        await interaction.response.send_message(f"Purged all messages from {channel.mention}.")
    else:
        await channel.purge(limit=number)
        await interaction.response.send_message(f"Purged {number} messages from {channel.mention}.")

@tasks.loop(seconds=1)
async def scheduled_message():
    if 'scheduled_channel_id' in settings:
        channel_id = settings['scheduled_channel_id']
        channel = bot.get_channel(channel_id)
        if channel:
            message_data = settings.get('scheduled_message', {"content": "No message set.", "embed": False, "include_info": False})
            message_content = message_data.get('content', "No message set.")
            
            if message_data.get('include_info', False):
                member_count = channel.guild.member_count
                message_content = message_content.replace("{member_count}", str(member_count))
            
            if message_data.get('embed', False):
                embed = discord.Embed(description=message_content, color=discord.Color.blue())
                if message_data.get('include_info', False):
                    embed.set_footer(text=f"Members: {member_count}")
                await channel.send(embed=embed)
            else:
                await channel.send(message_content)
        else:
            print(f"Channel ID {channel_id} not found.")
    else:
        print("Scheduled channel ID not set.")

# Run the bot with the specified token
bot.run(TOKEN)
