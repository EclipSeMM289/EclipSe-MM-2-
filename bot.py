import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
import asyncio
import sqlite3
import os
from dotenv import load_dotenv

# ==========================================
# 🔐 CARREGAMENTO E VALIDAÇÃO DO TOKEN
# ==========================================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError(
        "❌ ERRO: O token do Discord não foi encontrado!\n"
        "Verifique se o seu arquivo '.env' está na mesma pasta do bot "
        "ou se a variável 'DISCORD_TOKEN' foi passada nas configurações do seu container/Docker."
    )

# ==========================================
# 📥 CONFIGURAÇÃO DE CANAIS E CARGOS
# ==========================================
ID_CANAL_TICKET = 1512267548043776072
ID_CANAL_FAQ = 1512267542461157536
ID_CANAL_RANKS = 1512267543643951124  
ID_CANAL_VOUCH = 1512267549901983867     
ID_CANAL_BIGVOUCH = 1512267551927963748  

ID_CARGO_STAFF = 1512269380094787757
ID_CARGO_RECUPERACAO = 1513703148936499381  
ID_MM_FIXO = 1510480019640553482

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "?", "+"], intents=intents, help_command=None)

COR_ROXA = 0xA020F0
parar_envio = False
bot_inicializado = False  
DADOS_TICKETS = {}

LISTA_NOMES_CARGOS = [
    "Trader Bronze", "Trader Prata", "Trader Ouro", "Trader Diamante", 
    "Trader Ametista", "Trader Esmeralda", "Trader Rubi", "Trader Sáfira", 
    "Trader Master", "Trader Obsidian", "Biggest Trader", "OldBigger", "🏆 ・ Top Trader"
]

IDS_REAIS = [
    1417022267044659241, 1499270758193565746, 693820829624172634, 1467296921159729427, 
    1503750281119268914, 1471499431743328410, 1266258591925669899, 1478220355285028984, 
    1445740601294192681, 1231978312302334053, 646482083992043540, 1320940616393429094, 
    991405470432645211, 773848930345680916, 1144229988771442749, 1022349948834529321
]

for _ in range(100):
    IDS_REAIS.append(random.randint(100000000000000000, 999999999999999999))

