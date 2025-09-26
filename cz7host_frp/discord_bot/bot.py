import os
import discord
import httpx
from discord.ext import commands
from dotenv import load_dotenv

# --- Configurações ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "tunnel.cz7host.local")

# --- Cliente da API ---
class FrpApiClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
        self.client = httpx.AsyncClient(base_url=base_url, headers=self.headers)

    async def create_tunnel(self, user_id):
        try:
            response = await self.client.post("/tunnels", params={"user_id": str(user_id)})
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

# --- Bot do Discord ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
api_client = FrpApiClient(API_URL, API_SECRET_KEY)

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
    embed.add_field(name="`!tunel criar`", value="Cria um novo túnel FRP. Você receberá o ID do túnel por DM.", inline=False)
    embed.add_field(name="`!tunel deletar <ID_DO_TUNEL>`", value="Deleta um túnel existente.", inline=False)
    embed.add_field(name="`!dominio apontar <ID_DO_TUNEL> <subdominio>`", value=f"Aponta um subdomínio para seu túnel (ex: `meu-site`). Resultado: `meu-site.{BASE_DOMAIN}`.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="tunel")
async def tunnel(ctx, action: str, *, args: str = None):
    if action == "criar":
        result = await api_client.create_tunnel(ctx.author.id)
        if "error" in result:
            await ctx.reply(f"❌ Falha ao criar túnel: {result.get('details', result['error'])}")
        else:
            tunnel_id = result.get('tunnel_id')
            await ctx.reply(f"✅ Túnel criado com sucesso! Enviei os detalhes para sua DM.")

            embed = discord.Embed(
                title="Detalhes do seu Novo Túnel",
                description="Use as informações abaixo para configurar seu cliente FRP.",
                color=discord.Color.green()
            )
            embed.add_field(name="Tunnel ID", value=f"`{tunnel_id}`", inline=False)
            embed.add_field(name="Instruções", value="1. Baixe o cliente FRP.\n2. Crie um arquivo `.env` no mesmo diretório.\n3. Adicione a linha: `TUNNEL_ID=" + tunnel_id + "`\n4. Rode o cliente.", inline=False)
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
if not all([DISCORD_TOKEN, API_URL, API_SECRET_KEY]):
    print("ERRO: Variáveis de ambiente ausentes!")
    print("Certifique-se de que DISCORD_TOKEN, API_URL e API_SECRET_KEY estão definidos no seu arquivo .env")
else:
    bot.run(DISCORD_TOKEN)