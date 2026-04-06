import json
import os
from datetime import datetime
from botcity.maestro import BotMaestroSDK, AutomationTask
from botcity.plugins.googlesheets import BotGoogleSheetsPlugin

# Maestro
try:
    maestro = BotMaestroSDK.from_sys_args()
    execution = maestro.get_execution()
    MAESTRO_ATIVO = True
except Exception:
    maestro = None
    execution = None
    MAESTRO_ATIVO = False

# Configurações
SHEET_ID = "1wG6icQpwUmfjaL0KruwXelH9iAKV_UfRjwOURZXJDqE"

# Caminhos dos arquivos
BOT_DIR          = os.path.dirname(os.path.abspath(__file__))
RAIZ             = os.path.dirname(BOT_DIR)
CREDENTIALS_PATH = os.path.join(BOT_DIR, "config", "oauth_credentials.json")
AMBIENTAL_PATH   = os.path.join(RAIZ, "bot_ambiental", "telemetria_ambiental.json")
ENERGIA_PATH     = os.path.join(RAIZ, "bot_energia", "telemetria_energia.json")



def carregar_dados():
    if MAESTRO_ATIVO:
        artifacts = maestro.list_artifacts()
        
        # Filtra e pega o artefato mais recente de cada tipo
        ambiental_artifacts = [a for a in artifacts if a.name == "telemetria_ambiental.json"]
        energia_artifacts   = [a for a in artifacts if a.name == "telemetria_energia.json"]
        
        # Ordena por ID decrescente — ID maior = mais recente
        ambiental_artifacts.sort(key=lambda x: x.id, reverse=True)
        energia_artifacts.sort(key=lambda x: x.id, reverse=True)
        
        # Baixa apenas o mais recente de cada
        name, content = maestro.get_artifact(ambiental_artifacts[0].id)
        with open(name, "wb") as f:
            f.write(content)

        name, content = maestro.get_artifact(energia_artifacts[0].id)
        with open(name, "wb") as f:
            f.write(content)

        with open("telemetria_ambiental.json", encoding="utf-8") as f:
            ambiental = json.load(f)
        with open("telemetria_energia.json", encoding="utf-8") as f:
            energia = json.load(f)

    else:
        BOT_DIR = os.path.dirname(os.path.abspath(__file__))
        RAIZ    = os.path.dirname(BOT_DIR)
        with open(os.path.join(RAIZ, "bot_ambiental", "telemetria_ambiental.json"), encoding="utf-8") as f:
            ambiental = json.load(f)
        with open(os.path.join(RAIZ, "bot_energia", "telemetria_energia.json"), encoding="utf-8") as f:
            energia = json.load(f)

    return ambiental, energia



def definir_status(ambiental, energia):
    # Cruza dados ambientais e energéticos e define o status do sistema

    # Extrai valores — converte string para número onde necessário
    valor_focos = ambiental.get("focos_incendio_am", "0")
    focos    = int(valor_focos) if str(valor_focos).isdigit() else 0
    iqar     = int(ambiental.get("iqar_manaus", 0))
    balbina  = float(energia.get("balbina_volume_util", 100))
    bandeira = energia.get("bandeira_tarifaria", "🟩 Verde")

    # Regra 1 — Alerta Crítico: risco energético e tarifário simultâneos
    if balbina < 30 and "Verde" not in bandeira:
        return "[ALERTA CRÍTICO]"

    # Regra 2 — Atenção: qualquer indicador ambiental ou energético elevado
    elif focos > 20 or iqar > 100 or balbina < 50:
        return "[ATENÇÃO]"

    # Regra 3 — Normal: todos os indicadores dentro do esperado
    else:
        return "[NORMAL]"


def gravar_sheets(ambiental, energia, status):
    # Instancia o plugin com o credentials.json e o ID da planilha
    bot_sheets = BotGoogleSheetsPlugin(CREDENTIALS_PATH, SHEET_ID)

    # Monta a linha com todos os dados coletados
    nova_linha = [
        ambiental.get("timestamp"),
        ambiental.get("rio_negro_manaus"),
        ambiental.get("focos_incendio_am"),
        ambiental.get("iqar_manaus"),
        ambiental.get("iqar_nivel"),
        energia.get("balbina_volume_util"),
        energia.get("bandeira_tarifaria"),
        energia.get("impacto_tarifa"),
        status
    ]

    # Insere a linha no final da planilha
    bot_sheets.add_row(nova_linha)
    print(f"[BOT CONTROLADOR] Linha inserida: {nova_linha}")


def main():
    print("[BOT CONTROLADOR] Carregando dados dos bots...")
    ambiental, energia = carregar_dados()

    print("[BOT CONTROLADOR] Definindo status do sistema...")
    status = definir_status(ambiental, energia)
    print(f"[BOT CONTROLADOR] Status: {status}")

    print("[BOT CONTROLADOR] Gravando no Google Sheets...")
    gravar_sheets(ambiental, energia, status)

    print("[BOT CONTROLADOR] Concluído!")

    # Envia o JSON ambiental como artefato pro Maestro
    if MAESTRO_ATIVO:
        maestro.post_artifact(
            task_id=execution.task_id,
            artifact_name="telemetria_ambiental.json",
            filepath="telemetria_ambiental.json"
        )
        maestro.post_artifact(
            task_id=execution.task_id,
            artifact_name="telemetria_energia.json",
            filepath="telemetria_energia.json"
        )
        
        maestro.new_log_entry(
            activity_label="victorbreno-execucao-v1-log",
            values={
                "bot": "bot_controlador",
                "status": "SUCESSO",
                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "mensagem": f"Status definido: {status} | Linha gravada no Sheets"
            }
        )
        maestro.finish_task(
            task_id=execution.task_id,
            status=AutomationTask.finish_status.SUCCESS,
            message=f"Controlador concluído! Status: {status}"
        )


if __name__ == "__main__":
    main()