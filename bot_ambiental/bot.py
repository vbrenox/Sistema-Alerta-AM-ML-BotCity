import json
import os
import re
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
URL_SACE     = "https://www.sgb.gov.br/sace/sace_nivel/"
URL_INPE     = "https://terrabrasilis.dpi.inpe.br/queimadas/situacao-atual/situacao_atual/"
URL_INPE_48H = "https://terrabrasilis.dpi.inpe.br/queimadas/situacao-atual/media/focos_estado_48h.html"
URL_IQAR     = "https://www.aqi.in/pt/dashboard/brazil/amazonas/manaus"
OUTPUT_PATH  = "telemetria_ambiental.json"


def coletar_rio_negro(bot):
    # Acessa o SACE e navega até a estação de Manaus clicando nos links
    try:
        bot.browse(URL_SACE)
        bot.wait(3000)

        # Clica em "Lista" na linha do Amazonas via DOM
        xpath_lista = "//span[contains(@class,'bacia-nome') and contains(text(),'Amazonas')]/following-sibling::a[text()='Lista']"
        btn_lista = bot.find_element(xpath_lista, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_lista)
        bot.wait(1000)
        btn_lista.click()
        bot.wait(3000)

        # Remove target="_blank" para abrir na mesma aba
        bot.execute_javascript(
            "document.querySelector('a.estacao-link[href*=\"s=33\"]').removeAttribute('target');"
        )
        bot.wait(500)

        # Clica em Manaus — s=33 é o código único da estação de Manaus no SACE
        xpath_manaus = "//a[contains(@class,'estacao-link') and contains(@href,'s=33')]"
        btn_manaus = bot.find_element(xpath_manaus, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_manaus)
        bot.wait(1000)
        btn_manaus.click()
        bot.wait(3000)

        # Coleta o valor da cota no gráfico
        elemento = bot.find_element("/html/body/div/h2", By.XPATH)
        texto = elemento.text.strip().replace('\n', '')

        # O site retorna o valor em cm com ponto de milhar ex: 2.563
        # Removemos o ponto e dividimos por 100 pra converter pra metros
        match = re.search(r"[\d.]+", texto)
        if match:
            apenas_numeros = match.group().replace(".", "")
            valor_cm = int(apenas_numeros)
            cota = f"{valor_cm / 100:.2f} m"
        else:
            cota = texto

        return {"rio_negro_manaus": cota}

    except Exception as e:
        return {"rio_negro_manaus": f"Erro: {str(e)[:50]}"}


def coletar_focos_inpe(bot):
    # Acessa o INPE, rola até as tabelas, clica em 48h e coleta os focos do AM
    try:
        print("[BOT AMBIENTAL]-[INPE] Acessando portal de situação atual...")
        bot.browse(URL_INPE)
        bot.wait(5000)

        # Rola para baixo até as tabelas de focos aparecerem
        bot.execute_javascript("window.scrollBy(0, 600);")
        bot.wait(2000)

        # Clica no botão das últimas 48h na tabela de focos por estado
        xpath_48h = "//li[@title='Últimas 48 horas' and contains(@onclick,\"'box-estado'\")]"
        btn_48h = bot.find_element(xpath_48h, By.XPATH)
        bot.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn_48h)
        bot.wait(1000)
        btn_48h.click()
        bot.wait(3000)

        # Redireciona para a página com a tabela de focos por estado
        print("[BOT AMBIENTAL]-[INPE] Redirecionando para tabela de focos por estado...")
        bot.browse(URL_INPE_48H)
        bot.wait(3000)

        # XPath localiza a célula ao lado do cabeçalho 'AM' na tabela
        xpath = "//th[text()='AM']/following-sibling::td"
        elemento = bot.find_element(xpath, By.XPATH)
        focos = elemento.text.strip()

        return {"focos_incendio_am": focos}

    except Exception as e:
        print(f"[BOT AMBIENTAL]-[INPE] Erro ao coletar focos: {e}")
        return {"focos_incendio_am": "Sem foco de incêndio nas últimas 48h"}


def coletar_iqar(bot):
    # Acessa o AQI.in e coleta o índice de qualidade do ar de Manaus
    try:
        bot.browse(URL_IQAR)
        bot.wait(5000)

        # Força recarregamento para evitar dados em cache
        bot.execute_javascript("location.reload(true);")
        bot.wait(5000)
        print("[BOT AMBIENTAL]-[IQAr] Página recarregada, CTRL + F5, cache limpo.")

        # XPath do elemento que exibe o número do índice
        xpath = "//*[@id='body-main-wrapper']/div/div[1]/div/div[5]/div/div[1]/div[3]/div[1]/div[1]/div[1]/span"
        elemento = bot.find_element(xpath, By.XPATH)
        valor = elemento.text.strip()

        # Garante que só ficam os dígitos antes de converter
        indice = int("".join(filter(str.isdigit, valor)))

        # Classifica pelo índice AQI internacional
        if indice <= 50:
            nivel = "Bom"
        elif indice <= 100:
            nivel = "Moderado"
        elif indice <= 150:
            nivel = "Insalubre para grupos sensíveis"
        else:
            nivel = "Insalubre"

        return {"iqar_manaus": indice, "iqar_nivel": nivel}

    except Exception as e:
        return {"iqar_manaus": "Indisponível", "iqar_nivel": f"Erro: {str(e)[:50]}"}


def main():
    bot = WebBot()
    bot.headless = False
    bot.browser = Browser.CHROME

    # Chrome configurado com permissões bloqueadas
    options = default_options(headless=False)
    options.add_argument("--deny-permission-prompts")
    bot.options = options

    bot.driver_path = ChromeDriverManager().install()
    bot.start_browser()

    # Maximiza a janela após abrir
    bot.driver.maximize_window()
    bot.wait(1000)

    try:
        print("[BOT AMBIENTAL] Coletando Rio Negro...")
        rio = coletar_rio_negro(bot)

        print("[BOT AMBIENTAL] Coletando focos INPE...")
        focos = coletar_focos_inpe(bot)

        print("[BOT AMBIENTAL] Coletando qualidade do ar...")
        iqar = coletar_iqar(bot)

        # Junta todos os dados coletados num único dicionário
        telemetria = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
            **rio,
            **focos,
            **iqar
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(telemetria, f, ensure_ascii=False, indent=4)

        print(f"[BOT AMBIENTAL] Dados salvos em {OUTPUT_PATH}")
        print(telemetria)

        # Envia o arquivo JSON como artefato pro Maestro
        if MAESTRO_ATIVO:
            maestro.post_artifact(
                task_id=execution.task_id,
                artifact_name="telemetria_ambiental.json",
                filepath=OUTPUT_PATH
            )
            maestro.finish_task(
                task_id=execution.task_id,
                status=AutomationTask.Status.SUCCESS,
                message="Coleta ambiental concluída!"
            )

    except Exception as e:
        print(f"[BOT AMBIENTAL] Erro: {e}")
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