import discord
from discord import app_commands
from discord.ext import commands
import os

# --- Загрузка токена ---
# Ищем токен в переменных окружения Bothost
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("❌ ОШИБКА: Токен не найден! Добавьте переменную BOT_TOKEN в настройках Bothost.")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.stored_role = None       # Роль для выдачи
        self.welcome_channel = None   # Канал для приветствий

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Бот успешно запущен, команды синхронизированы.")

bot = MyBot()

# --- Кнопки подтверждения ---
class InviteView(discord.ui.View):
    def __init__(self, role: discord.Role, guild_id: int):
        super().__init__(timeout=None)
        self.role = role
        self.guild_id = guild_id 

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Мгновенный ответ, чтобы Discord не выдал ошибку "Приложение не отвечает"
        await interaction.response.defer(ephemeral=True)

        guild = bot.get_guild(self.guild_id)
        if guild is None:
            await interaction.followup.send("❌ Ошибка: сервер не найден.", ephemeral=True)
            return

        member = guild.get_member(interaction.user.id)
        if member is None:
            await interaction.followup.send("❌ Не удалось найти вас на сервере. Возможно, вы его покинули.", ephemeral=True)
            return

        # Проверка, есть ли уже роль (защита от двойного нажатия)
        if self.role in member.roles:
            await interaction.followup.send(f"Вы уже имеете роль {self.role.mention}.", ephemeral=True)
            return

        try:
            # Выдаем роль
            await member.add_roles(self.role)
            
            # Отправляем сообщение в канал приветствия
            if bot.welcome_channel:
                await bot.welcome_channel.send(f"Приветствую {member.mention}, рады видеть вас в нашей команде!")
            
            await interaction.followup.send(f"✅ Вы получили роль {self.role.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав на выдачу этой роли (проверьте, что роль бота стоит ВЫШЕ выдаваемой в настройках сервера).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при выдаче роли: {e}", ephemeral=True)

        # Отключаем кнопки после нажатия
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass # Игнорируем, если сообщение уже удалено

    @discord.ui.button(label="Отказаться", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("❌ Вы отклонили приглашение.", ephemeral=True)
        
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass


# --- Команда /роли ---
@bot.tree.command(name="роли", description="Установить роль для приглашений")
@app_commands.describe(role="Роль, которая будет выдаваться при согласии")
@app_commands.default_permissions(manage_roles=True)
async def set_role(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    bot.stored_role = role
    await interaction.followup.send(f"✅ Роль для приглашений установлена: {role.mention}", ephemeral=True)


# --- Команда /чатик ---
@bot.tree.command(name="чатик", description="Установить текущий канал для приветствий")
@app_commands.default_permissions(manage_channels=True) 
async def set_channel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    bot.welcome_channel = interaction.channel
    await interaction.followup.send(f"✅ Этот канал ({interaction.channel.mention}) установлен для приветствий.", ephemeral=True)


# --- Команда /пригласить ---
@bot.tree.command(name="пригласить", description="Пригласить участника в команду")
@app_commands.describe(user="Кого приглашаем")
async def invite(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)

    if bot.stored_role is None:
        await interaction.followup.send("❌ Сначала установите роль командой `/роли`.", ephemeral=True)
        return
        
    if bot.welcome_channel is None:
        await interaction.followup.send("❌ Сначала установите канал для приветствий командой `/чатик`.", ephemeral=True)
        return

    if user.bot:
        await interaction.followup.send("❌ Нельзя пригласить бота.", ephemeral=True)
        return

    channel_link = f"https://discord.com/channels/{interaction.guild_id}/{bot.welcome_channel.id}"

    try:
        dm_text = (
            f"Приветствую уважаемый {user.mention}, вас пригласили в команду **Shadow Tester** "
            f"в канале - {channel_link}"
        )
        view = InviteView(role=bot.stored_role, guild_id=interaction.guild_id)
        await user.send(dm_text, view=view)
        await interaction.followup.send(f"✅ Приглашение отправлено пользователю {user.mention} в ЛС.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ Не удалось отправить ЛС пользователю {user.mention}. Возможно, у него закрыты личные сообщения.",
            ephemeral=True
        )


# --- Команда /soo ---
@bot.tree.command(name="soo", description="Написать сообщение от имени бота (только для владельца сервера)")
@app_commands.describe(text="Текст сообщения")
async def say_as_bot(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)

    if interaction.user.id != interaction.guild.owner_id:
        await interaction.followup.send("❌ Только владелец сервера может использовать эту команду.", ephemeral=True)
        return

    try:
        await interaction.message.delete()
    except:
        pass

    await interaction.channel.send(text)


# Запуск бота
bot.run(TOKEN)