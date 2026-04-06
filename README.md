# Sistema de Alerta Energético e Ambiental — AM

Automação web desenvolvida com **Python 3.11**, **BotCity Framework** e **BotCity Maestro** para monitoramento contínuo de indicadores ambientais e energéticos do Amazonas. O sistema coleta dados de portais governamentais, consolida em uma planilha Google Sheets e dispara alertas via WhatsApp.

---

## Visão Geral

O sistema é composto por 4 bots especializados, orquestrados pelo BotCity Maestro:

| Bot | Fontes | Responsabilidade |
|---|---|---|
| `bot_ambiental` | SACE, INPE, IQAr | Coleta nível do Rio Negro, focos de incêndio e qualidade do ar |
| `bot_energia` | ONS, ANEEL | Coleta volume útil da UHE Balbina e bandeira tarifária |
| `bot_controlador` | Google Sheets | Consolida os dados e grava na planilha |
| `bot_alerta` | Twilio WhatsApp | Lê a planilha e dispara alerta via WhatsApp |

---

## Pré-requisitos

- Python 3.11
- Windows 10/11
- Google Chrome instalado
- Conta ativa no [BotCity Maestro](https://developers.botcity.dev)
- Conta Twilio com WhatsApp Sandbox configurado
- Projeto Google Cloud com a API Google Sheets habilitada

---

## Estrutura do Projeto
Sistema-Alerta-AM-BotCity/
├── bot_ambiental/
│   ├── bot.py
│   └── requirements.txt
├── bot_energia/
│   ├── bot.py
│   └── requirements.txt
├── bot_controlador/
│   ├── bot.py
│   ├── requirements.txt
│   └── config/
│       ├── oauth_credentials.json
│       └── token_sheets.json
├── bot_alerta/
│   ├── bot.py
│   ├── requirements.txt
│   └── config/
│       ├── oauth_credentials.json
│       └── token_sheets.json
├── .env
├── .gitignore
└── README.md

---

## Instalação

### 1. Clonar o repositório
```bash
git clone https://github.com/vbrenox/Sistema-Alerta-AM-BotCity.git
cd Sistema-Alerta-AM-BotCity
```

### 2. Criar e ativar ambiente virtual
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependências de cada bot
```bash
pip install -r bot_ambiental/requirements.txt
pip install -r bot_energia/requirements.txt
pip install -r bot_controlador/requirements.txt
pip install -r bot_alerta/requirements.txt
```

---

## Configuração de Credenciais

### 1. Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
```env
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM=+14155238886
TWILIO_TO=+5592XXXXXXXXX
```

> As credenciais Twilio são obtidas no painel em [twilio.com/console](https://twilio.com/console).

### 2. Google Sheets — OAuth2

O projeto utiliza autenticação OAuth2 com app de desktop.

1. Acesse o [Google Cloud Console](https://console.cloud.google.com)
2. Crie um projeto e habilite a **Google Sheets API**
3. Em **Credenciais**, crie um **ID do cliente OAuth 2.0** do tipo `Aplicativo de desktop`
4. Baixe o JSON e salve como:
   - `bot_controlador/config/oauth_credentials.json`
   - `bot_alerta/config/oauth_credentials.json`
5. Na primeira execução local, o navegador abrirá para autorização — o token será salvo automaticamente como `token_sheets.json` na mesma pasta

### 3. ID da Planilha Google Sheets

A planilha utilizada é `SistemaAlertaAM`. O ID está definido diretamente nos bots:
```python
SHEET_ID = "1wG6icQpwUmfjaL0KruwXelH9iAKV_UfRjwOURZXJDqE"
```

Certifique-se de que a conta OAuth2 tem acesso de edição à planilha.

---

## Execução Local

Execute cada bot na ordem abaixo a partir da raiz do projeto:
```bash
# 1. Coleta ambiental
python bot_ambiental/bot.py

# 2. Coleta energética
python bot_energia/bot.py

# 3. Consolidação no Google Sheets
python bot_controlador/bot.py

# 4. Envio do alerta via WhatsApp
python bot_alerta/bot.py
```

> Em execução local, `MAESTRO_ATIVO = False`. As credenciais são lidas do `.env` e os JSONs são lidos diretamente das pastas dos bots.

---

## Configuração no BotCity Maestro

### 1. Registrar os bots (Easy Deploy)

Para cada bot, crie um ZIP contendo os arquivos obrigatórios e faça o deploy:

| Bot | Arquivos no ZIP |
|---|---|
| `bot_ambiental` | `bot.py`, `requirements.txt` |
| `bot_energia` | `bot.py`, `requirements.txt` |
| `bot_controlador` | `bot.py`, `requirements.txt`, `config/oauth_credentials.json`, `config/token_sheets.json` |
| `bot_alerta` | `bot.py`, `requirements.txt`, `config/oauth_credentials.json`, `config/token_sheets.json` |

No Maestro:
1. Acesse **Automações → Easy Deploy**
2. Clique em **Nova Automação**
3. Preencha o label conforme abaixo e faça o upload do ZIP

| Bot | Label no Maestro |
|---|---|
| `bot_ambiental` | `victorbreno-ambiental-v1` |
| `bot_energia` | `victorbreno-energia-v1` |
| `bot_controlador` | `victorbreno-controlador-v1` |
| `bot_alerta` | `victorbreno-alerta-v1` |

### 2. Configurar o Credentials Vault

No Maestro, acesse **Credenciais** e crie um vault com o label `victorbreno-twilio-v1` contendo as seguintes chaves:

| Chave | Valor |
|---|---|
| `TWILIO_SID` | Account SID da Twilio |
| `TWILIO_TOKEN` | Auth Token da Twilio |
| `TWILIO_FROM` | Número Twilio (ex: `+14155238886`) |
| `TWILIO_TO` | Número destino (ex: `+5592XXXXXXXXX`) |

> Os números devem ser informados **sem** o prefixo `whatsapp:`.

### 3. Configurar o Log de Execução

No Maestro, acesse **Log de Execução → Novo Log** e crie com o label `victorbreno-execucao-v1-log` com as seguintes colunas:

| Label | Nome |
|---|---|
| `bot` | Bot |
| `status` | Status |
| `timestamp` | Timestamp |
| `mensagem` | Mensagem |

### 4. Configurar o Runner

Certifique-se de que o Runner está ativo e configurado. O projeto utiliza o runner `runner-manha02`.

### 5. Executar os bots no Maestro

No Maestro, acesse **Fila de Tarefas → Nova Tarefa** e crie as tarefas na seguinte ordem:

1. `victorbreno-ambiental-v1`
2. `victorbreno-energia-v1`
3. `victorbreno-controlador-v1`
4. `victorbreno-alerta-v1`

O Runner executará cada bot em sequência. Ao final, verifique:
- **Arquivos de Resultado** — JSONs gerados por cada bot
- **Log de Execução** — entradas com status `SUCESSO` dos 4 bots
- **Google Sheets** — nova linha gravada com os dados coletados
- **WhatsApp** — mensagem de alerta recebida

---

## Variáveis e Padrões de Código

### Detecção automática de ambiente

Todos os bots detectam automaticamente se estão rodando localmente ou no Maestro:
```python
try:
    maestro = BotMaestroSDK.from_sys_args()
    execution = maestro.get_execution()
    MAESTRO_ATIVO = True
except Exception:
    maestro = None
    execution = None
    MAESTRO_ATIVO = False
```

### Leitura do artefato mais recente

O `bot_controlador` filtra e ordena os artefatos por ID para garantir que sempre usa os dados da execução mais recente:
```python
ambiental_artifacts = [
    a for a in artifacts
    if a.name == "telemetria_ambiental.json"
]
ambiental_artifacts.sort(key=lambda x: x.id, reverse=True)
name, content = maestro.get_artifact(ambiental_artifacts[0].id)
```

---

## .gitignore

O arquivo `.gitignore` deve conter:

.env
config/oauth_credentials.json
config/token_sheets.json
pycache/
*.pyc
venv/

---

## Tecnologias Utilizadas

- [Python 3.11](https://www.python.org)
- [BotCity Framework Web](https://botcity.dev)
- [BotCity Maestro SDK](https://botcity.dev)
- [Selenium 4.18.1](https://selenium.dev) — dependência do BotCity Framework Web
  (versão fixada para garantir compatibilidade)
- [Google Sheets API — botcity-googlesheets-plugin](https://pypi.org/project/botcity-googlesheets-plugin)
- [Twilio WhatsApp — botcity-twilio-whatsapp-plugin](https://pypi.org/project/botcity-twilio-whatsapp-plugin)

---

## Autor

**Victor Breno Carvalho da Silva**  
Bolsista de P&DI — IFAM  
Projeto Final: AX Academy · Digital Transformation  
Prof. Raimundo Barreto · Mentor: Anderson Gadelha Fontoura