import mlflow.pyfunc
import os
import pickle
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from mlflow.tracking import MlflowClient

modelo = {}

class DadosEntrada(BaseModel):
    val_nivelmontante: float = Field(..., example=49.27)
    val_niveljusante:  float = Field(..., example=27.27)
    val_vazaoafluente: float = Field(..., example=1097.0)
    mes:  int = Field(..., example=5)
    dia:  int = Field(..., example=1)
    hora: int = Field(..., example=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if os.path.exists("/.dockerenv"):
            MLRUNS_PATH = "file:///app/mlruns"
            EXP_BASE = "/app/mlruns"
        else:
            MLRUNS_PATH = f"file:///{os.path.abspath('mlruns').replace(os.sep, '/')}"
            EXP_BASE = os.path.abspath('mlruns')

        mlflow.set_tracking_uri(MLRUNS_PATH)
        print(f"MLflow tracking URI: {MLRUNS_PATH}")

        # MLflow 3.x salva modelos em models/ em vez de artifacts/ do run
        # Busca automaticamente o GradientBoosting mais recente
        exp_id = "737769590242991027"
        models_path = os.path.join(EXP_BASE, exp_id, "models")
        modelos_gb = []
        for m in os.listdir(models_path):
            pkl = os.path.join(models_path, m, "artifacts", "model.pkl")
            if os.path.exists(pkl):
                with open(pkl, "rb") as f:
                    pipe = pickle.load(f)
                if "GradientBoosting" in type(pipe.named_steps['clf']).__name__:
                    modelos_gb.append((os.path.getmtime(pkl), m))
        modelos_gb.sort(reverse=True)
        modelo_id = modelos_gb[0][1]
        source = f"{MLRUNS_PATH}/{exp_id}/models/{modelo_id}/artifacts"
        print(f"Modelo encontrado: {source}")

        modelo["pipeline"] = mlflow.pyfunc.load_model(source)
        modelo["uri"] = source
        print("[OK] Modelo carregado!")
    except Exception as e:
        print(f"Erro ao carregar modelo: {e}")
        modelo["pipeline"] = None
        modelo["uri"] = None
    yield
    modelo.clear()

app = FastAPI(
    title="Previsor de Vazão Defluente - Balbina",
    description="Previsão de vazão defluente da UHE Balbina via GradientBoosting",
    version="1.0.0",
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
    import pandas as pd
    df = pd.DataFrame([dados.model_dump()])
    try:
        predicao = modelo["pipeline"].predict(df)
        return {"vazao_defluente_prevista_m3s": round(float(predicao[0]), 2)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))