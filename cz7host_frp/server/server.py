import asyncio
import os
import uuid
import uvicorn
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

load_dotenv()

# --- Configurações ---
SERVER_IP = os.getenv("SERVER_IP", "0.0.0.0")
FRP_PORT = int(os.getenv("FRP_PORT", 7000))
API_PORT = int(os.getenv("API_PORT", 8000))
HTTP_PORT = int(os.getenv("HTTP_PORT", 80))
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "tunnel.cz7host.local")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "supersecretkey_for_discord_bot")
BOT_CALLBACK_URL = os.getenv("BOT_CALLBACK_URL")

# --- API (FastAPI) ---
api = FastAPI(title="CZ7 Host FRP Management API")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# --- Estado do Servidor ---
tunnels = {}  # {tunnel_id: {config}}
pending_connections = {}  # {token: {public_reader, public_writer, initial_data}}
domain_map = {}  # {hostname: tunnel_id}

# --- Segurança da API ---
async def get_api_key(key: str = Depends(api_key_header)):
    if key != API_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return key

# --- Lógica do Servidor TCP e HTTP ---

async def notify_bot_of_connection(tunnel_id: str):
    """Envia um callback para o bot informando que um túnel foi conectado."""
    if not BOT_CALLBACK_URL:
        return

    if tunnel_id not in tunnels:
        return

    tunnel_data = tunnels[tunnel_id]
    payload = {
        "tunnel_id": tunnel_id,
        "user_id": tunnel_data.get("user_id"),
        "event": "connected"
    }

    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": API_SECRET_KEY}
            response = await client.post(BOT_CALLBACK_URL, json=payload, headers=headers, timeout=5)
            if response.status_code == 200:
                print(f"[{tunnel_id}] Callback para o bot enviado com sucesso.")
            else:
                print(f"[{tunnel_id}] Erro ao enviar callback para o bot: {response.status_code} {response.text}")
    except httpx.RequestError as e:
        print(f"[{tunnel_id}] Falha ao conectar com o bot para callback: {e}")


async def forward_data(reader, writer, name):
    try:
        while not reader.at_eof():
            data = await reader.read(4096)
            if not data: break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError, BrokenPipeError):
        pass
    finally:
        writer.close()

async def signal_new_connection(tunnel_id, public_reader, public_writer, initial_data=None):
    if tunnel_id not in tunnels or not tunnels[tunnel_id].get('connected'):
        print(f"[{tunnel_id}] Sinal ignorado: túnel não conectado.")
        public_writer.close()
        return

    try:
        token = str(uuid.uuid4())
        pending_connections[token] = {"public_reader": public_reader, "public_writer": public_writer, "initial_data": initial_data}

        control_writer = tunnels[tunnel_id]['control_writer']
        control_writer.write(f"NEW_CONNECTION:{token}\n".encode())
        await control_writer.drain()
        print(f"[{tunnel_id}] Cliente sinalizado para nova conexão (token: {token[:8]})")
    except Exception as e:
        print(f"[{tunnel_id}] Erro ao sinalizar cliente: {e}")
        public_writer.close()

async def handle_http_connection(public_reader, public_writer):
    try:
        http_request_bytes = await public_reader.readuntil(b'\r\n\r\n')
        http_request = http_request_bytes.decode('utf-8', errors='ignore')

        host_header = next((line for line in http_request.split('\r\n') if line.lower().startswith('host:')), None)

        if not host_header:
            public_writer.close()
            return

        host = host_header.split(':', 1)[1].strip().lower()

        if host not in domain_map:
            error_response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 26\r\n\r\nCZ7 Host: Tunnel Not Found"
            public_writer.write(error_response)
            await public_writer.drain()
            public_writer.close()
            return

        tunnel_id = domain_map[host]
        await signal_new_connection(tunnel_id, public_reader, public_writer, initial_data=http_request_bytes)

    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass # Conexão fechada pelo cliente antes de enviar dados completos
    except Exception as e:
        print(f"[HTTP] Erro: {e}")
        public_writer.close()

