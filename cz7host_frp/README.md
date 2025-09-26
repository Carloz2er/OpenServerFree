# CZ7 Host - Sistema de Tunelamento FRP via Discord

Bem-vindo ao CZ7 Host! Este projeto é um sistema completo de Fast Reverse Proxy (FRP) que permite aos usuários expor seus serviços locais (como servidores web) à internet de forma segura. O sistema é totalmente gerenciado através de um bot do Discord, proporcionando uma experiência de autoatendimento para seus clientes, com feedback de conexão em tempo real.

## Componentes do Sistema

1.  **Servidor (`/server`)**: O coração do sistema. É um servidor Python assíncrono que gerencia conexões de clientes, encaminha tráfego, oferece uma API REST para gerenciamento e envia notificações de status.
2.  **Cliente (`/client`)**: Um script leve em Python que o usuário final executa em sua máquina local para se conectar ao servidor e expor um serviço.
3.  **Bot do Discord (`/discord_bot`)**: A interface de usuário. Permite que os clientes criem e gerenciem seus túneis e domínios, recebendo notificações em tempo real.

---

## 🚀 Guia do Administrador

Siga estes passos para configurar e implantar todo o sistema CZ7 Host.

### Pré-requisitos

1.  **Um servidor/VPS** com um endereço IP público.
2.  **Um nome de domínio** (ex: `cz7host.com`).
3.  **Python 3.8+** instalado no servidor.
4.  **Um bot do Discord** criado. Você precisará do **Token do Bot**. (Veja como criar um em [discord.com/developers](https://discord.com/developers/docs/intro)).

### 1. Configuração do DNS

No painel de controle do seu domínio, configure os seguintes registros:

- **Registro A**: `tunnel.cz7host.com` -> `IP_DO_SEU_SERVIDOR`
- **Registro CNAME**: `*.tunnel.cz7host.com` -> `tunnel.cz7host.com`

### 2. Configuração do Servidor

1.  **Navegue até a pasta do servidor**: `cd cz7host_frp/server`
2.  **Instale as dependências**: `pip install -r requirements.txt`
3.  **Crie e edite o arquivo `.env`** com as seguintes variáveis:
    ```ini
    # O domínio base que você configurou no DNS
    BASE_DOMAIN=tunnel.cz7host.com

    # Uma chave secreta forte para a comunicação entre o bot e o servidor
    API_SECRET_KEY=gere_uma_chave_segura_aqui

    # O endereço para o qual o servidor enviará notificações de conexão.
    # Deve ser o endereço do seu bot.
    BOT_CALLBACK_URL=http://127.0.0.1:8081/callback

    # Portas (geralmente não precisam ser alteradas)
    SERVER_IP=0.0.0.0
    FRP_PORT=7000
    API_PORT=8000
    HTTP_PORT=80
    ```

### 3. Configuração do Bot do Discord

1.  **Navegue até a pasta do bot**: `cd cz7host_frp/discord_bot`
2.  **Instale as dependências**: `pip install -r requirements.txt`
3.  **Crie e edite o arquivo `.env`** com as seguintes variáveis:
    ```ini
    # O token do seu bot do Discord
    DISCORD_TOKEN=seu_token_do_discord_aqui

    # A URL da API do seu servidor
    API_URL=http://127.0.0.1:8000

    # A MESMA chave secreta que você definiu no .env do servidor
    API_SECRET_KEY=a_mesma_chave_segura_aqui

    # O MESMO domínio base do servidor
    BASE_DOMAIN=tunnel.cz7host.com

    # Endereço e porta para a API de callback do bot
    BOT_API_HOST=127.0.0.1
    BOT_API_PORT=8081
    ```
    **Importante**: Se o bot e o servidor rodarem em máquinas diferentes, certifique-se de que o `BOT_CALLBACK_URL` no servidor aponte para o IP público e a porta correta do bot, e que o firewall permita a conexão.

### 4. Iniciando o Sistema

- **Para iniciar o servidor**, vá para a pasta `cz7host_frp/server` e execute: `python server.py`
- **Para iniciar o bot**, vá para a pasta `cz7host_frp/discord_bot` e execute: `python bot.py`

Para produção, é recomendado usar um gerenciador de processos como `systemd` ou `pm2`.

---

## 🎮 Guia do Cliente Final

Bem-vindo ao CZ7 Host! Siga estes passos para expor seu projeto local para o mundo.

### 1. Crie seu Túnel

- No nosso servidor do Discord, digite o comando, especificando a porta do seu serviço local:
  ```
  !tunel criar 8080
  ```
- O bot responderá e enviará uma **mensagem direta (DM)** com seu **ID do Túnel (`TUNNEL_ID`)**.

### 2. Configure o Cliente FRP

1.  **Baixe a pasta `client`** do nosso repositório.
2.  Na pasta `client`, **instale as dependências**: `pip install -r requirements.txt`
3.  Crie um arquivo chamado `.env` e adicione as seguintes linhas:
    ```ini
    # O endereço IP do servidor CZ7 Host
    SERVER_IP=ip_do_servidor_cz7_host

    # A porta do seu serviço local (a mesma que você usou no comando !tunel criar)
    LOCAL_PORT=8080

    # O ID do túnel que você recebeu do bot na DM
    TUNNEL_ID=seu_tunnel_id_aqui
    ```

### 3. Inicie o Cliente

- Com tudo configurado, execute o cliente: `python client.py`
- Se tudo estiver correto, você receberá uma **nova DM do bot** confirmando que seu túnel está **online e conectado**!

### 4. (Opcional) Aponte um Domínio

- Para ter uma URL amigável, use o comando no Discord:
  ```
  !dominio apontar <SEU_TUNNEL_ID> <nome-do-seu-site>
  ```
- O bot confirmará, e seu site estará acessível em `http://nome-do-seu-site.tunnel.cz7host.com`.

### Comandos do Bot

- `!ajuda`: Mostra todos os comandos.
- `!tunel criar <porta_local>`: Cria um novo túnel para a porta especificada.
- `!tunel status <ID_DO_TUNEL>`: Verifica o status de conexão de um túnel.
- `!tunel deletar <ID_DO_TUNEL>`: Deleta um túnel.
- `!dominio apontar <ID_DO_TUNEL> <subdominio>`: Aponta um subdomínio para seu túnel.