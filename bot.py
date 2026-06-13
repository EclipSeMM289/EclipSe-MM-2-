import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
import asyncio
import sqlite3

import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# 📥 CONFIGURAÇÃO DE CANAIS:
ID_CANAL_TICKET = 1512267548043776072
ID_CANAL_FAQ = 1512267542461157536
ID_CANAL_RANKS = 1512267543643951124  
ID_CANAL_VOUCH = 1512267549901983867     
ID_CANAL_BIGVOUCH = 1512267551927963748  

# 👑 CARGOS E IDS ATUALIZADOS:
ID_CARGO_STAFF = 1512269380094787757       # Cargo da Staff / Moderadores
ID_CARGO_RECUPERACAO = 1513703148936499381 # Cargo entregue no comando ?hit
ID_MM_FIXO = 1510480019640553482           # ID do Middleman (MM) Fixo

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  

bot = commands.Bot(command_prefix=["!", "?", "+"], intents=intents, help_command=None)

COR_ROXA = 0xA020F0
parar_envio = False
DADOS_TICKETS = {}

# Mapeamento de cargos para busca dinâmica
LISTA_NOMES_CARGOS = [
    "Trader Bronze", "Trader Prata", "Trader Ouro", "Trader Diamante", 
    "Trader Ametista", "Trader Esmeralda", "Trader Rubi", "Trader Sáfira", 
    "Trader Master", "Trader Obsidian", "Biggest Trader", "OldBigger", "🏆 ・ Top Trader"
]

# Configuração e Inicialização do Banco de Dados SQLite
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

def pegar_emoji(guild, nome, fallback):
    e = discord.utils.get(guild.emojis, name=nome)
    return e if e else fallback

def calcular_taxa(valor: float) -> float:
    if valor <= 2.50: return 0.00
    elif valor <= 100.00: return 1.00
    elif valor <= 200.00: return 2.15
    elif valor <= 400.00: return 4.30
    elif valor <= 700.00: return 6.80
    else: return valor * 0.012

def formatar_valor(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Atualização automática e checagem de cargos baseada nos valores fornecidos
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
                description=f"🎉 {membro.mention} alcançou o total acumulado de **{formatar_valor(saldo)}** em negociações e subiu para o cargo **{cargo_alvo.mention}**!",
                color=COR_ROXA
            )
            await canal_notificacao.send(embed=embed_up)
        except Exception as e:
            print(f"Erro ao atualizar cargo de {membro.name}: {e}")


# 👑 COMPONENTE BOTÃO DO PAINEL DE RANK
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


# 💳 MODAL PARA O MIDDLEMAN INSERIR A CHAVE PIX
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


# 🟪 BOTÃO DE CONFIRMAÇÃO DE RECEBIMENTO
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

        try: await interaction.channel.purge(limit=100)
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


