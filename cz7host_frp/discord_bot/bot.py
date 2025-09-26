import os
import discord
import httpx
import asyncio
import threading
import uvicorn
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

# --- Configurações ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "tunnel.cz7host.local")
BOT_API_HOST = os.getenv("BOT_API_HOST", "127.0.0.1")
BOT_API_PORT = int(os.getenv("BOT_API_PORT", 8081))

# --- Cliente da API ---
class FrpApiClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
        self.client = httpx.AsyncClient(base_url=base_url, headers=self.headers)

    async def create_tunnel(self, user_id, local_port):
        try:
            params = {"user_id": str(user_id), "local_port": local_port}
            response = await self.client.post("/tunnels", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"Erro na API: {e.response.status_code}", "details": e.response.json()}
        except httpx.RequestError as e:
            return {"error": f"Erro de conexão com a API: {e}"}

    async def get_tunnel(self, tunnel_id):
        try:
            response = await self.client.get(f"/tunnels/{tunnel_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"Erro na API: {e.response.status_code}", "details": e.response.json()}
        except httpx.RequestError as e:
            return {"error": f"Erro de conexão com a API: {e}"}

    async def delete_tunnel(self, tunnel_id):
        try:
            response = await self.client.delete(f"/tunnels/{tunnel_id}")
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code}
        except httpx.HTTPStatusError as e:
            return {"error": f"Erro na API: {e.response.status_code}", "details": e.response.json()}
        except httpx.RequestError as e:
            return {"error": f"Erro de conexão com a API: {e}"}

    async def map_domain(self, tunnel_id, subdomain):
        try:
            url = f"/tunnels/{tunnel_id}/domain"
            response = await self.client.put(url, params={"subdomain": subdomain})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"Erro na API: {e.response.status_code}", "details": e.response.json()}
        except httpx.RequestError as e:
            return {"error": f"Erro de conexão com a API: {e}"}

# --- API de Callback do Bot ---
bot_api = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class TunnelEvent(BaseModel):
    tunnel_id: str
    user_id: str
    event: str

async def get_api_key(key: str = Depends(api_key_header)):
    if key != API_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return key

# --- Bot do Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Necessário para buscar usuários
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
api_client = FrpApiClient(API_URL, API_SECRET_KEY)

@bot_api.post("/callback", dependencies=[Depends(get_api_key)])
async def handle_callback(event: TunnelEvent):
    if event.event == "connected":
        print(f"Recebido callback: Túnel {event.tunnel_id} conectado para o usuário {event.user_id}")

        user = bot.get_user(int(event.user_id))
        if not user:
            # Tenta buscar o usuário se não estiver no cache
            try:
                user = await bot.fetch_user(int(event.user_id))
            except discord.NotFound:
                print(f"Usuário {event.user_id} não encontrado.")
                return {"status": "error", "message": "User not found"}

        if user:
            embed = discord.Embed(
                title="🚀 Seu Túnel está Online!",
                description=f"O cliente para o túnel `{event.tunnel_id[:8]}...` foi conectado com sucesso.",
                color=discord.Color.brand_green()
            )
            embed.set_footer(text="Seu serviço agora deve estar acessível.")
            try:
                await user.send(embed=embed)
                return {"status": "ok", "message": "DM sent"}
            except discord.Forbidden:
                print(f"Não foi possível enviar DM para o usuário {user.id}. Ele pode ter DMs desativadas.")
                return {"status": "error", "message": "DM forbidden"}

    return {"status": "ok", "message": "Event received"}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('--- CZ7 Host Bot ---')

