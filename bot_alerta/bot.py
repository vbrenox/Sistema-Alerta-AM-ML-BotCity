import json
import os
import gspread
from dotenv import load_dotenv
from twilio.rest import Client
from datetime import datetime
from google.oauth2.service_account import Credentials
from botcity.maestro import BotMaestroSDK, AutomationTask

# Maestro
try:
    maestro = BotMaestroSDK.from_sys_args()
    execution = maestro.get_execution()
    MAESTRO_ATIVO = True
except Exception:
    maestro = None
    execution = None
    MAESTRO_ATIVO = False

# Carrega variáveis do .env
load_dotenv()

TWILIO_SID   = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM  = os.getenv("TWILIO_FROM")
TWILIO_TO    = os.getenv("TWILIO_TO")

# Configurações
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

BOT_DIR          = os.path.dirname(os.path.abspath(__file__))
RAIZ             = os.path.dirname(BOT_DIR)
CREDENTIALS_PATH = os.path.join(RAIZ, "config", "credentials.json")
SHEET_NAME       = "SistemaAlertaAM"
OUTPUT_PATH      = "alerta_enviado.txt"


def carregar_dados():
    # Lê a última linha gravada pelo bot controlador no Google Sheets
    creds  = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)

    planilha  = client.open(SHEET_NAME)
    aba       = planilha.sheet1
    registros = aba.get_all_records()

    if not registros:
        print("[BOT ALERTA] Planilha vazia!")
        return {}, {}

    ultima_linha = registros[-1]
    print(f"[BOT ALERTA] Dados lidos do Sheets: {ultima_linha}")

    # Reconstrói os dicionários no mesmo formato dos JSONs
    ambiental = {
        "timestamp"        : ultima_linha.get("Timestamp"),
        "rio_negro_manaus" : ultima_linha.get("Rio Negro (m)"),
        "focos_incendio_am": ultima_linha.get("Focos AM"),
        "iqar_manaus"      : ultima_linha.get("IQAr"),
        "iqar_nivel"       : ultima_linha.get("Nível IQAr")
    }

    energia = {
        "balbina_volume_util": ultima_linha.get("Balbina (%)"),
        "bandeira_tarifaria" : ultima_linha.get("Bandeira"),
        "impacto_tarifa"     : ultima_linha.get("Impacto Tarifa")
    }

    return ambiental, energia


def montar_mensagem(ambiental, energia):
    # Monta a mensagem de alerta com todos os dados coletados

    balbina      = energia.get("balbina_volume_util", "N/A")
    bandeira     = energia.get("bandeira_tarifaria", "Desconhecida")
    bandeira_msg = energia.get("impacto_tarifa", "Sem Info")
    focos        = ambiental.get("focos_incendio_am", "0")
    rio          = ambiental.get("rio_negro_manaus", "N/A")
    iqar_valor   = ambiental.get("iqar_manaus", 0)
    iqar_nivel   = ambiental.get("iqar_nivel", "Indeterminado")
    data_hora    = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Classifica os focos de incêndio
    focos_num = int(focos) if str(focos).isdigit() else 0
    if focos_num == 0:
        focos_label = "[NORMAL]- Sem foco nas últimas 48h "
    elif focos_num <= 20:
        focos_label = f"[BAIXO]- {focos_num} focos nas últimas 48h"
    elif focos_num <= 50:
        focos_label = f"[MODERADO]- {focos_num} focos nas últimas 48h"
    else:
        focos_label = f"[ALTO]- {focos_num} focos nas últimas 48h"

    # Frase contextual do IQAr
    iqar_num = int(iqar_valor) if str(iqar_valor).isdigit() else 0
    if iqar_num <= 50:
        frase_iqar = "Ar limpo! Ótimo dia para atividades ao ar livre."
    elif iqar_num <= 100:
        frase_iqar = "Qualidade moderada. Hidrate-se bem e prefira ambientes ventilados."
    elif iqar_num <= 150:
        frase_iqar = "Atenção! Crianças e idosos devem evitar exposição prolongada."
    else:
        frase_iqar = "Ar perigoso! Recomendado o uso de máscara."

    # Frase contextual da Balbina
    try:
        balbina_num = float(balbina)
    except Exception:
        balbina_num = 100

    if balbina_num < 30:
        frase_balbina = "Represa Balbina em nível crítico! Isso pode significar aumento na sua conta de luz em breve, controle seu consumo imediatamente!"
    elif balbina_num < 50:
        frase_balbina = "Represa Balbina abaixo da metade. Fique de olho na sua conta de luz, o risco de cobrança extra ainda existe, controle seu consumo."
    else:
        frase_balbina = "Represa Balbina em nível confortável. Sem risco de aumento na conta de luz por agora."

    # Status geral
    if focos_num > 50 or iqar_num > 150 or balbina_num < 30:
        status = "[ALERTA CRÍTICO]"
    elif focos_num > 20 or iqar_num > 100 or balbina_num < 50:
        status = "[ATENÇÃO]"
    else:
        status = "[NORMAL]"

    # Monta a mensagem final
    msg = (
        f"*Sistema de Alerta Energético e Ambiental - AM*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"UHE Balbina: {balbina}% vol. útil\n"
        f"Bandeira: {bandeira} - {bandeira_msg}\n\n"
        f"Focos de incêndio AM: {focos_label}\n"
        f"Rio Negro: {rio}\n"
        f"IQAr: {iqar_valor} - {iqar_nivel}, {frase_iqar}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Status Geral: {status}\n\n"
        f"{frase_balbina}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n" 
        f"Amazonas • {data_hora}"
    )
    return msg


def enviar_whatsapp(mensagem):
    # Envia a mensagem de alerta via Twilio WhatsApp
    if not TWILIO_SID or not TWILIO_TOKEN:
        print("[BOT ALERTA] Credenciais Twilio não encontradas!")
        return

    client  = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_FROM,
        body=mensagem,
        to=TWILIO_TO
    )
    print(f"[BOT ALERTA] Alerta enviado! SID: {message.sid}")
    print("\n--- Mensagem Enviada ---\n")
    print(mensagem)


def main():
    print("[BOT ALERTA] Carregando dados do Google Sheets...")
    ambiental, energia = carregar_dados()

    print("[BOT ALERTA] Montando mensagem...")
    mensagem = montar_mensagem(ambiental, energia)

    print("[BOT ALERTA] Enviando alerta via WhatsApp...")
    enviar_whatsapp(mensagem)

    # Salva a mensagem como artefato pro Maestro
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(mensagem)

    if MAESTRO_ATIVO:
        maestro.post_artifact(
            task_id=execution.task_id,
            artifact_name="alerta_enviado.txt",
            filepath=OUTPUT_PATH
        )
        maestro.finish_task(
            task_id=execution.task_id,
            status=AutomationTask.Status.SUCCESS,
            message="Alerta enviado com sucesso!"
        )


if __name__ == "__main__":
    main()