async def handle_frp_client(client_reader, client_writer):
    client_addr = client_writer.get_extra_info('peername')
    try:
        first_line = await client_reader.readline()
        message = first_line.decode().strip()

        if message.startswith("DATA:"):
            token = message.split(":", 1)[1]
            if token in pending_connections:
                pending = pending_connections.pop(token)
                public_reader = pending["public_reader"]
                public_writer = pending["public_writer"]

                if pending["initial_data"]:
                    client_writer.write(pending["initial_data"])
                    await client_writer.drain()

                await asyncio.gather(
                    forward_data(public_reader, client_writer, "pub->cli"),
                    forward_data(client_reader, public_writer, "cli->pub")
                )
            else:
                client_writer.close()

        elif message.startswith("CONTROL:"):
            tunnel_id = message.split(":", 1)[1]
            if tunnel_id in tunnels and not tunnels[tunnel_id].get('connected'):
                tunnels[tunnel_id].update({
                    'control_writer': client_writer,
                    'connected': True,
                    'client_addr': client_addr
                })
                print(f"[{tunnel_id}] Cliente conectado de {client_addr}")
                asyncio.create_task(notify_bot_of_connection(tunnel_id))
                await client_reader.read() # Manter conexão para futuros sinais
            else:
                client_writer.close()
        else:
            client_writer.close()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        # Lógica de Limpeza
        for tid, data in list(tunnels.items()):
            if data.get('control_writer') == client_writer:
                print(f"[{tid}] Cliente desconectado. Limpando túnel.")
                if 'domain' in data and data['domain'] in domain_map:
                    del domain_map[data['domain']]
                tunnels.pop(tid)
                break
        client_writer.close()

# --- Endpoints da API ---

@api.post("/tunnels", summary="Cria um novo túnel", dependencies=[Depends(get_api_key)])
async def create_tunnel(user_id: str, local_port: int):
    tunnel_id = str(uuid.uuid4())
    tunnels[tunnel_id] = {
        "user_id": user_id,
        "local_port": local_port,
        "connected": False,
        "domain": None,
    }
    print(f"API criou o túnel {tunnel_id} para o usuário {user_id} para a porta local {local_port}")
    return {"tunnel_id": tunnel_id, "user_id": user_id, "local_port": local_port}

@api.get("/tunnels/{tunnel_id}", summary="Obtém detalhes de um túnel específico", dependencies=[Depends(get_api_key)])
async def get_tunnel_details(tunnel_id: str):
    if tunnel_id not in tunnels:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    data = tunnels[tunnel_id]
    # Clean data for JSON response
    clean_data = {k: v for k, v in data.items() if not asyncio.iscoroutine(v) and not isinstance(v, (asyncio.StreamWriter, asyncio.base_events.Server))}
    return clean_data


@api.put("/tunnels/{tunnel_id}/domain", summary="Aponta um subdomínio para um túnel", dependencies=[Depends(get_api_key)])
async def map_domain(tunnel_id: str, subdomain: str):
    if tunnel_id not in tunnels:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    full_domain = f"{subdomain.lower()}.{BASE_DOMAIN}"
    if full_domain in domain_map and domain_map[full_domain] != tunnel_id:
        raise HTTPException(status_code=409, detail=f"Domain '{full_domain}' is already in use.")

    # Remove mapeamento antigo se o túnel já tinha um
    if tunnels[tunnel_id].get('domain') and tunnels[tunnel_id]['domain'] in domain_map:
        del domain_map[tunnels[tunnel_id]['domain']]

    domain_map[full_domain] = tunnel_id
    tunnels[tunnel_id]["domain"] = full_domain
    print(f"API mapeou {full_domain} para {tunnel_id}")
    return {"message": "Domain mapped successfully", "domain": full_domain}

@api.delete("/tunnels/{tunnel_id}", summary="Deleta um túnel", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_api_key)])
async def delete_tunnel(tunnel_id: str):
    if tunnel_id not in tunnels:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    tunnel = tunnels.pop(tunnel_id)
    if tunnel.get('domain') and tunnel['domain'] in domain_map:
        del domain_map[tunnel['domain']]

    if tunnel.get('connected'):
        tunnel['control_writer'].close()

    print(f"API deletou o túnel {tunnel_id}")
    return {}

# --- Ponto de Entrada Principal ---

async def main():
    config = uvicorn.Config(app, host=SERVER_IP, port=API_PORT, log_level="info")
    api_server = uvicorn.Server(config)

    tcp_server = await asyncio.start_server(handle_frp_client, SERVER_IP, FRP_PORT)
    http_server = await asyncio.start_server(handle_http_connection, SERVER_IP, HTTP_PORT)

    print(f"--- CZ7 Host FRP Server ---")
    print(f"API de Gerenciamento em http://{SERVER_IP}:{API_PORT}")
    print(f"Servidor de Clientes FRP em {SERVER_IP}:{FRP_PORT}")
    print(f"Proxy HTTP em {SERVER_IP}:{HTTP_PORT} para *.{BASE_DOMAIN}")

    await asyncio.gather(api_server.serve(), tcp_server.serve_forever(), http_server.serve_forever())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor desligando.")