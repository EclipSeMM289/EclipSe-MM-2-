import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

ID_CANAL_TICKET = 1512267548043776072
ID_CATEGORIA_TICKETS = 1513339617951223869
ID_CARGO_STAFF = 1512269380094787757

COR_ROXA = 0xA020F0
URL_IMAGEM_TICKET = "https://cdn.eclipsebuxx.com/chat/MMEMBED.png"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "?", "+"], intents=intents, help_command=None)


def pegar_emoji(guild, nome, fallback):
    if guild:
        e = discord.utils.get(guild.emojis, name=nome)
        return e if e else fallback
    return fallback


class PainelInternoTicketView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)

        emoji_add = pegar_emoji(guild, "discotoolsxyzicon27", "➕")
        emoji_cancel = pegar_emoji(guild, "discotoolsxyzicon28", "❌")

        self.btn_add = discord.ui.Button(
            label="Adicionar por ID",
            style=discord.ButtonStyle.secondary,
            emoji=emoji_add
        )
        self.btn_add.callback = self.adicionar_id_callback
        self.add_item(self.btn_add)

        self.btn_cancel = discord.ui.Button(
            label="Cancelar Ticket",
            style=discord.ButtonStyle.secondary,
            emoji=emoji_cancel
        )
        self.btn_cancel.callback = self.cancelar_ticket_callback
        self.add_item(self.btn_cancel)

    async def adicionar_id_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Use o sistema de adicionar usuário aqui.",
            ephemeral=True
        )

    async def cancelar_ticket_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🛑 Ticket será fechado em 5 segundos...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()


class TicketDropdown(discord.ui.Select):
    def __init__(self, guild):
        emoji_pix = pegar_emoji(guild, "discotoolsxyzicon25", "🤝")
        emoji_cross = pegar_emoji(guild, "discotoolsxyzicon26", "❌")

        options = [
            discord.SelectOption(
                label="Trade PIX",
                description="Intermediação de pagamento PIX",
                emoji=emoji_pix
            ),
            discord.SelectOption(
                label="Cross Trade",
                description="Indisponível no momento",
                emoji=emoji_cross
            )
        ]

        super().__init__(
            placeholder="Selecione o tipo de transação",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        membro = interaction.user
        escolha = self.values[0]

        if escolha == "Cross Trade":
            await interaction.response.send_message(
                "❌ Esta opção de transação está indisponível no momento.",
                ephemeral=True
            )
            return

        categoria = guild.get_channel(ID_CATEGORIA_TICKETS)
        cargo_staff = guild.get_role(ID_CARGO_STAFF)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            membro: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        if cargo_staff:
            overwrites[cargo_staff] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"🏷️・automático-{membro.name}",
            category=categoria,
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"✅ Seu ticket foi criado em {channel.mention}!",
            ephemeral=True
        )

        emoji_ticket = pegar_emoji(guild, "discotoolsxyzicon2", "🤝")

        embed_interno = discord.Embed(
            title=f"{str(emoji_ticket)}   ━   Middleman de PIX criado.",
            color=COR_ROXA,
            description=(
                "Seja bem vindo ao ticket automático.\n\n"
                "**Passos:**\n"
                "1. Adicione o usuário com quem vai negociar usando o botão abaixo.\n"
                "2. Definam quem envia e quem recebe.\n"
                "3. Informe valor e item.\n"
                "4. Aguarde a staff confirmar."
            )
        )

        msg = await channel.send(
            content=membro.mention,
            embed=embed_interno,
            view=PainelInternoTicketView(guild)
        )

        try:
            await msg.pin()
        except:
            pass


class PainelTicketV2(discord.ui.LayoutView):
    def __init__(self, guild):
        super().__init__(timeout=None)

        emoji_icon = pegar_emoji(guild, "discotoolsxyzicon2", "🤝")

        container = discord.ui.Container(
            accent_color=discord.Color(COR_ROXA)
        )

        container.add_item(
           discord.MediaGalleryItem
                discord.ui.MediaGalleryItem(URL_IMAGEM_TICKET)
            )
        

        container.add_item(
            discord.ui.TextDisplay(
                f"### {str(emoji_icon)}   ━   Solicitar MM"
            )
        )

        container.add_item(
            discord.ui.TextDisplay(
                "> **Taxas Normais**\n"
                "**R$ 1,00** Acima de R$2,50.\n"
                "**R$ 2,15** Acima de R$100.\n"
                "**R$ 4,30** Acima de R$200.\n"
                "**R$ 6,80** Acima de R$400.\n"
                "**1,2%** Acima de R$700.\n\n"
                "Em conta adicionamos **4R$.**"
            )
        )

        row = discord.ui.ActionRow()
        row.add_item(TicketDropdown(guild))
        container.add_item(row)

        self.add_item(container)


@bot.command(name="painel")
async def enviar_painel(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Apenas administradores podem usar.")
        return

    await ctx.channel.purge(limit=20)
    await ctx.send(view=PainelTicketV2(ctx.guild))
    await ctx.send("✅ Painel enviado.", delete_after=5)


@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user}")

    canal = bot.get_channel(ID_CANAL_TICKET)
    if not canal:
        print("❌ Canal de ticket não encontrado.")
        return

    try:
        await canal.purge(limit=100)
    except:
        pass

    await canal.send(view=PainelTicketV2(canal.guild))
    print("✅ Painel de Tickets enviado usando Components V2 real!")


bot.run(TOKEN)