@bot.command(name="ajuda")
async def help_command(ctx):
    embed = discord.Embed(
        title="Ajuda - Comandos do CZ7 Host FRP",
        description="Aqui estão os comandos que você pode usar para gerenciar seus túneis.",
        color=discord.Color.blue()
    )
    embed.add_field(name="`!tunel criar <porta_local>`", value="Cria um novo túnel FRP para a porta especificada (ex: 8080).", inline=False)
    embed.add_field(name="`!tunel status <ID_DO_TUNEL>`", value="Verifica o status de conexão de um túnel.", inline=False)
    embed.add_field(name="`!tunel deletar <ID_DO_TUNEL>`", value="Deleta um túnel existente.", inline=False)
    embed.add_field(name="`!dominio apontar <ID_DO_TUNEL> <subdominio>`", value=f"Aponta um subdomínio para seu túnel (ex: `meu-site`). Resultado: `meu-site.{BASE_DOMAIN}`.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="tunel")
async def tunnel(ctx, action: str, *, args: str = None):
    if action == "criar":
        if not args:
            await ctx.reply("Uso correto: `!tunel criar <porta_local>` (ex: `!tunel criar 8080`)")
            return
        try:
            local_port = int(args.strip())
        except ValueError:
            await ctx.reply("❌ A porta local deve ser um número válido.")
            return

        result = await api_client.create_tunnel(ctx.author.id, local_port)
        if "error" in result:
            await ctx.reply(f"❌ Falha ao criar túnel: {result.get('details', result['error'])}")
        else:
            tunnel_id = result.get('tunnel_id')
            await ctx.reply(f"✅ Túnel criado com sucesso para a porta `{local_port}`! Enviei os detalhes para sua DM.")

            embed = discord.Embed(
                title="Detalhes do seu Novo Túnel",
                description="Use as informações abaixo para configurar seu cliente FRP.",
                color=discord.Color.green()
            )
            embed.add_field(name="Tunnel ID", value=f"`{tunnel_id}`", inline=False)
            embed.add_field(name="Porta Local Configurada", value=f"`{local_port}`", inline=False)
            embed.add_field(name="Instruções", value=f"1. Baixe o cliente FRP.\n2. Crie um arquivo `.env`.\n3. Adicione `TUNNEL_ID={tunnel_id}`\n4. Adicione `LOCAL_PORT={local_port}`\n5. Rode o cliente.", inline=False)
            await ctx.author.send(embed=embed)

    elif action == "deletar":
        if not args:
            await ctx.reply("Uso correto: `!tunel deletar <ID_DO_TUNEL>`")
            return

        tunnel_id = args.strip()
        result = await api_client.delete_tunnel(tunnel_id)
        if "error" in result:
            await ctx.reply(f"❌ Falha ao deletar túnel: {result.get('details', result['error'])}")
        else:
            await ctx.reply(f"✅ Túnel `{tunnel_id}` deletado com sucesso.")

    elif action == "status":
        if not args:
            await ctx.reply("Uso correto: `!tunel status <ID_DO_TUNEL>`")
            return

        tunnel_id = args.strip()
        result = await api_client.get_tunnel(tunnel_id)

        if "error" in result:
            await ctx.reply(f"❌ Falha ao obter status: {result.get('details', result['error'])}")
        else:
            is_connected = result.get('connected', False)
            status_text = "🟢 Conectado" if is_connected else "🔴 Desconectado"
            color = discord.Color.green() if is_connected else discord.Color.red()

            embed = discord.Embed(
                title=f"Status do Túnel: {tunnel_id[:8]}...",
                color=color
            )
            embed.add_field(name="Status", value=status_text, inline=True)
            embed.add_field(name="Porta Local", value=f"`{result.get('local_port', 'N/A')}`", inline=True)

            domain = result.get('domain')
            if domain:
                embed.add_field(name="Domínio", value=f"http://{domain}", inline=False)

            if is_connected:
                embed.set_footer(text=f"Cliente conectado de: {result.get('client_addr', 'N/A')}")

            await ctx.reply(embed=embed)

    else:
        await ctx.reply(f"Ação `{action}` desconhecida. Use `!ajuda` para ver os comandos.")

@bot.command(name="dominio")
async def domain(ctx, action: str, tunnel_id: str, subdomain: str = None):
    if action == "apontar":
        if not subdomain:
            await ctx.reply("Uso correto: `!dominio apontar <ID_DO_TUNEL> <subdominio>`")
            return

        result = await api_client.map_domain(tunnel_id.strip(), subdomain.strip())
        if "error" in result:
            await ctx.reply(f"❌ Falha ao apontar domínio: {result.get('details', result['error'])}")
        else:
            full_domain = result.get('domain')
            embed = discord.Embed(
                title="Domínio Apontado com Sucesso!",
                description=f"O subdomínio agora aponta para o seu túnel.",
                color=discord.Color.purple()
            )
            embed.add_field(name="Endereço Público", value=f"http://{full_domain}", inline=False)
            embed.add_field(name="Túnel de Destino", value=f"`{tunnel_id}`", inline=False)
            await ctx.reply(embed=embed)
    else:
        await ctx.reply(f"Ação `{action}` desconhecida. Use `!ajuda` para ver os comandos.")

# --- Validação e Execução ---

def run_api():
    """Roda a API do bot em um thread separado para não bloquear o loop do Discord."""
    uvicorn.run(bot_api, host=BOT_API_HOST, port=BOT_API_PORT)

if not all([DISCORD_TOKEN, API_URL, API_SECRET_KEY]):
    print("ERRO: Variáveis de ambiente ausentes!")
    print("Certifique-se de que DISCORD_TOKEN, API_URL, API_SECRET_KEY e BOT_API_PORT estão definidos.")
else:
    # Inicia a API de callback em um thread
    api_thread = threading.Thread(target=run_api)
    api_thread.daemon = True
    api_thread.start()
    print(f"API de callback do bot escutando em http://{BOT_API_HOST}:{BOT_API_PORT}")

    # Inicia o bot do Discord
    bot.run(DISCORD_TOKEN)