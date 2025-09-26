# CZ7 Host - Sistema de Tunelamento FRP via Discord

Bem-vindo ao CZ7 Host! Este projeto é um sistema completo de Fast Reverse Proxy (FRP) que permite aos usuários expor seus serviços locais (como servidores web) à internet de forma segura. O sistema é totalmente gerenciado através de um bot do Discord, proporcionando uma experiência de autoatendimento para seus clientes.

## Componentes do Sistema

1.  **Servidor (`/server`)**: O coração do sistema. É um servidor Python assíncrono que gerencia conexões de clientes, encaminha tráfego e oferece uma API REST para gerenciamento.
2.  **Cliente (`/client`)**: Um script leve em Python que o usuário final executa em sua máquina local para se conectar ao servidor e expor um serviço.
3.  **Bot do Discord (`/discord_bot`)**: A interface de usuário. Permite que os clientes criem e gerenciem seus túneis e domínios através de comandos simples no Discord.

---

## 🚀 Guia do Administrador

Siga estes passos para configurar e implantar todo o sistema CZ7 Host.

### Pré-requisitos

1.  **Um servidor/VPS** com um endereço IP público.
2.  **Um nome de domínio** (ex: `cz7host.com`).
3.  **Python 3.8+** instalado no servidor.
4.  **Um bot do Discord** criado. Você precisará do **Token do Bot**. (Veja como criar um em [discord.com/developers](https://discord.com/developers/docs/intro)).

### 1. Configuração do DNS

Esta é a etapa mais importante para o funcionamento dos subdomínios. No painel de controle do seu domínio, configure os seguintes registros:

- **Registro A**:
  - **Nome/Host**: `@` ou `cz7host.com` (seu domínio raiz)
  - **Valor/Aponta para**: O endereço IP do seu servidor.
- **Registro A (para o serviço de túnel)**:
  - **Nome/Host**: `tunnel` (ou o nome que preferir)
  - **Valor/Aponta para**: O endereço IP do seu servidor.
- **Registro CNAME (Curinga)**:
  - **Nome/Host**: `*.tunnel`
  - **Valor/Aponta para**: `tunnel.cz7host.com` (o registro A que você acabou de criar).

Isso fará com que `tunnel.cz7host.com` e qualquer subdomínio como `meu-site.tunnel.cz7host.com` apontem para o seu servidor.

### 2. Configuração do Servidor

1.  **Clone o repositório** para o seu servidor.
2.  **Navegue até a pasta do servidor**: `cd cz7host_frp/server`
3.  **Instale as dependências**: `pip install -r requirements.txt`
4.  **Crie o arquivo de ambiente**: `touch .env`
5.  **Edite o arquivo `.env`** com as seguintes variáveis:
    ```ini
    # O domínio base que você configurou no DNS
    BASE_DOMAIN=tunnel.cz7host.com

    # Uma chave secreta forte para a comunicação entre o bot e o servidor
    API_SECRET_KEY=gere_uma_chave_segura_aqui

    # Portas (geralmente não precisam ser alteradas)
    SERVER_IP=0.0.0.0
    FRP_PORT=7000
    API_PORT=8000
    HTTP_PORT=80
    ```

### 3. Configuração do Bot do Discord

1.  **Navegue até a pasta do bot**: `cd cz7host_frp/discord_bot`
2.  **Instale as dependências**: `pip install -r requirements.txt`
3.  **Crie o arquivo de ambiente**: `touch .env`
4.  **Edite o arquivo `.env`** com as seguintes variáveis:
    ```ini
    # O token do seu bot do Discord
    DISCORD_TOKEN=seu_token_do_discord_aqui

    # A URL da API do seu servidor
    API_URL=http://127.0.0.1:8000

    # A MESMA chave secreta que você definiu no .env do servidor
    API_SECRET_KEY=a_mesma_chave_segura_aqui

    # O MESMO domínio base do servidor
    BASE_DOMAIN=tunnel.cz7host.com
    ```

### 4. Iniciando o Sistema

- **Para iniciar o servidor**, vá para a pasta `cz7host_frp/server` e execute:
  ```bash
  python server.py
  ```
- **Para iniciar o bot**, vá para a pasta `cz7host_frp/discord_bot` e execute:
  ```bash
  python bot.py
  ```

Para produção, é recomendado usar um gerenciador de processos como `systemd` ou `pm2` para manter os scripts rodando.

---

## 🎮 Guia do Cliente Final

Bem-vindo ao CZ7 Host! Siga estes passos para expor seu projeto local para o mundo.

### 1. Crie seu Túnel

- No nosso servidor do Discord, digite o comando:
  ```
  !tunel criar
  ```
- O bot responderá e enviará uma **mensagem direta (DM)** com seu **ID do Túnel (`TUNNEL_ID`)**. Guarde-o com segurança!

### 2. Configure o Cliente FRP

1.  **Baixe a pasta `client`** do nosso repositório.
2.  Certifique-se de ter o Python instalado.
3.  Na pasta `client`, **instale as dependências**:
    ```bash
    pip install -r requirements.txt
    ```
4.  Crie um arquivo chamado `.env` na mesma pasta.
5.  Abra o arquivo `.env` e adicione as seguintes linhas:
    ```ini
    # O endereço IP do servidor CZ7 Host
    SERVER_IP=ip_do_servidor_cz7_host

    # A porta do seu serviço local que você quer expor (ex: 8080 para um site)
    LOCAL_PORT=8080

    # O ID do túnel que você recebeu do bot na DM
    TUNNEL_ID=seu_tunnel_id_aqui
    ```

### 3. Inicie o Cliente

- Com tudo configurado, execute o cliente:
  ```bash
  python client.py
  ```
- Se tudo estiver correto, você verá uma mensagem de sucesso. Seu serviço local agora está conectado!

### 4. (Opcional) Aponte um Domínio

- Para ter uma URL amigável, use o comando no Discord:
  ```
  !dominio apontar <SEU_TUNNEL_ID> <nome-do-seu-site>
  ```
- **Exemplo**: `!dominio apontar f4a2-b6c8-e1d3 meu-portfolio`
- O bot confirmará, e seu site estará acessível em `http://meu-portfolio.tunnel.cz7host.com`.

### Comandos do Bot

- `!ajuda`: Mostra todos os comandos.
- `!tunel criar`: Cria um novo túnel.
- `!tunel deletar <ID_DO_TUNEL>`: Deleta um túnel.
- `!dominio apontar <ID_DO_TUNEL> <subdominio>`: Aponta um subdomínio para seu túnel.