# 🛠️ PAINEL DE CONTROLE DA TRANSAÇÃO (BOTÕES INTERNOS)
class PainelConfiguracaoStaffView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="Definir Chave PIX", style=discord.ButtonStyle.secondary, emoji="📝", row=0)
    async def definir_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ID_CARGO_STAFF for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas o Middleman pode configurar o PIX.", ephemeral=True)
            return
        await interaction.response.send_modal(ConfigurarDadosPixModal(self.ticket_id))

    @discord.ui.button(label="Confirmar Dados da Troca", style=discord.ButtonStyle.secondary, emoji="🤝", row=0)
    async def confirmar_dados_unico(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        try: await interaction.channel.purge(limit=100)
        except: pass

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


# 🔄 VIEW DO PAINEL DE SELEÇÃO DE FUNÇÕES (CLIENTES)
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
            await interaction.response.defer()
            try: await interaction.channel.purge(limit=100)
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

    async def flujo_definir_valor(self, channel):
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
                    try: await channel.purge(limit=100)
                    except: pass
                    asyncio.create_task(self.fluxo_definir_item(channel, valor))
                    break
                except ValueError:
                    await channel.send("❌ **Valor inválido!** Insira apenas números. Exemplo: `50.00`", delete_after=4)
                    try: await msg.delete()
                    except: pass
            except asyncio.TimeoutError:
                await channel.send("🛑 **Tempo limite esgotado!** Ninguém definiu o valor a tempo.")
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
            try: await channel.purge(limit=100)
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
            await channel.send("🛑 **Tempo limite esgotado!** O item não foi registrado a tempo.")


# 👑 MODAL PARA ADICIONAR USUÁRIO POR ID DENTRO DO TICKET
class AdicionarIDModal(discord.ui.Modal, title="Adicionar Usuário por ID"):
    id_input = discord.ui.TextInput(label="ID do Usuário", placeholder="Cole o ID do outro participante aqui...", min_length=15, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.id_input.value)
            membro_adicionar = await interaction.guild.fetch_member(user_id)
            if membro_adicionar:
                await interaction.response.defer()
                await interaction.channel.set_permissions(membro_adicionar, read_messages=True, send_messages=True)
                try: await interaction.channel.purge(limit=100)
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


# 🎛️ VIEW COM OS BOTÕES DO INTERIOR DO TICKET
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
        await interaction.response.send_message("🛑 **Este ticket será fechado e deletado em 5 segundos...**")
        await asyncio.sleep(5)
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
            "1. Adicione o usuário com quem vai negociar usando o menu ou botão abaixo.\n"
            "2. O bot pedirá para ambos descreverem os itens no chat.\n"
            "3. Após confirmação, o pix automático é gerado."
        )
        await channel.send(content=membro.mention, embed=embed_interno, view=PainelInternoTicketView(guild))


class TicketView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(guild))


# 📜 NOVO COMANDO: ?comandos (AUTO-DELETÁVEL EM 60 SEGUNDOS)
@bot.command(name="comandos")
async def comandos_servidor(ctx):
    # Cria uma estrutura visual organizada dividida em seções
    embed_ajuda = discord.Embed(
        title="📋 Lista de Comandos do Servidor",
        description="Esta mensagem e a solicitação serão deletadas automaticamente em **1 minuto**.",
        color=COR_ROXA
    )
    
    # Comandos acessíveis por qualquer membro comum
    embed_ajuda.add_field(
        name="👤 Comandos de Usuários",
        value=(
            "`?comandos` - Mostra esta lista de ajuda.\n"
            "`?perfil` - Mostra seu saldo acumulado e estatísticas de trade.\n"
            "`?perfil @membro` - Consulta o volume total de trades de outro usuário."
        ),
        inline=False
    )

    # Comandos restritos aos Moderadores / Staff
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

    # Envia a resposta configurada para sumir em 60 segundos
    resposta_bot = await ctx.send(embed=embed_ajuda, delete_after=60)
    
    # Tenta apagar a mensagem original enviada pelo usuário após o mesmo tempo
    try:
        await ctx.message.delete(delay=30)
    except discord.Forbidden:
        pass # Ignora caso o bot não tenha permissão de gerenciar mensagens no canal específico
    except Exception as e:
        print(f"Erro ao tentar deletar mensagem de comando: {e}")


# ⚡ SISTEMA DO COMANDO ?HIT
class HitPainelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.secondary, row=0)
    async def aceitar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        cargo = interaction.guild.get_role(ID_CARGO_RECUPERACAO)
        if cargo:
            try:
                await interaction.user.add_roles(cargo)
                await interaction.response.send_message("🟪 Você aceitou! O cargo de recuperação foi adicionado ao seu perfil.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erro ao adicionar o cargo: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ O cargo de recuperação configurado não foi encontrado.", ephemeral=True)

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.secondary, row=0)
    async def recusar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            tempo_timeout = discord.utils.utcnow() + timedelta(days=10)
            await interaction.user.edit(timed_out_until=tempo_timeout, reason="Recusou o painel de suporte contra scam (?hit).")
            await interaction.response.send_message("🔇 Você recusou a ajuda e foi mutado por 10 dias.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Eu não tenho permissão de administrador superior para mutar você.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao aplicar o castigo: {e}", ephemeral=True)


