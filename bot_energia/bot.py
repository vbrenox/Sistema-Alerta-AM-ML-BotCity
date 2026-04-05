import csv
import json
import os
import time
import glob
from datetime import datetime
from botcity.web import WebBot, Browser, By
from botcity.web.browsers.chrome import default_options
from botcity.maestro import BotMaestroSDK, AutomationTask
from webdriver_manager.chrome import ChromeDriverManager

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
URL_ONS      = "https://dados.ons.org.br/dataset/dados_hidrologicos_ho"
URL_ANEEL    = "https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias"
OUTPUT_PATH  = "telemetria_energia.json"

# Pasta do próprio bot — funciona local e no Maestro
BOT_DIR = os.path.dirname(os.path.abspath(__file__))


def aguardar_download(pasta, nome_parcial, timeout=30):
    # Aguarda o arquivo aparecer na pasta do bot
    inicio = time.time()
    while time.time() - inicio < timeout:
        arquivos = glob.glob(os.path.join(pasta, f"*{nome_parcial}*"))
        arquivos = [a for a in arquivos if not a.endswith(".crdownload")]
        if arquivos:
            return max(arquivos, key=os.path.getctime)
        time.sleep(1)
    return None


def coletar_balbina(bot):
    # Acessa o portal ONS Dados Abertos e baixa o CSV hidráulico do mês atual
    try:
        bot.browse(URL_ONS)
        bot.wait(5000)

        # Gera o nome do dataset do mês atual dinamicamente
        ano_mes  = datetime.now().strftime("%Y-%m")
        nome_csv = f"Dados_Hidrologicos_Horario-{ano_mes}"

        # XPaths dinâmicos com o nome do mês atual
        xpath_explorar = f"//li[contains(.,'{nome_csv}') and contains(.,'CSV')]//a[contains(@class,'dropdown-toggle')]"
        xpath_baixar   = f"//li[contains(.,'{nome_csv}') and contains(.,'CSV')]//ul//li[2]/a"

        # Localiza e rola até o botão Explorar
        btn_explorar = bot.find_element(xpath_explorar, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_explorar)
        bot.wait(1000)

        # Clique 1 — abre o menu dropdown
        btn_explorar.click()
        bot.wait(1000)

        # Localiza e rola até o botão Baixar
        btn_baixar = bot.find_element(xpath_baixar, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_baixar)
        bot.wait(1000)

        # Clique 2 — inicia o download
        btn_baixar.click()
        print("[BOT ENERGIA] Download do CSV Balbina iniciado...")

        # Nome real do arquivo gerado pelo Chrome
        ano_mes_underscore = datetime.now().strftime("%Y_%m")
        arquivo = aguardar_download(BOT_DIR, f"DADOS_HIDROLOGICOS_HO_{ano_mes_underscore}")
        if not arquivo:
            return {"balbina_volume_util": "Erro: download não concluído"}

        # Processa o CSV — filtra linha da UHE Balbina
        balbina_volume = "Indisponível"
        with open(arquivo, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if "BALBINA" in str(row).upper():
                    balbina_volume = row.get("val_volumeutil", "Indisponível")
                    break

        print(f"[BOT ENERGIA] CSV Balbina processado: {arquivo}")
        return {"balbina_volume_util": balbina_volume}

    except Exception as e:
        return {"balbina_volume_util": f"Erro: {str(e)[:50]}"}


def coletar_bandeira(bot):
    # Acessa ANEEL Dados Abertos e baixa o CSV de bandeiras tarifárias
    try:
        bot.browse(URL_ANEEL)
        bot.wait(5000)

        # XPaths do botão Explorar e Baixar do CSV de acionamento
        xpath_explorar = "//*[@id='dataset-resources']/ul/li[4]/div/a"
        xpath_baixar   = "//*[@id='dataset-resources']/ul/li[4]/div/ul/li[2]/a"

        # Localiza e rola até o botão Explorar
        btn_explorar = bot.find_element(xpath_explorar, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_explorar)
        bot.wait(1000)

        # Clique 1 — abre o menu dropdown
        btn_explorar.click()
        bot.wait(1000)

        # Localiza e rola até o botão Baixar
        btn_baixar = bot.find_element(xpath_baixar, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_baixar)
        bot.wait(1000)

        # Clique 2 — inicia o download
        btn_baixar.click()
        print("[BOT ENERGIA] Download do CSV Bandeira iniciado...")

        # Aguarda o arquivo aparecer na pasta do bot
        arquivo = aguardar_download(BOT_DIR, "bandeira-tarifaria-acionamento")
        if not arquivo:
            return {"bandeira_tarifaria": "Indisponível", "impacto_tarifa": "Erro: download não concluído"}

        # CSV da ANEEL usa encoding latin-1 — padrão de sistemas gov brasileiros
        with open(arquivo, encoding="latin-1") as f:
            reader = csv.DictReader(f, delimiter=";")
            rows = list(reader)
            if rows:
                ultima = rows[-1]
                bandeira_texto = ultima.get("DscBandeiraTarifaria", "").strip().upper()

        # Classifica do mais específico pro mais genérico
        if "VERMELHA 2" in bandeira_texto or "PATAMAR 2" in bandeira_texto:
            bandeira = "Vermelha 2"
            impacto  = "Acréscimo de R$ 7,87 por 100 kWh"
        elif "VERMELHA" in bandeira_texto:
            bandeira = "Vermelha 1"
            impacto  = "Acréscimo de R$ 4,46 por 100 kWh"
        elif "AMARELA" in bandeira_texto:
            bandeira = "Amarela"
            impacto  = "Acréscimo de R$ 1,88 por 100 kWh"
        else:
            bandeira = "Verde"
            impacto  = "Sem custo adicional na conta de luz"

        print(f"[BOT ENERGIA] CSV Bandeira processado: {arquivo}")
        return {"bandeira_tarifaria": bandeira, "impacto_tarifa": impacto}

    except Exception as e:
        return {"bandeira_tarifaria": "Indisponível", "impacto_tarifa": f"Erro: {str(e)[:50]}"}


def main():
    bot = WebBot()
    bot.headless = False
    bot.browser = Browser.CHROME

    # Chrome configurado pra baixar direto na pasta do bot
    options = default_options(
        headless=False,
        download_folder_path=BOT_DIR
    )
    options.add_argument("--deny-permission-prompts")
    bot.options = options

    bot.driver_path = ChromeDriverManager().install()
    bot.start_browser()

    # Maximiza a janela após abrir
    bot.driver.maximize_window()
    bot.wait(1000)

    try:
        print("[BOT ENERGIA] Coletando dados da UHE Balbina (ONS)...")
        balbina = coletar_balbina(bot)

        print("[BOT ENERGIA] Coletando bandeira tarifária (ANEEL)...")
        bandeira = coletar_bandeira(bot)

        # Consolida os dados num único dicionário
        telemetria = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
            **balbina,
            **bandeira
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(telemetria, f, ensure_ascii=False, indent=4)

        print(f"[BOT ENERGIA] Telemetria salva em {OUTPUT_PATH}")
        print(telemetria)

        # Remove os CSVs após salvar a telemetria com sucesso
        for arquivo in glob.glob(os.path.join(BOT_DIR, "*.csv")):
            os.remove(arquivo)
            print(f"[BOT ENERGIA] Arquivo removido: {os.path.basename(arquivo)}")

        # Envia os artefatos pro Maestro
        if MAESTRO_ATIVO:
            maestro.post_artifact(
                task_id=execution.task_id,
                artifact_name="telemetria_energia.json",
                filepath=OUTPUT_PATH
            )
            maestro.finish_task(
                task_id=execution.task_id,
                status=AutomationTask.Status.SUCCESS,
                message="Coleta energética concluída!"
            )

    except Exception as e:
        print(f"[BOT ENERGIA] Erro: {e}")
        if MAESTRO_ATIVO:
            maestro.finish_task(
                task_id=execution.task_id,
                status=AutomationTask.Status.FAILED,
                message=f"Erro: {str(e)}"
            )
    finally:
        bot.stop_browser()


if __name__ == "__main__":
    main()