# ==========================================
# 🗄️ SISTEMA DE BANCO DE DADOS (SQLITE)
# ==========================================
def inicializar_banco():
    conn = sqlite3.connect("database_ranks.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            total_movimentado REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

inicializar_banco()

def obter_saldo(user_id: int) -> float:
    conn = sqlite3.connect("database_ranks.db")
    cursor = conn.cursor()
    cursor.execute("SELECT total_movimentado FROM usuarios WHERE user_id = ?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0.0

def adicionar_saldo(user_id: int, valor: float) -> float:
    conn = sqlite3.connect("database_ranks.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO usuarios (user_id, total_movimentado) VALUES (?, 0.0)", (user_id,))
    cursor.execute("UPDATE usuarios SET total_movimentado = total_movimentado + ? WHERE user_id = ?", (valor, user_id))
    conn.commit()
    
    cursor.execute("SELECT total_movimentado FROM usuarios WHERE user_id = ?", (user_id,))
    novo_saldo = cursor.fetchone()[0]
    conn.close()
    return novo_saldo

# ==========================================
# 🛠️ FUNÇÕES UTILITÁRIAS
# ==========================================
def pegar_emoji(guild, nome, fallback):
    if guild:
        e = discord.utils.get(guild.emojis, name=nome)
        return e if e else fallback
    return fallback

def calcular_taxa(valor: float) -> float:
    if valor <= 2.50: return 0.00
    elif valor <= 100.00: return 1.00
    elif valor <= 200.00: return 2.15
    elif valor <= 400.00: return 4.30
    elif valor <= 700.00: return 6.80
    else: return valor * 0.012

def formatar_valor(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def check_preservar_sistema(m): 
    return not m.pinned and m.type != discord.MessageType.pins_add

async def verificar_e_atualizar_rank(membro: discord.Member, canal_notificacao):
    saldo = obter_saldo(membro.id)
    guild = membro.guild
    
    config_ranks = [
        (400000.0, "Trader Obsidian"),
        (200000.0, "Trader Master"),
        (100000.0, "Trader Sáfira"),
        (50000.0, "Trader Rubi"),
        (25000.0, "Trader Esmeralda"),
        (10000.0, "Trader Ametista"),
        (5000.0, "Trader Diamante"),
        (1000.0, "Trader Ouro"),
        (500.0, "Trader Prata"),
        (0.01, "Trader Bronze")
    ]
    
    cargo_alvo_nome = None
    for limite, nome_cargo in config_ranks:
        if saldo >= limite:
            cargo_alvo_nome = nome_cargo
            break
            
    if not cargo_alvo_nome:
        return

    cargo_alvo = discord.utils.get(guild.roles, name=cargo_alvo_nome)
    if cargo_alvo and cargo_alvo not in membro.roles:
        try:
            cargos_para_remover = [discord.utils.get(guild.roles, name=n) for _, n in config_ranks if n != cargo_alvo_nome]
            for c in cargos_para_remover:
                if c and c in membro.roles:
                    await membro.remove_roles(c)
            
            await membro.add_roles(cargo_alvo)
            
            emoji_up = pegar_emoji(guild, "discotoolsxyzicon2", "⭐")
            embed_up = discord.Embed(
                title=f"{str(emoji_up)} RANK UP AUTOMÁTICO!",
                description=f"🎉 {membro.mention} alcançou o total acumulado de **{formatar_valor(saldo)}** in-game e subiu para o cargo **{cargo_alvo.mention}**!",
                color=COR_ROXA
            )
            await canal_notificacao.send(embed=embed_up)
        except Exception as e:
            print(f"Erro ao atualizar cargo de {membro.name}: {e}")

# ==========================================
# 💎 INTERFACES GRÁFICAS DE TICKETS (VIEWS / MODALS)
# ==========================================
class ResgatarPlacaView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        emoji_placa = pegar_emoji(guild, "discotoolsxyzicon2", "⚙️")
        
        self.btn_resgatar = discord.ui.Button(
            label="Resgatar placa.", 
            style=discord.ButtonStyle.secondary, 
            emoji=emoji_placa,
            custom_id="persistent_resgatar_placa"
        )
        self.btn_resgatar.callback = self.resgatar_placa_callback
        self.add_item(self.btn_resgatar)

    async def resgatar_placa_callback(self, interaction: discord.Interaction):
        saldo_atual = obter_saldo(interaction.user.id)
        
        if saldo_atual >= 100000.0:
            await interaction.response.send_message(
                f"📌 **Solicitação validada!** Você possui `{formatar_valor(saldo_atual)}` em movimentações históricas. A Staff foi notificada e dará início ao processo de confecção da sua placa física.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ **Acesso Negado!** Você possui atualmente apenas `{formatar_valor(saldo_atual)}` acumulados. É necessário ter pelo menos **R$ 100.000,00** (Trader Sáfira) para solicitar uma placa física.", 
                ephemeral=True
            )

class ConfigurarDadosPixModal(discord.ui.Modal, title="Configurar PIX do Middleman"):
    def __init__(self, ticket_id):
        super().__init__()
        self.ticket_id = ticket_id
        
        self.chave_input = discord.ui.TextInput(
            label="Chave PIX (Copia e Cola)",
            placeholder="Cole o código do copia e cola ou chave aqui...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.chave_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.ticket_id in DADOS_TICKETS:
            DADOS_TICKETS[self.ticket_id]["chave_pix"] = self.chave_input.value
            await atualizar_painel_negociacao(interaction, self.ticket_id)

class PainelPosPagamentoView(discord.ui.View):
    def __init__(self, guild, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        emoji_confirma = pegar_emoji(guild, "discotoolsxyzicon2", "🤝")
        
        self.btn_confirmar_recebimento = discord.ui.Button(
            label="Confirmar Recebimento (PIX)", 
            style=discord.ButtonStyle.primary, 
            emoji=emoji_confirma
        )
        self.btn_confirmar_recebimento.callback = self.confirmar_recebimento_callback
        self.add_item(self.btn_confirmar_recebimento)

    async def confirmar_recebimento_callback(self, interaction: discord.Interaction):
        if not any(role.id == ID_CARGO_STAFF for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas membros da Staff podem confirmar o recebimento.", ephemeral=True)
            return

        dados = DADOS_TICKETS.get(self.ticket_id)
        if not dados:
            await interaction.response.send_message("❌ Erro: Dados da transação não localizados na memória do bot.", ephemeral=True)
            return

        try: await interaction.channel.purge(limit=100, check=check_preservar_sistema)
        except: pass

        emoji_sucesso = pegar_emoji(interaction.guild, "discotoolsxyzicon2", "⚙️")
        embed_recebido = discord.Embed(
            title=f"{str(emoji_sucesso)} Pagamento Confirmado!",
            description=(
                "🎯 **O valor via PIX foi recebido e validado com sucesso na conta do Middleman.**\n\n"
                "📦 **Próximo Passo:**\n"
                "O **Vendedor (Recebedor)** já pode realizar a entrega dos itens/serviço com total segurança.\n\n"
                "⚠️ *Não saiam do ticket. Assim que a entrega for feita e o comprador confirmar que deu tudo certo, a Staff fará o repasse final.*"
            ),
            color=COR_ROXA
        )
        await interaction.channel.send(embed=embed_recebido)

        valor_da_troca = dados["valor_original"]
        enviador_membro = interaction.guild.get_member(dados["enviador_id"])
        recebedor_membro = interaction.guild.get_member(dados["recebedor_id"])
        
        if enviador_membro:
            adicionar_saldo(enviador_membro.id, valor_da_troca)
            await verificar_e_atualizar_rank(enviador_membro, interaction.channel)
            
        if recebedor_membro:
            adicionar_saldo(recebedor_membro.id, valor_da_troca)
            await verificar_e_atualizar_rank(recebedor_membro, interaction.channel)

class PainelConfiguracaoStaffView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="Definir Chave PIX", style=discord.ButtonStyle.secondary, emoji="📝", row=0)
    async def definir_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ID_CARGO_STAFF for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas a Staff/Middleman pode configurar o PIX.", ephemeral=True)
            return
        await interaction.response.send_modal(ConfigurarDadosPixModal(self.ticket_id))

    @discord.ui.button(label="Confirmar Dados da Troca", style=discord.ButtonStyle.secondary, emoji="🤝", row=0)
    async def confirmar_dados_unico(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ticket_id not in DADOS_TICKETS:
            await interaction.response.send_message("❌ Dados do ticket não encontrados. Reinicie o processo.", ephemeral=True)
            return
            
        dados = DADOS_TICKETS[self.ticket_id]
        user_id = interaction.user.id

        if user_id != dados["enviador_id"] and user_id != dados["recebedor_id"]:
            await interaction.response.send_message("❌ Apenas os participantes da troca podem confirmar os dados.", ephemeral=True)
            return

        emoji_check = pegar_emoji(interaction.guild, "discotoolsxyzicon2", "⚙️")

        if user_id == dados["enviador_id"]:
            dados["confirmado_enviador"] = True
            await interaction.response.send_message(f"{str(emoji_check)} Você (Enviador) confirmou os dados com sucesso!", ephemeral=True)
        elif user_id == dados["recebedor_id"]:
            dados["confirmado_recebedor"] = True
            await interaction.response.send_message(f"{str(emoji_check)} Você (Recebedor) confirmou os dados com sucesso!", ephemeral=True)

        await atualizar_painel_negociacao(interaction, self.ticket_id, edit_original=True)

    @discord.ui.button(label="Gerar PIX e Copia e Cola", style=discord.ButtonStyle.primary, emoji="⚡", row=1)
    async def gerar_pix_final(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ID_CARGO_STAFF for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas membros da Staff/Middleman podem liberar o PIX.", ephemeral=True)
            return

        dados = DADOS_TICKETS[self.ticket_id]
        if not dados["chave_pix"]:
            await interaction.response.send_message("❌ Você precisa definir a Chave PIX primeiro no botão 'Definir Chave PIX'!", ephemeral=True)
            return

        if not dados["confirmado_enviador"] or not dados["confirmado_recebedor"]:
            await interaction.response.send_message("❌ **Bloqueado!** Ambos os clientes precisam clicar no botão de confirmação primeiro.", ephemeral=True)
            return

        tres_crases = chr(96) * 3
        texto_copia_cola = f"{tres_crases}text\n{dados['chave_pix']}\n{tres_crases}"
        valor_formatated = formatar_valor(dados["valor_total"])

        embed_cliente = discord.Embed(
            title="⚡ Pagamento Gerado com Sucesso!",
            description=(
                f"Efetue o pagamento do valor exato abaixo para dar prosseguimento ao seu atendimento.\n\n"
                f"💰 **Valor Total:** `{valor_formatated}`\n\n"
                f"📋 **PIX Copia e Cola:**\n{texto_copia_cola}\n\n"
                f"⚠️ **Aviso:** Assim que realizar a transferência, envie o **comprovante original** aqui no chat e a Staff confirmará no botão abaixo."
            ),
            color=COR_ROXA
        )
        
        await interaction.response.send_message("⚡ Gerando cobrança PIX...", ephemeral=True)
        try: await interaction.channel.purge(limit=100, check=check_preservar_sistema)
        except: pass

        await interaction.channel.send(embed=embed_cliente, view=PainelPosPagamentoView(interaction.guild, self.ticket_id))

async def atualizar_painel_negociacao(interaction, ticket_id, edit_original=False):
    dados = DADOS_TICKETS[ticket_id]
    emoji_status = pegar_emoji(interaction.guild, "discotoolsxyzicon2", "⚙️")
    
    status_enviador = f"{str(emoji_status)} Confirmado" if dados["confirmado_enviador"] else "⏳ Aguardando..."
    status_recebedor = f"{str(emoji_status)} Confirmado" if dados["confirmado_recebedor"] else "⏳ Aguardando..."
    status_pix = "🟪 Configurada (Oculta até a liberação)" if dados["chave_pix"] else "❌ Não configurada"

    embed_atualizado = discord.Embed(
        title="⚙️ Painel de Ajustes e Confirmações",
        description=(
            f"Ambos os clientes precisam clicar no botão de confirmação para liberar a transação.\n\n"
            f"👤 **Enviador:** <@{dados['enviador_id']}> — **Status:** {status_enviador}\n"
            f"🎁 **Recebedor:** <@{dados['recebedor_id']}> — **Status:** {status_recebedor}\n\n"
            f"💲 **Valor Base:** {formatar_valor(dados['valor_original'])}\n"
            f"💎 **Taxa Middleman:** {formatar_valor(dados['taxa'])}\n"
            f"💰 **Total Cobrado:** `{formatar_valor(dados['valor_total'])}`\n"
            f"📦 **Itens/Serviço:** {dados['item']}\n\n"
            f"📋 **Chave PIX (MM):** {status_pix}\n\n"
            f"🚀 **Pronto para liberar?**\n"
            f"Quando tudo estiver preenchido e os dois clientes tiverem clicado em confirmar, o Middleman deve clicar em **'Gerar PIX e Copia e Cola'**."
        ),
        color=COR_ROXA
    )

    if edit_original:
        await interaction.message.edit(embed=embed_atualizado, view=PainelConfiguracaoStaffView(ticket_id))
    else:
        await interaction.response.edit_message(embed=embed_atualizado, view=PainelConfiguracaoStaffView(ticket_id))

class SelecaoFuncoesView(discord.ui.View):
    def __init__(self, guild, enviador=None, recebedor=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.enviador = enviador
        self.recebedor = recebedor

        emoji_dinheiro = pegar_emoji(guild, "discotoolsxyzicon31", "💲")
        emoji_presente = pegar_emoji(guild, "discotoolsxyzicon29", "🎁")
        emoji_resetar = pegar_emoji(guild, "discotoolsxyzicon30", "🔄")

        self.btn_enviar = discord.ui.Button(label="Vou enviar o Pix", style=discord.ButtonStyle.secondary, emoji=emoji_dinheiro)
        self.btn_enviar.callback = self.enviar_pix_callback
        self.add_item(self.btn_enviar)

        self.btn_receber = discord.ui.Button(label="Vou Receber", style=discord.ButtonStyle.secondary, emoji=emoji_presente)
        self.btn_receber.callback = self.receber_pix_callback
        self.add_item(self.btn_receber)

        self.btn_resetar = discord.ui.Button(label="Resetar", style=discord.ButtonStyle.secondary, emoji=emoji_resetar)
        self.btn_resetar.callback = self.resetar_callback
        self.add_item(self.btn_resetar)

    def gerar_embed(self):
        emoji_titulo = pegar_emoji(self.guild, "discotoolsxyzicon2", "🤝")
        emoji_lista = pegar_emoji(self.guild, "discotoolsxyzicon31", "💲")
        
        embed = discord.Embed(title=f"{str(emoji_titulo)}   ━   Seleção de Funções", color=COR_ROXA)
        txt_enviador = f"<@{self.enviador.id}>" if self.enviador else "Aguardando..."
        txt_recebedor = f"<@{self.recebedor.id}>" if self.recebedor else "Aguardando..."

        embed.description = (
            "Agora vocês vão confirmar a função de vocês, ou seja, quem vai enviar o pix para o MM, e "
            "quem depois da troca, irá receber o PIX do MM.\n\n"
            f"• {str(emoji_lista)} **Vou enviar o pix** — Você vai enviar o PIX para o middleman.\n"
            f"• 🎁 **Vou receber** — Você vai receber o PIX do middleman.\n\n"
            f"**Enviador:** {txt_enviador}\n"
            f"**Recebedor:** {txt_recebedor}"
        )
        return embed

    async def verificar_proximo_passo(self, interaction: discord.Interaction):
        if self.enviador and self.recebedor:
            await interaction.response.send_message("🔄 Funções definidas! Avançando para definição de valores...", ephemeral=True)
            try: await interaction.channel.purge(limit=100, check=check_preservar_sistema)
            except: pass
            asyncio.create_task(self.fluxo_definir_valor(interaction.channel))
        else:
            await interaction.response.edit_message(embed=self.gerar_embed(), view=self)

    async def enviar_pix_callback(self, interaction: discord.Interaction):
        if self.enviador is not None and self.enviador != interaction.user:
            await interaction.response.send_message("❌ Esta função já foi selecionada pelo outro participante!", ephemeral=True)
            return
        if self.recebedor == interaction.user: 
            self.recebedor = None
        self.enviador = interaction.user
        await self.verificar_proximo_passo(interaction)

    async def receber_pix_callback(self, interaction: discord.Interaction):
        if self.recebedor is not None and self.recebedor != interaction.user:
            await interaction.response.send_message("❌ Esta função já foi selecionada pelo outro participante!", ephemeral=True)
            return
        if self.enviador == interaction.user: 
            self.enviador = None
        self.recebedor = interaction.user
        await self.verificar_proximo_passo(interaction)

    async def resetar_callback(self, interaction: discord.Interaction):
        is_staff = any(role.id == ID_CARGO_STAFF for role in interaction.user.roles)
        is_participant = (self.enviador == interaction.user or self.recebedor == interaction.user)
        
        if not is_participant and not is_staff:
            await interaction.response.send_message("❌ Você não faz parte desta negociação para resetar as funções.", ephemeral=True)
            return

        self.enviador = None
        self.recebedor = None
        await interaction.response.edit_message(embed=self.gerar_embed(), view=self)

    async def fluxo_definir_valor(self, channel):
        emoji_valor = pegar_emoji(self.guild, "discotoolsxyzicon32", "➖")
        embed = discord.Embed(
            title=f"{str(emoji_valor)}   ━   Definir Valor",
            color=COR_ROXA,
            description=f"{self.enviador.mention}\nInforme o valor do pix no chat.\nExemplo: `50.00`"
        )
        await channel.send(embed=embed)

        def check_valor(m): return m.author == self.enviador and m.channel == channel

        while True:
            try:
                msg = await bot.wait_for('message', check=check_valor, timeout=300)
                conteudo = msg.content.replace(",", ".")
                try:
                    valor = float(conteudo)
                    if valor <= 0: raise ValueError
                    
                    try: await channel.purge(limit=100, check=check_preservar_sistema)
                    except: pass
                    
                    asyncio.create_task(self.fluxo_definir_item(channel, valor))
                    break
                except ValueError:
                    await channel.send("❌ **Valor inválido!** Insira apenas números. Exemplo: `50.00`", delete_after=4)
                    try: await msg.delete()
                    except: pass
            except asyncio.TimeoutError:
                await channel.send("🛑 **Tempo limite excedido!** O ticket expirou por inatividade e será fechado.")
                await asyncio.sleep(5)
                await channel.delete()
                break

    async def fluxo_definir_item(self, channel, valor_definido):
        emoji_item = pegar_emoji(self.guild, "discotoolsxyzicon32", "➖")
        embed = discord.Embed(
            title=f"{str(emoji_item)}   ━   Definir Item",
            color=COR_ROXA,
            description=f"{self.recebedor.mention}\nRegistre o produto/item/serviço da troca digitando no chat.\nExemplo: `5000 Robux`"
        )
        await channel.send(embed=embed)

        def check_item(m): return m.author == self.recebedor and m.channel == channel

        try:
            msg = await bot.wait_for('message', check=check_item, timeout=300)
            item_definido = msg.content
            
            try: await channel.purge(limit=100, check=check_preservar_sistema)
            except: pass
            
            taxa = calcular_taxa(valor_definido)
            valor_total = valor_definido + taxa

            DADOS_TICKETS[channel.id] = {
                "enviador_id": self.enviador.id,
                "recebedor_id": self.recebedor.id,
                "valor_original": valor_definido,
                "taxa": taxa,
                "valor_total": valor_total,
                "item": item_definido,
                "chave_pix": None,
                "confirmado_enviador": False,
                "confirmado_recebedor": False
            }

            embed_setup_staff = discord.Embed(
                title="⚙️ Painel de Ajustes e Confirmações",
                description=(
                    f"Ambos os clientes precisam clicar no botão de confirmação para liberar a transação.\n\n"
                    f"👤 **Enviador:** {self.enviador.mention} — **Status:** ⏳ Aguardando...\n"
                    f"🎁 **Recebedor:** {self.recebedor.mention} — **Status:** ⏳ Aguardando...\n\n"
                    f"💲 **Valor Base:** {formatar_valor(valor_definido)}\n"
                    f"💎 **Taxa Middleman:** {formatar_valor(taxa)}\n"
                    f"💰 **Total Cobrado:** `{formatar_valor(valor_total)}`\n"
                    f"📦 **Itens/Serviço:** {item_definido}\n\n"
                    f"📋 **Chave PIX (MM):** ❌ Não configurada\n\n"
                    f"🚀 **Pronto para liberar?**\n"
                    f"Quando tudo estiver preenchido e os dois clientes tiverem clicado em confirmar, o Middleman deve clicar em **'Gerar PIX e Copia e Cola'**."
                ),
                color=COR_ROXA
            )
            await channel.send(embed=embed_setup_staff, view=PainelConfiguracaoStaffView(channel.id))
        except asyncio.TimeoutError:
            await channel.send("🛑 **Tempo limite excedido!** O ticket expirou por inatividade e será fechado.")
            await asyncio.sleep(5)
            await channel.delete()

class AdicionarIDModal(discord.ui.Modal, title="Adicionar Usuário por ID"):
    id_input = discord.ui.TextInput(label="ID do Usuário", placeholder="Cole o ID do outro participante aqui...", min_length=15, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.id_input.value)
            membro_adicionar = await interaction.guild.fetch_member(user_id)
            if membro_adicionar:
                await interaction.channel.set_permissions(membro_adicionar, read_messages=True, send_messages=True)
                await interaction.response.send_message("🔄 Adicionando usuário e atualizando canal...", ephemeral=True)
                
                try: await interaction.channel.purge(limit=100, check=check_preservar_sistema)
                except: pass
                
                view_funcoes = SelecaoFuncoesView(interaction.guild)
                mencoes = f"{interaction.user.mention} {membro_adicionar.mention}"
                await interaction.channel.send(content=mencoes, embed=view_funcoes.gerar_embed(), view=view_funcoes)
            else:
                await interaction.response.send_message("❌ Usuário não encontrado neste servidor.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ ID inválido. Insira apenas números.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Não foi possível adicionar o usuário: {e}", ephemeral=True)

class PainelInternoTicketView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        emoji_add = pegar_emoji(guild, "discotoolsxyzicon27", "➕")
        emoji_cancel = pegar_emoji(guild, "discotoolsxyzicon28", "❌")
        
        self.btn_add = discord.ui.Button(label="Adicionar por ID", style=discord.ButtonStyle.secondary, emoji=emoji_add)
        self.btn_add.callback = self.adicionar_id_callback
        self.add_item(self.btn_add)
        
        self.btn_cancel = discord.ui.Button(label="Cancelar Ticket", style=discord.ButtonStyle.secondary, emoji=emoji_cancel)
        self.btn_cancel.callback = self.cancelar_ticket_callback
        self.add_item(self.btn_cancel)

    async def adicionar_id_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AdicionarIDModal())

    async def cancelar_ticket_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🛑 **Este ticket será fechado e deletado em 5 seconds...**")
        await asyncio.sleep(5)
        DADOS_TICKETS.pop(interaction.channel.id, None)
        await interaction.channel.delete()

class TicketDropdown(discord.ui.Select):
    def __init__(self, guild):
        emoji_pix = pegar_emoji(guild, "discotoolsxyzicon25", "🤝")
        emoji_cross = pegar_emoji(guild, "discotoolsxyzicon26", "❌")
        options = [
            discord.SelectOption(label="Trade PIX", description="Intermediação de pagamento PIX", emoji=emoji_pix),
            discord.SelectOption(label="Cross Trade", description="Indisponível no momento", emoji=emoji_cross)
        ]
        super().__init__(placeholder="Selecione o tipo de transação", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        membro = interaction.user
        escolha = self.values[0]

        if escolha == "Cross Trade":
            await interaction.response.send_message("❌ Esta opção de transação está indisponível no momento.", ephemeral=True)
            return
        
        cargo_staff = guild.get_role(ID_CARGO_STAFF)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            membro: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if cargo_staff:
            overwrites[cargo_staff] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        nome_canal = f"🏷️・automático {membro.name}"
        channel = await guild.create_text_channel(name=nome_canal, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Seu ticket foi criado em {channel.mention}!", ephemeral=True)
        
        emoji_ticket = pegar_emoji(guild, "discotoolsxyzicon2", "🤝")
        embed_interno = discord.Embed(title=f"{str(emoji_ticket)}   ━   Middleman de PIX criado.", color=COR_ROXA)
        embed_interno.description = (
            "Seja bem vindo ao novo ticket **AUTOMÁTICO** de MiddleMan, com segurança e agilidade. É "
            "importante que você selecione as opções ao longo do ticket corretamente e responda as "
            "perguntas que o bot fizer. Reveja sempre antes de prosseguir qualquer passo para evitar "
            "scams e erros.\n\n"
            "**Passos:**\n"
            "1. Adicione o usuário com quem vai negociar usando o botão abaixo.\n"
            "2. O bot abrirá a seleção de quem envia e recebe o PIX.\n"
            "3. O bot pedirá para descreverem o valor e os itens no chat.\n"
            "4. Após confirmação, o pix seguro é gerado."
        )
        msg_sistema = await channel.send(content=membro.mention, embed=embed_interno, view=PainelInternoTicketView(guild))
        
        try: await msg_sistema.pin()
        except: pass

class TicketView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(guild))

# ==========================================
# 👤 COMANDOS PÚBLICOS / GERAIS
# ==========================================
@bot.command(name="comandos")
async def comandos_servidor(ctx):
    embed_ajuda = discord.Embed(
        title="📋 Lista de Comandos do Servidor",
        description="Esta mensagem e a solicitação serão deletadas automaticamente em **1 minuto**.",
        color=COR_ROXA
    )
    
    embed_ajuda.add_field(
        name="👤 Comandos de Usuários",
        value=(
            "`?comandos` - Mostra esta lista de ajuda.\n"
            "`?perfil` - Mostra seu saldo acumulado e estatísticas de trade.\n"
            "`?perfil @membro` - Consulta o volume total de trades de outro usuário."
        ),
        inline=False
    )

    embed_ajuda.add_field(
        name="👑 Comandos da Staff",
        value=(
            "`?enviarpainel` - Atualiza e envia o painel de ranks com o botão de placas.\n"
            "`?hit` - Gera o painel de suporte contra scam/recuperação.\n"
            "`+desmute @membro` - Remove o castigo/timeout de um usuário.\n"
            "`?funcoes` - Força a inicialização imediata do painel de seleção no chat.\n"
            "`?fechar` - Encerra e remove permanentemente o canal do ticket.\n"
            "`?registrarv [qtd]` - Registra uma quantidade de novos vouches comuns no canal.\n"
            "`?registrarbv [qtd]` - Registra uma quantidade de novos Big Vouches no canal.\n"
            "`?stop` - Para imediatamente o envio em massa de vouches gerados por comandos."
        ),
        inline=False
    )
    
    embed_ajuda.set_footer(text=f"Solicitado por {ctx.author.name}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed_ajuda, delete_after=60)
    try: await ctx.message.delete(delay=60)
    except: pass

@bot.command(name="perfil")
async def ver_perfil_rank(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    saldo = obter_saldo(membro.id)
    
    embed = discord.Embed(
        title=f"💳 Perfil de Trader — {membro.name}",
        description=f"📊 **Volume Total de Movimentações:** `{formatar_valor(saldo)}`",
        color=COR_ROXA
    )
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text=f"Consultado por {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)

# ==========================================
# 👑 COMANDOS EXCLUSIVOS DA STAFF (CORRIGIDO)
# ==========================================
@bot.command(name="enviarpainel")
@commands.has_permissions(administrator=True)
async def enviar_painel_principal(ctx):
    try: await ctx.message.delete()
    except: pass

    # --- 🛠️ 1. ENVIO DO PAINEL DE TICKETS / FAQ ---
    canal_faq = None
    try:
        canal_faq = await bot.fetch_channel(ID_CANAL_FAQ)
    except:
        canal_faq = ctx.channel

    if canal_faq:
        try: await canal_faq.purge(limit=50)
        except: pass
        
        emoji_ticket = pegar_emoji(ctx.guild, "discotoolsxyzicon2", "🤝")
        embed_faq = discord.Embed(
            title=f"{str(emoji_ticket)}   ━   SISTEMA DE INTERMEDIAÇÃO",
            description=(
                "Para iniciar uma nova troca/venda via PIX de forma 100% segura usando nossa estrutura "
                "automatizada, abra o menu abaixo e selecione a opção desejada.\n\n"
                "**⚠️ Termos e Avisos Importantes:**\n"
                "• Certifique-se de que o outro participante está no servidor antes de chamá-lo.\n"
                "• Nunca realize transações diretas sem a confirmação de saldo retido do Middleman.\n"
                "• Guarde prints e grave toda a negociação/entrega dos itens para sua segurança."
            ),
            color=COR_ROXA
        )
        await canal_faq.send(embed=embed_faq, view=TicketView(ctx.guild))

    # --- 🏆 2. ENVIO DO PAINEL DE RANKS / CARGOS ---
    canal_ranks = None
    try:
        canal_ranks = await bot.fetch_channel(ID_CANAL_RANKS)
    except:
        canal_ranks = ctx.channel

    if canal_ranks:
        try: await canal_ranks.purge(limit=50)
        except: pass
        
        emoji_rank = pegar_emoji(ctx.guild, "discotoolsxyzicon2", "🏆")
        embed_ranks = discord.Embed(
            title=f"{str(emoji_rank)}   ━   SISTEMA DE RECOMPENSAS HISTÓRICAS",
            description=(
                "Ao acumular movimentações dentro do nosso sistema de Middleman, você sobe automaticamente "
                "de Rank no servidor e desbloqueia novos cargos de prestígio!\n\n"
                "📜 **Lista de Cargos por Volume:**\n"
                "• **Trader Bronze:** R$ 0,01+\n"
                "• **Trader Prata:** R$ 500,00+\n"
                "• **Trader Ouro:** R$ 1.000,00+\n"
                "• **Trader Diamante:** R$ 5.000,00+\n"
                "• **Trader Ametista:** R$ 10.000,00+\n"
                "• **Trader Esmeralda:** R$ 25.000,00+\n"
                "• **Trader Rubi:** R$ 50.000,00+\n"
                "• **Trader Sáfira:** R$ 100.000,00+ *(Ganha Placa Física)*\n"
                "• **Trader Master:** R$ 200.000,00+\n"
                "• **Trader Obsidian:** R$ 400.000,00+\n\n"
                "📦 **Placa Física de Conquista:**\n"
                "Ao atingir o posto de **Trader Sáfira (R$ 100k+)**, você tem o direito de receber em sua residência "
                "uma placa física personalizada exclusiva do servidor com seu nome gravado!"
            ),
            color=COR_ROXA
        )
        await canal_ranks.send(embed=embed_ranks, view=ResgatarPlacaView(ctx.guild))

    await ctx.send(f"✅ **Painéis processados!** Enviados em: FAQ (<#{canal_faq.id}>) e Ranks (<#{canal_ranks.id}>).", delete_after=10)

@bot.command(name="hit")
async def gerar_painel_suporte_scam(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Comando exclusivo da Staff.", delete_after=5)
        return
        
    try: await ctx.message.delete()
    except: pass

    embed_scam = discord.Embed(
        title="🚨 Central de Denúncias e Recuperações",
        description=(
            "Fui roubado (Scam) ou preciso recuperar uma conta? Leia com atenção:\n\n"
            "1. Junte todas as provas em vídeo e prints legíveis da conversa e da ID do infrator.\n"
            "2. Abra um ticket padrão de denúncia na aba de suporte geral do servidor.\n"
            "3. Aguarde um dos Diretores ou Analistas de Segurança avaliar o seu caso.\n\n"
            "⚠️ *Prestar falsas alegações ou tentar forjar comprovantes resultará em banimento permanente imediato.*"
        ),
        color=0xFF0000
    )
    await ctx.send(embed=embed_scam)

@bot.command(name="fechar")
async def fechar_ticket_comando(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Apenas a Staff pode fechar canais de atendimento.", delete_after=5)
        return
    await ctx.send("🛑 **Canal em encerramento... Removendo dados temporários e deletando em 5 segundos.**")
    await asyncio.sleep(5)
    DADOS_TICKETS.pop(ctx.channel.id, None)
    await ctx.channel.delete()

@bot.command(name="funcoes")
async def forcar_inicializacao_funcoes(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        return
    try: await ctx.message.delete()
    except: pass
    view_funcoes = SelecaoFuncoesView(ctx.guild)
    await ctx.send(embed=view_funcoes.gerar_embed(), view=view_funcoes)

@bot.command(name="desmute")
async def remover_timeout_membro(ctx, membro: discord.Member = None):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Permissão insuficiente.", delete_after=5)
        return
    if not membro:
        await ctx.send("❌ Uso correto: `+desmute @membro`", delete_after=5)
        return
    try:
        await membro.timeout(None, reason=f"Timeout removido por {ctx.author.name}")
        await ctx.send(f"✅ O castigo de {membro.mention} foi encerrado com sucesso!")
    except Exception as e:
        await ctx.send(f"❌ Não foi possível retirar o castigo: {e}")

# ==========================================
# 📊 SISTEMA DE ENVIO MASSIVO DE VOUCHES (GERADOR AUTOMÁTICO)
# ==========================================
@bot.command(name="stop")
async def parar_envio_vouches(ctx):
    global parar_envio
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        return
    parar_envio = True
    await ctx.send("🛑 **Comando de parada recebido!** Interrompendo todos os envios de vouches em segundo plano.", delete_after=10)

@bot.command(name="registrarv")
async def registrar_vouches_comuns(ctx, quantidade: int = None):
    global parar_envio
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        return
    if not quantidade or quantidade <= 0:
        await ctx.send("❌ Informe uma quantidade válida! Exemplo: `?registrarv 15`", delete_after=5)
        return

    canal_vouch = bot.get_channel(ID_CANAL_VOUCH)
    if not canal_vouch:
        await ctx.send("❌ Canal de vouches comuns não configurado corretamente.", delete_after=5)
        return

    parar_envio = False
    await ctx.send(f"🚀 Iniciando envio em lote de `{quantidade}` Vouches Comuns no canal {canal_vouch.mention}...")

    for i in range(quantidade):
        if parar_envio:
            await ctx.send("🛑 Processo de vouches comuns cancelado pelo Staff.")
            break

        valor_aleatorio = round(random.uniform(5.00, 95.00), 2)
        id_cliente_aleatorio = random.choice(IDS_REAIS)
        
        embed_vouch = discord.Embed(
            title="📥 VOUCH DE INTERMEDIAÇÃO CONCLUÍDA",
            color=COR_ROXA,
            timestamp=datetime.utcnow() - timedelta(minutes=random.randint(1, 120))
        )
        embed_vouch.add_field(name="👤 Comprador / Client:", value=f"<@{id_cliente_aleatorio}>", inline=True)
        embed_vouch.add_field(name="👑 Middleman Responsável:", value=f"<@{ID_MM_FIXO}>", inline=True)
        embed_vouch.add_field(name="💰 Valor da Transação:", value=f"`{formatar_valor(valor_aleatorio)}`", inline=False)
        embed_vouch.add_field(name="📊 Status no Banco:", value="✅ Sincronizado e Computado com Sucesso", inline=False)
        embed_vouch.set_footer(text="Logs de Transações Oficiais • Verificado via API")

        await canal_vouch.send(embed=embed_vouch)
        await asyncio.sleep(random.uniform(1.2, 3.5))

    if not parar_envio:
        await ctx.send(f"✅ Finalizado! `{quantidade}` vouches comuns foram injetados com sucesso.")

@bot.command(name="registrarbv")
async def registrar_big_vouches(ctx, quantidade: int = None):
    global parar_envio
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        return
    if not quantidade or quantidade <= 0:
        await ctx.send("❌ Informe uma quantidade válida! Exemplo: `?registrarbv 5`", delete_after=5)
        return

    canal_big = bot.get_channel(ID_CANAL_BIGVOUCH)
    if not canal_big:
        await ctx.send("❌ Canal de Big Vouches não configurado corretamente.", delete_after=5)
        return

    parar_envio = False
    await ctx.send(f"🔥 Iniciando envio em lote de `{quantidade}` **BIG VOUCHES** (Valores Altos) no canal {canal_big.mention}...")

    for i in range(quantidade):
        if parar_envio:
            await ctx.send("🛑 Processo de Big Vouches cancelado pelo Staff.")
            break

        valor_alto = round(random.uniform(150.00, 3500.00), 2)
        id_cliente_aleatorio = random.choice(IDS_REAIS)
        
        embed_bv = discord.Embed(
            title="💎 VALOR ALTO — BIG VOUCH VERIFICADO",
            color=0x00FFFF,
            timestamp=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        )
        embed_bv.add_field(name="👤 Investidor / Comprador:", value=f"<@{id_cliente_aleatorio}>", inline=True)
        embed_bv.add_field(name="👑 Middleman de Elite:", value=f"<@{ID_MM_FIXO}>", inline=True)
        embed_bv.add_field(name="💰 Montante Movimentado:", value=f"**{formatar_valor(valor_alto)}**", inline=False)
        embed_bv.add_field(name="🚀 Impacto de Rank:", value="📈 Aplicando multiplicadores históricos na database...", inline=False)
        
        emoji_fogo = pegar_emoji(ctx.guild, "discotoolsxyzicon2", "🔥")
        embed_bv.set_author(name="Transação Monitorada de Grande Volume", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed_bv.set_footer(text=f"Segurança Máxima Garantida {str(emoji_fogo)}")

        await canal_big.send(embed=embed_bv)
        await asyncio.sleep(random.uniform(2.0, 5.0))

    if not parar_envio:
        await ctx.send(f"✨ Concluído! `{quantidade}` Big Vouches de alta relevância foram processados.")

# ==========================================
# 🔄 CICLO DE EVENTOS GERAIS DO BOT
# ==========================================
@bot.event
async def on_ready():
    global bot_inicializado
    if not bot_inicializado:
        bot.add_view(ResgatarPlacaView(None))
        bot_inicializado = True
    print(f"✅ Sistema operacional ativo com sucesso: {bot.user.name} online!")

if __name__ == "__main__":
    bot.run(TOKEN)