@bot.command(name="hit")
async def hit_comando(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Você não tem permissão para usar este comando.", delete_after=5)
        try: await ctx.message.delete()
        except: pass
        return

    try: await ctx.message.delete()
    except: pass

    embed_hit = discord.Embed(
        title="⚠️ ATENÇÃO!",
        description=(
            "Infelizmente você foi scamado e perdeu seus itens/dinheiro.\n"
            "😢 Sabemos como isso é frustrante...\n"
            "But ainda há esperança!\n\n"
            "🤝 Junte-se a nós e receba ajuda da comunidade para voltar ao topo.\n"
            "Entre agora e comece sua recuperação! 💸🔥"
        ),
        color=COR_ROXA
    )
    await ctx.send(embed=embed_hit, view=HitPainelView())


# 👑 COMANDO +DESMUTE @USER
@bot.command(name="desmute")
async def desmute_comando(ctx, membro: discord.Member = None):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Apenas membros da Staff podem retirar o castigo de usuários.", delete_after=5)
        return
    if not membro:
        await ctx.send("❌ Você precisa mencionar o usuário que deseja desmutar! Exemplo: `+desmute @nome`")
        return
    try:
        await membro.edit(timed_out_until=None, reason=f"Castigo removido manualmente por {ctx.author.name}")
        await ctx.send(f"🟪 O castigo de {membro.mention} foi retirado com sucesso!")
    except discord.Forbidden:
        await ctx.send("❌ Eu não possuo permissões administrativas suficientes para desmutar este membro.")
    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro ao tentar desmutar: {e}")


# Função para gerar a estrutura interna do Painel de Ranks e postar de forma unificada
async def postar_estrutura_painel_ranks(guild, canal):
    roles = {nome: discord.utils.get(guild.roles, name=nome) for nome in LISTA_NOMES_CARGOS}
    
    if not all(roles.values()):
        print("❌ Alerta: Faltam cargos de rank no servidor para gerar o painel!")
        return False

    url_gif_cargos = "https://media.discordapp.net/attachments/1371123164729442475/1482116537119936755/339de7b78f614c4195ebd8433f51dc71.png?ex=6a287a96&is=6a272916&hm=385f3440aac43ad3f6f8fab6faa47f8448cb142bc70b4143df0937eb93c98854&=&format=webp&quality=lossless&width=1584&height=276"
    
    await canal.send(content=url_gif_cargos)

    embed_rank = discord.Embed(color=COR_ROXA)
    embed_rank.description = (
        "⭐   ━   **Cargos e placas.**\n\n"
        f"**<@&{roles['Trader Bronze'].id}>**\n> Faça uma trade no servidor.\n\n"
        f"**<@&{roles['Trader Prata'].id}>**\n> Alcance 500R$ no servidor!\n\n"
        f"**<@&{roles['Trader Ouro'].id}>**\n> Alcance 1000R$ no servidor!\n\n"
        f"**<@&{roles['Trader Diamante'].id}>**\n> Alcance 5000R$ no servidor!\n\n"
        f"**<@&{roles['Trader Ametista'].id}>**\n> Alcance 10000R$ no servidor!\n\n"
        f"**<@&{roles['Trader Esmeralda'].id}>**\n> Alcance 25000R$ no servidor!\n\n"
        f"**<@&{roles['Trader Rubi'].id}>**\n> Alcance 50000R$ no servidor!\n\n"
        f"**<@&{roles['Trader Sáfira'].id}>**\n> Alcance 100000R$ no servidor!\n> **Você ganha uma placa física de recompensa.**\n\n"
        f"**<@&{roles['Trader Master'].id}>**\n> Alcance 200000R$ no servidor!\n> **Você ganha uma placa física de recompensa.**\n\n"
        f"**<@&{roles['Trader Obsidian'].id}>**\n> Alcance 400000R$ no servidor!\n> **Você ganha uma placa física de recompensa.**\n\n"
        "─── 👤 **Cargos Extras** ───\n\n"
        f"**<@&{roles['Biggest Trader'].id}>**\nTenha a maior troca atual da EclipSe MM.\n\n"
        f"**<@&{roles['OldBigger'].id}>**\nTenha feito pelo menos uma vez a maior troca da EclipSe MM.\n\n"
        f"**<@&{roles['🏆 ・ Top Trader'].id}>**\nTermine o mês como TOP 1 MENSAL.\n"
    )
    await canal.send(embed=embed_rank, view=ResgatarPlacaView(guild))
    return True


# 👑 COMANDO MANUAL: ?enviarpainel
@bot.command(name="enviarpainel")
async def enviar_painel_especifico(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Apenas membros da Staff podem executar este comando.", delete_after=5)
        return

    canal_ranks = bot.get_channel(ID_CANAL_RANKS)
    if not canal_ranks:
        await ctx.send(f"❌ Não consegui localizar o canal de Ranks com o ID `{ID_CANAL_RANKS}`.")
        return

    try: await canal_ranks.purge(limit=100)
    except: pass

    sucesso = await postar_estrutura_painel_ranks(ctx.guild, canal_ranks)
    if sucesso:
        await ctx.send(f"✅ Painel de Ranks atualizado enviado no canal correto {canal_ranks.mention}!")
    else:
        await ctx.send("❌ Falha ao enviar o painel. Verifique se todos os cargos existem.")


# COMANDO EXTRA PARA VERIFICAR SEU SALDO ATUAL E PROGRESSO: ?perfil
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
    await ctx.send(embed=embed)


# ⏰ TAREFA EM SEGUNDO PLANO
@tasks.loop(minutes=1)
async def loop_vouches_automaticos():
    eh_big_vouch = random.choice([True, False])
    tipo_envio = random.choice(["Automático", "Manual"])
    
    if eh_big_vouch:
        canal = bot.get_channel(ID_CANAL_BIGVOUCH)
        valor_aleatorio = round(random.uniform(1000.0, 10000.0), 2)
    else:
        canal = bot.get_channel(ID_CANAL_VOUCH)
        valor_aleatorio = round(random.uniform(5.0, 1000.0), 2)
        
    if canal:
        await gerador_de_vouch_base(canal, tipo_envio, valor_aleatorio, eh_big_vouch)


@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user}")
    
    guild_inicial = bot.guilds[0] if bot.guilds else None
    bot.add_view(ResgatarPlacaView(guild_inicial))
    
    if not loop_vouches_automaticos.is_running():
        loop_vouches_automaticos.start()
        print("⏰ Loop de 1 minuto de canais de Vouch ativo!")
    
    url_foto_aperto_mao = "https://cdn.discordapp.com/attachments/1183577000854896732/1183582455320743956/image_84c404.jpg"
    url_gif_original_ticket = "https://cdn.eclipsebuxx.com/chat/MMEMBED.png"
    url_gif_novo_faq = "https://cdn.discordapp.com/attachments/1475513995053240442/1491436000067715204/5c7d37c02d7a40abf85cfa4140547a48.gif?ex=6a2d6103&is=6a2c0f83&hm=32926c260dcbb7f687824dd03c431a037c1a2f96380d5e39975350f733cb8836&"
    
    espacamento_invisivel = "‎" + " " * 75  

    print("Purgando e atualizando todos os painéis nos canais...")

    canal_alvo = bot.get_channel(ID_CANAL_TICKET)
    if canal_alvo:
        try:
            await canal_alvo.purge(limit=100)
            
            emoji_icon = pegar_emoji(canal_alvo.guild, "discotoolsxyzicon2", "🤝")
            embed = discord.Embed(color=COR_ROXA)
            embed.description = (
                f"{str(emoji_icon)}   ━   **Solicitar MM**\n"
                f"{espacamento_invisivel}\n"
                "> **Taxas Normais**\n"
                "**R$ 1,00** Acima de R$2,50.\n"
                "**R$ 2,15** Acima de R$100.\n"
                "**R$ 4,30** Acima de R$200.\n"
                "**R$ 6,80** Acima de R$400.\n"
                "**1,2%** Acima de R$700.\n"
                "Em conta adicionamos **4R$.**"
            )
            embed.set_image(url=url_gif_original_ticket)
            
            await canal_alvo.send(embed=embed, view=TicketView(canal_alvo.guild))
            print("✅ Canal de Tickets limpo e painel enviado!")
        except Exception as e:
            print(f"❌ Erro ao enviar para o canal de ticket: {e}")

    canal_ranks = bot.get_channel(ID_CANAL_RANKS)
    if canal_ranks and guild_inicial:
        try:
            await canal_ranks.purge(limit=100)
            await postar_estrutura_painel_ranks(guild_inicial, canal_ranks)
            print("✅ Canal de Ranks limpo e painel enviado!")
        except Exception as e:
            print(f"❌ Erro ao atualizar automaticamente o canal de ranks: {e}")

    canal_faq = bot.get_channel(ID_CANAL_FAQ)
    if canal_faq:
        try:
            await canal_faq.purge(limit=100)
            
            embed_faq_unico = discord.Embed(color=COR_ROXA)
            embed_faq_unico.set_thumbnail(url=url_foto_aperto_mao)
            
            embed_faq_unico.title = "❓ — FAQ."
            embed_faq_unico.description = "Todas as dúvidas frequentes do nosso novo middleman automático de forma organizada aqui! Caso tenha outras dúvidas, contacte um staff.\n\u200b"

            embed_faq_unico.add_field(
                name="❓ — E se o vendedor não me entregar o produto após eu pagar ou o cliente não confirmar que recebeu ?",
                value=(
                    "Nosso middleman automático foi projetado para ser seguro em literalmente qualquer etapa, por isso temos uma função chamada abrir disputa que é disponibilizada logo após a confirmação do pagamento. Você pode usar essa função para qualquer irregularidade na sua troca, que assim um supervisor será contactado para entender a irregularidade e tomar a melhor decisão\n\n"
                    "Você pode usar a disputa caso você não receba o produto ou o comprador não confirme a entrega, que o supervisor irá analisar sua troca, mensagens trocadas e etc, que assim o seu valor será retornado/reembolsado.\n\u200b"
                ),
                inline=False
            )

            embed_faq_unico.add_field(
                name="❓ — O pagamento é seguro? O dinheiro pode ser retido ou perdido?",
                value="Não, temos uma integração com gateways gigantes e seguras, que garante que o seu dinheiro ficará conosco de forma segura, nada é perdido com MED (contestação). Mesmo que o comprador peça reembolso no banco, a plataforma protege o valor e nada fica retido.\n\u200b",
                inline=False
            )

            embed_faq_unico.add_field(
                name="❓ — Alguma coisa é liberada sem ambas as partes ?",
                value=(
                    "Não, a troca enquanto decorre é analisada por supervisores e nada pode ser liberado sem o acordo de ambas as partes. Caso uma das partes seja desonesta ou suma da troca, tomaremos a melhor decisão analisando a troca.\n\n"
                    "Por exemplo, o vendedor sumiu no meio da troca sem te entregar o produto, nós te reembolsaríamos analisando o chat da troca."
                ),
                inline=False
            )

            await canal_faq.send(embed=embed_faq_unico)
            await canal_faq.send(content=url_gif_novo_faq)
            print("✅ Canal de FAQ limpo e painel enviado!")
            
        except Exception as e:
            print(f"❌ Erro ao reproduzir mensagens do FAQ: {e}")


@bot.command()
async def funcoes(ctx):
    try: await ctx.channel.purge(limit=100)
    except: pass
    view_funcoes = SelecaoFuncoesView(ctx.guild)
    await ctx.send(embed=view_funcoes.gerar_embed(), view=view_funcoes)


@bot.command()
async def fechar(ctx):
    if not any(role.id == ID_CARGO_STAFF for role in ctx.author.roles):
        await ctx.send("❌ Apenas membros da Staff podem fechar este ticket.", delete_after=5)
        try: await ctx.message.delete()
        except: pass
        return
        
    await ctx.send("🛑 **Deletando este canal de atendimento em 3 seconds...**")
    await asyncio.sleep(3)
    DADOS_TICKETS.pop(ctx.channel.id, None)
    await ctx.channel.delete()


async def gerador_de_vouch_base(destino, tipo, valor, eh_big):
    guild = destino.guild
    trade = pegar_emoji(guild, "discotoolsxyzicon2", "🤝")
    money = pegar_emoji(guild, "discotoolsxyzicon22", "💲")
    users = pegar_emoji(guild, "discotoolsxyzicon23", "👥")
    calendar = pegar_emoji(guild, "discotoolsxyzicon24", "📅")

    agora = datetime.now().strftime("%d de %B de %Y %H:%M")
    meses = {
        "January": "janeiro", "February": "fevereiro", "March": "março", 
        "April": "abril", "May": "maio", "June": "junho", 
        "July": "julho", "August": "agosto", "September": "setembro", 
        "October": "outubro", "November": "novembro", "December": "dezembro"
    }
    for eng, pt in meses.items(): agora = agora.replace(eng, pt)

    membros_reais = [membro.id for membro in guild.members if not membro.bot]

    if len(membros_reais) >= 2:
        id_p1 = random.choice(membros_reais)
        id_p2 = random.choice(membros_reais)
        while id_p1 == id_p2: 
            id_p2 = random.choice(membros_reais)
    else:
        id_p1 = 1417022267044659241
        id_p2 = 1499270758193565746

    texto_titulo = "Big vouch" if eh_big else "vouch"
    embed = discord.Embed(
        title=f"{str(trade)} ━ Troca de PIX {texto_titulo}. ({tipo})",
        description=f"Uma troca de pix {tipo.lower()} aconteceu, informações abaixo:\n\u200b",
        color=COR_ROXA
    )
    
    valor_texto = (
        f"• {str(money)} **Valor:** {formatar_valor(valor)}\n"
        f"• {str(users)} **Participantes:** <@{id_p1}> e <@{id_p2}>\n"
        f"• {str(calendar)} **Horário:** {agora}\n"
        f"• 👤 **Middleman:** <@{ID_MM_FIXO}>"
    )

    embed.add_field(name="", value=valor_texto, inline=False)
    await destino.send(embed=embed)


@bot.command()
async def registrarbv(ctx, quantidade: int):
    global parar_envio
    parar_envio = False
    for _ in range(quantidade):
        if parar_envio: break
        await gerador_de_vouch_base(ctx.channel, random.choice(["Automático", "Manual"]), round(random.uniform(1000.0, 10000.0), 2), eh_big=True)
        await asyncio.sleep(0.5)

@bot.command()
async def registrarv(ctx, quantidade: int):
    global parar_envio
    parar_envio = False
    for _ in range(quantidade):
        if parar_envio: break
        await gerador_de_vouch_base(ctx.channel, random.choice(["Automático", "Manual"]), round(random.uniform(5.0, 1000.0), 2), eh_big=False)
        await asyncio.sleep(0.5)

@bot.command()
async def stop(ctx):
    global parar_envio
    parar_envio = True
    await ctx.send("🛑 **O envio de mensagens automáticas via comando foi parado com sucesso!**")

bot.run(TOKEN)