import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# --- Configurações do Cliente ---
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", 7000))
LOCAL_IP = os.getenv("LOCAL_IP", "127.0.0.1")
LOCAL_PORT = int(os.getenv("LOCAL_PORT", 8080))
# O TUNNEL_ID será fornecido pelo bot do Discord após criar o túnel via API.
TUNNEL_ID = os.getenv("TUNNEL_ID")

# --- Lógica de Encaminhamento (Proxy) ---

async def forward_data(reader, writer, connection_name):
    """Lê dados de um 'reader' e os escreve em um 'writer'."""
    try:
        while not reader.at_eof():
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError, BrokenPipeError):
        pass # Silencioso para não poluir o log
    finally:
        writer.close()
        await writer.wait_closed()

# --- Gerenciamento do Canal de Dados ---

async def create_data_channel(token):
    """
    Cria uma nova conexão com o servidor para servir como um canal de dados
    e a conecta ao serviço local.
    """
    try:
        server_reader, server_writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)
        server_writer.write(f"DATA:{token}\n".encode())
        await server_writer.drain()

        local_reader, local_writer = await asyncio.open_connection(LOCAL_IP, LOCAL_PORT)

        # Inicia o proxy bidirecional
        await asyncio.gather(
            forward_data(server_reader, local_writer, "serv->loc"),
            forward_data(local_reader, server_writer, "loc->serv")
        )

    except ConnectionRefusedError:
        print(f"[ERRO] Não foi possível conectar ao serviço local em {LOCAL_IP}:{LOCAL_PORT}.")
    except Exception as e:
        print(f"[ERRO] Falha ao criar canal de dados para {token}: {e}")


# --- Ponto de Entrada Principal do Cliente ---

async def run_client():
    """
    Estabelece o canal de controle com o servidor e escuta por comandos.
    """
    if not TUNNEL_ID:
        print("[ERRO] A variável de ambiente TUNNEL_ID não foi definida.")
        print("Por favor, crie um túnel usando o bot do Discord e configure o TUNNEL_ID.")
        return

    print("--- CZ7 Host FRP Client ---")
    print(f"Conectando ao servidor em {SERVER_IP}:{SERVER_PORT}...")
    print(f"Associando-se ao túnel: {TUNNEL_ID}")
    print(f"Serviço local: http://{LOCAL_IP}:{LOCAL_PORT}")

    try:
        # Conecta ao servidor para estabelecer o canal de controle
        control_reader, control_writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)

        # Identifica este cliente para o túnel pré-autorizado
        control_writer.write(f"CONTROL:{TUNNEL_ID}\n".encode())
        await control_writer.drain()

        print("\nConexão de controle estabelecida. Aguardando tráfego...")
        print("(Pressione Ctrl+C para sair)")

        # Loop principal do canal de controle: escuta por comandos do servidor
        while True:
            server_command = await control_reader.readline()
            if not server_command:
                print("[CONTROLE] Servidor encerrou a conexão.")
                break

            command_str = server_command.decode().strip()
            if command_str.startswith("NEW_CONNECTION:"):
                token = command_str.split(":", 1)[1]
                # Inicia a criação do canal de dados em uma nova tarefa para não bloquear
                asyncio.create_task(create_data_channel(token))

    except ConnectionRefusedError:
        print(f"[ERRO] Conexão recusada. O servidor FRP está online em {SERVER_IP}:{SERVER_PORT}?")
    except Exception as e:
        print(f"[ERRO] Uma exceção inesperada ocorreu: {e}")
    finally:
        print("Cliente encerrado.")


if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        print("\nDesligando o cliente...")