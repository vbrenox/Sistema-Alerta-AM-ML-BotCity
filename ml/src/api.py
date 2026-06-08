import mlflow
import mlflow.pyfunc
import numpy as np
import os
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

modelo = {}
stats_mes = {}

STATS_MES = {
    1:  {"media": 278.0,  "std": 15.0},
    2:  {"media": 290.0,  "std": 20.0},
    3:  {"media": 850.0,  "std": 180.0},
    4:  {"media": 1100.0, "std": 150.0},
    5:  {"media": 1150.0, "std": 130.0},
    6:  {"media": 1050.0, "std": 120.0},
    7:  {"media": 900.0,  "std": 100.0},
    8:  {"media": 700.0,  "std": 90.0},
    9:  {"media": 450.0,  "std": 80.0},
    10: {"media": 300.0,  "std": 30.0},
    11: {"media": 280.0,  "std": 20.0},
    12: {"media": 278.0,  "std": 15.0},
}

class DadosEntrada(BaseModel):
    val_nivelmontante: float = Field(..., example=49.78)
    val_niveljusante:  float = Field(..., example=27.02)
    val_vazaoafluente: float = Field(..., example=2192.0)
    mes:               int   = Field(..., example=5)
    dia:               int   = Field(..., example=22)
    hora:              int   = Field(..., example=10)
    ano:               int   = Field(..., example=2026)
    lag_1h:            float = Field(..., example=1167.0)
    lag_6h:            float = Field(..., example=1150.0)
    lag_24h:           float = Field(..., example=1100.0)
    lag_168h:          float = Field(..., example=950.0)
    media_6h:          float = Field(..., example=1155.0)
    media_24h:         float = Field(..., example=1080.0)
    rio_negro_m:       float = Field(..., example=25.63)
    focos_am:          int   = Field(..., example=2)
    iqar:              int   = Field(..., example=28)

def classificar_severidade(vazao_prevista, mes, iso_score):
    stats = STATS_MES.get(mes, {"media": 600.0, "std": 300.0})
    z = abs((vazao_prevista - stats["media"]) / stats["std"])
    iso_anomalia = iso_score is not None and iso_score < -0.04
    z_alto = z > 2.5

    if iso_anomalia and z_alto:
        return "CRITICO" if iso_score < -0.04 else "ALTO"
    elif iso_anomalia or z_alto:
        return "MODERADO"
    return "NORMAL"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if os.path.exists("/.dockerenv"):
            MLRUNS_PATH = "file:///app/ml/mlruns"
            EXP_BASE = "/app/ml/mlruns"
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mlruns"))
            MLRUNS_PATH = f"file:///{base.replace(os.sep, '/')}"
            EXP_BASE = base

        mlflow.set_tracking_uri(MLRUNS_PATH)
        print(f"MLflow URI: {MLRUNS_PATH}")

        # Busca o modelo XGBoost mais recente pelo path
        import pickle, glob
        modelos = glob.glob(os.path.join(EXP_BASE, "**", "model.pkl"), recursive=True)
        modelos.sort(key=os.path.getmtime, reverse=True)

        if not modelos:
            raise Exception("Nenhum modelo encontrado em mlruns")

        modelo_path = os.path.dirname(modelos[0])
        print(f"Modelo encontrado: {modelo_path}")

        modelo["pipeline"] = mlflow.pyfunc.load_model(modelo_path)
        modelo["uri"] = modelo_path
        print("[OK] Modelo carregado!")
    except Exception as e:
        print(f"Erro ao carregar modelo: {e}")
        modelo["pipeline"] = None
        modelo["uri"] = None
    yield
    modelo.clear()

app = FastAPI(
    title="Sistema de Alerta Energético e Ambiental AM",
    description="Previsão de vazão + detecção de anomalia híbrida (XGBoost + IsolationForest + Z-score sazonal)",
    version="2.0.0",
    lifespan=lifespan,
)

@app.get("/saude")
def saude():
    if modelo.get("pipeline") is None:
        raise HTTPException(status_code=500, detail="Modelo nao carregado.")
    return {"ok": True, "modelo": modelo["uri"]}

@app.post("/predict")
def predict(dados: DadosEntrada):
    if modelo.get("pipeline") is None:
        raise HTTPException(status_code=500, detail="Modelo nao disponivel.")

    features = [
        "val_nivelmontante", "val_niveljusante", "val_vazaoafluente",
        "mes", "dia", "hora", "ano",
        "lag_1h", "lag_6h", "lag_24h", "lag_168h",
        "media_6h", "media_24h"
    ]

    dados_dict = dados.model_dump()
    df = pd.DataFrame([{f: dados_dict[f] for f in features}])

    try:
        vazao_prevista = float(modelo["pipeline"].predict(df)[0])
        severidade = classificar_severidade(vazao_prevista, dados.mes, None)
        anomalia = severidade != "NORMAL"

        return {
            "vazao_prevista_m3s": round(vazao_prevista, 2),
            "anomalia": anomalia,
            "severidade": severidade,
            "mes_referencia": dados.mes,
            "rio_negro_m": dados.rio_negro_m,
            "focos_am": dados.focos_am,
            "iqar": dados.iqar
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))