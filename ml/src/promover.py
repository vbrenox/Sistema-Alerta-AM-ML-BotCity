import mlflow
from pathlib import Path
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parent.parent
mlflow.set_tracking_uri(f"file:///{ROOT}/mlruns".replace("\\", "/"))

c = MlflowClient()

# Busca a versão mais recente do modelo
versoes = c.get_latest_versions("previsor_vazao_balbina")
versao_mais_recente = max(versoes, key=lambda v: int(v.version)).version

c.set_registered_model_alias("previsor_vazao_balbina", "production", versao_mais_recente)
print(f"Alias @production atribuido a versao {versao_mais_recente}!")