import json
import os
import requests
import re
from datetime import datetime
from botcity.maestro import BotMaestroSDK, AutomationTask
from botcity.plugins.googlesheets import BotGoogleSheetsPlugin
from evidently import Report
from evidently.presets import DataDriftPreset
import pandas as pd

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
SHEET_ID     = "1wG6icQpwUmfjaL0KruwXelH9iAKV_UfRjwOURZXJDqE"
API_URL      = "http://localhost:8000/predict"
EVIDENTLY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relatorio_drift.html")

BOT_DIR          = os.path.dirname(os.path.abspath(__file__))
RAIZ             = os.path.dirname(BOT_DIR)
CREDENTIALS_PATH = os.path.join(BOT_DIR, "config", "oauth_credentials.json")
BASELINE_PATH    = os.path.join(RAIZ, "ml", "data", "processed", "balbina_processado.csv")


def carregar_dados():
    if MAESTRO_ATIVO:
        artifacts = maestro.list_artifacts()

        ambiental_artifacts = [a for a in artifacts if a.name == "telemetria_ambiental.json"]
        energia_artifacts   = [a for a in artifacts if a.name == "telemetria_energia.json"]

        ambiental_artifacts.sort(key=lambda x: x.id, reverse=True)
        energia_artifacts.sort(key=lambda x: x.id, reverse=True)

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
        with open(os.path.join(RAIZ, "bot_ambiental", "telemetria_ambiental.json"), encoding="utf-8") as f:
            ambiental = json.load(f)
        with open(os.path.join(RAIZ, "bot_energia", "telemetria_energia.json"), encoding="utf-8") as f:
            energia = json.load(f)

    return ambiental, energia


def extrair_rio_negro(valor):
    # Extrai valor numérico do nível do Rio Negro ex: "25.63 m" -> 25.63
    try:
        match = re.search(r"[\d.]+", str(valor))
        return float(match.group()) if match else 25.0
    except Exception:
        return 25.0


def chamar_predict(ambiental, energia):
    # Monta payload e chama o endpoint /predict
    agora = datetime.now()

    try:
        vazao_atual = float(energia.get("balbina_vazao_m3s", 500))
    except Exception:
        vazao_atual = 500.0

    try:
        focos = int(ambiental.get("focos_incendio_am", 0)) if str(ambiental.get("focos_incendio_am", 0)).isdigit() else 0
    except Exception:
        focos = 0

    try:
        iqar = int(ambiental.get("iqar_manaus", 28))
    except Exception:
        iqar = 28

    payload = {
        "val_nivelmontante": 49.0,
        "val_niveljusante":  27.0,
        "val_vazaoafluente": vazao_atual * 1.5,
        "mes":      agora.month,
        "dia":      agora.day,
        "hora":     agora.hour,
        "ano":      agora.year,
        "lag_1h":   vazao_atual,
        "lag_6h":   vazao_atual,
        "lag_24h":  vazao_atual,
        "lag_168h": vazao_atual,
        "media_6h":  vazao_atual,
        "media_24h": vazao_atual,
        "rio_negro_m": extrair_rio_negro(ambiental.get("rio_negro_manaus", "25.0 m")),
        "focos_am": focos,
        "iqar":     iqar
    }

    print(f"[BOT CONTROLADOR] Chamando /predict com vazão atual: {vazao_atual} m³/s")
    response = requests.post(API_URL, json=payload, timeout=10)
    response.raise_for_status()
    resultado = response.json()
    print(f"[BOT CONTROLADOR] Predição: {resultado}")
    return resultado


def gerar_evidently(energia):
    try:
        df_baseline = pd.read_csv(BASELINE_PATH, sep=";")
        df_baseline = df_baseline[["val_vazaodefluente"]].dropna()

        try:
            vazao_atual = float(energia.get("balbina_vazao_m3s", 500))
        except Exception:
            vazao_atual = 500.0

        df_atual = pd.DataFrame({"val_vazaodefluente": [vazao_atual]})

        report = Report(metrics=[DataDriftPreset()])
        result = report.run(reference_data=df_baseline, current_data=df_atual)
        result.save_html(EVIDENTLY_PATH)
        print(f"[BOT CONTROLADOR] Relatório Evidently salvo em: {EVIDENTLY_PATH}")
    except Exception as e:
        print(f"[BOT CONTROLADOR] Erro ao gerar Evidently: {e}")


def gravar_sheets(ambiental, energia, predicao):
    bot_sheets = BotGoogleSheetsPlugin(CREDENTIALS_PATH, SHEET_ID)

    severidade = predicao.get("severidade", "NORMAL")
    vazao_prev = predicao.get("vazao_prevista_m3s", "N/A")
    anomalia   = predicao.get("anomalia", False)

    status_ml = f"[ML] {severidade}"

    nova_linha = [
        ambiental.get("timestamp"),
        ambiental.get("rio_negro_manaus"),
        ambiental.get("focos_incendio_am"),
        ambiental.get("iqar_manaus"),
        ambiental.get("iqar_nivel"),
        energia.get("balbina_volume_util"),
        energia.get("balbina_vazao_m3s", "N/A"),
        energia.get("bandeira_tarifaria"),
        energia.get("impacto_tarifa"),
        str(round(vazao_prev, 2)) if isinstance(vazao_prev, float) else vazao_prev,
        str(anomalia),
        severidade,
        status_ml
    ]

    bot_sheets.add_row(nova_linha)
    print(f"[BOT CONTROLADOR] Linha inserida: {nova_linha}")
    return status_ml


def main():
    print("[BOT CONTROLADOR] Carregando dados dos bots...")
    ambiental, energia = carregar_dados()

    print("[BOT CONTROLADOR] Chamando endpoint ML...")
    predicao = chamar_predict(ambiental, energia)
    status_ml = predicao.get("severidade", "NORMAL")

    print("[BOT CONTROLADOR] Gravando no Google Sheets...")
    gravar_sheets(ambiental, energia, predicao)

    print("[BOT CONTROLADOR] Gerando relatório Evidently...")
    gerar_evidently(energia)

    print(f"[BOT CONTROLADOR] Concluído! Status ML: {status_ml}")

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
        if os.path.exists(EVIDENTLY_PATH):
            maestro.post_artifact(
                task_id=execution.task_id,
                artifact_name="relatorio_drift.html",
                filepath=EVIDENTLY_PATH
            )
        maestro.new_log_entry(
            activity_label="victorbreno-execucao-v1-log",
            values={
                "bot": "bot_controlador",
                "status": "SUCESSO",
                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "mensagem": f"Severidade ML: {status_ml} | Vazão prevista: {predicao.get('vazao_prevista_m3s')} m³/s"
            }
        )
        maestro.finish_task(
            task_id=execution.task_id,
            status=AutomationTask.finish_status.SUCCESS,
            message=f"Controlador ML concluído! Severidade: {status_ml}"
        )


if __name__ == "__main__":
    main()