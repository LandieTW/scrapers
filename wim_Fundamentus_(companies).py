#!/usr/bin/env python3

"""
This is an auto-searching script for evaluating investiments in Brazilian 
companies market, using data from Fundamentus website.
"""

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional
from osn_currencies_tools.currency_live import get_exchange_rate
from pprint import pprint
import numpy as np
import pandas as pd
import os
import time
import warnings

# ignoring warning outuputs
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ----------------------------------------------------------------

fundamentus_url = "https://www.fundamentus.com.br/resultado.php"
redentia_url = "https://www.redentia.com.br/ranking/nunca-tiveram-prejuizo"
tradingview_url = "https://br.tradingview.com/markets/stocks-brazil/market-movers-all-stocks/"

# https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/
b3_xlsx = "ClassifSetorial.xlsx"

usd_rate = get_exchange_rate("USD", "BRL")

# ----------------------------------------------------------------


def click(driver, xpath: str, wait_time=10) -> Optional[bool]:
    """Clicks in elements which xpath is given"""
    wait = WebDriverWait(driver, wait_time)
    try:
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(1)
        
        try: 
            element.click()
        except:
            driver.execute_script("arguments[0].click();", element)

    except Exception as e:
        print(f"Error clicking element with XPath {xpath}: \n{e}")


def parse_cell(text: str):
    """Parses a numerical text to float format"""
    text = text.strip()
    is_percent = text.endswith("%")
    if is_percent:
        text = text.removesuffix("%").strip()

    if "," not in text:
        try:
            val = float(text.replace(".", ""))
        except ValueError:
            return text
    else:
        integer, decimal = text.rsplit(",", 1)
        integer = integer.replace(",", "").replace(".", "")
        val = float(f"{integer}.{decimal}")

    return val


# ----------------------------------------------------------------

_this_path = os.path.dirname(os.path.abspath(__file__))
download_path = os.path.join(os.path.expanduser("~"), "Downloads")

edge_options = Options()
edge_options.add_argument("--headless")
edge_options.add_argument("--start-maximized")
edge_options.add_argument("--log-level=3")
edge_options.add_argument("--disable-logging")
edge_options.add_argument("--disable-dev-shm-usage")
edge_options.add_argument("--no-sandbox")
edge_options.add_argument("--disable-gpu")
edge_options.add_argument("--disable-extensions")
edge_options.add_argument("--blink-settings=imagesEnabled=false")

prefs = {"profile.managed_default_content_settings.images": 2,
         "profile.managed_default_content_settings.media_stream": 2,
         "download.default_directory": _this_path,
         "download.prompt_for_download": False,}

edge_options.add_experimental_option('prefs', prefs)

edge_options.page_load_strategy = "eager" 

# ------------------------------------------------------------------

service = Service(os.path.join(_this_path, "msedgedriver.exe"), log_path=os.devnull)

driver = webdriver.Edge(service=service, options=edge_options)
wait = WebDriverWait(driver, 15)

driver.get(fundamentus_url)

fundamentus_version = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/ul[1]/li[5]/a"))).text
if "Mobile" in fundamentus_version:
    click(driver, "/html/body/div[1]/div[1]/div[2]/ul[1]/li[5]/a")

all_windows = driver.window_handles
driver.switch_to.window(all_windows[-1])

header = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/div[2]/table/thead/tr"))).text.split("\n")
header = header[1:]
for h in range(len(header)):
    if header[h] in ["DIV.YIELD", "MRG EBIT", "MRG. LÍQ.", "ROIC", "ROE", "CRESC. REC.5A"]:
        header[h] += " [%]"

fundamentus_table = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/div[2]/table/tbody")))

dados = driver.execute_script(r"""
    const rows = arguments[0].querySelectorAll('tr');
    const result = [];
    for (let row of rows) {

        const cells = row.querySelectorAll('td');
        const rowData = [];

        for (let cell of cells) {
            rowData.push(cell.innerText.trim());
        }

        result.push(rowData);
    }
    return result;
""", fundamentus_table)

driver.get(tradingview_url)

click(driver, xpath="/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[1]/div/div/div/button[5]/span[1]/span")

click(driver, xpath='/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[3]/button')
time.sleep(2)
click(driver, xpath='/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[3]/button')
time.sleep(2)

wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-rowkey]")))
tradingview_table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody[data-testid='selectable-rows-table-body']")))

tradingview_data = driver.execute_script(r"""
    const rows = arguments[0].querySelectorAll('tr');
    const result = {};

    for (let row of rows) {
        const cells = row.querySelectorAll('td');

        if (cells.length > 5) {
            let ticker = cells[0].innerText.trim().split('\n')[0].trim();
            let t_div = cells[7].innerText.trim();

            if (ticker && ticker.length >= 4) {
                result[ticker] = parseInt(t_div, 10);
            }
        }
    }
    return result;
""", tradingview_table)

year_dividend = pd.Series(tradingview_data, name="YEARS DIVIDEND").to_frame()

# ---------------------------------------------------------------

index, lines = [], []
for values in dados:
    index.append(parse_cell(values[0]))
    lines.append([parse_cell(v) for v in values[1:]])

df = pd.DataFrame(lines, columns=header, index=index)

df = df.join(year_dividend)

# ----------------------------------------------------------------

df.rename(columns={'COTAÇÃO': 'PREÇO'}, inplace=True)

for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ----------------------------------------------------------------

b3_xlsx_path = os.path.join(_this_path, b3_xlsx)

df_setor = pd.read_excel(
    b3_xlsx_path,
    header=None,
    skiprows=3,
    usecols="B:G",
    names=["SETOR", "SUBSETOR", "SEGMENTO", "EMPRESA", "CODIGO", "SEGMENTO DE NEGOCIAÇÃO"],
    dtype=str,
)
df_setor = df_setor.replace("", pd.NA)
df_setor = df_setor[df_setor["SETOR"].ne("SETOR ECONÔMICO") & df_setor["CODIGO"].notna()]
df_setor[["SETOR", "SUBSETOR", "SEGMENTO"]] = df_setor[["SETOR", "SUBSETOR", "SEGMENTO"]].ffill()
df_setor = df_setor.reset_index(drop=True)

df = df.apply(pd.to_numeric, errors="coerce")
codigo = df.index.str[:4]
mapa = df_setor.set_index("CODIGO")
for col in ["SETOR", "SUBSETOR", "SEGMENTO"]:
    df[col] = codigo.map(mapa[col])

df = df.dropna(subset=["SETOR", "SUBSETOR", "SEGMENTO"])

# -----------------------------------------------------------------

df_wim = df.copy().reset_index()
df_wim = df_wim.rename(columns={'index': 'TICKER'})

df_wim['SETOR_SUBSETOR_SEGMENTO'] = (
    df_wim['SETOR'].astype(str) + '_' +
    df_wim['SUBSETOR'].astype(str) + '_' +
    df_wim['SEGMENTO'].astype(str)
)

df_wim['RECEITA_PROXY'] = np.where(
    df_wim['PSR'] > 0,
    df_wim['VALOR DE MERCADO'] / df_wim['PSR'],
    df_wim['VALOR DE MERCADO']
)

df_wim['MARKET_SHARE_RECEITA_%'] = (
    df_wim.groupby('SETOR_SUBSETOR_SEGMENTO')['RECEITA_PROXY']
          .transform(lambda s: 100 * s / s.sum())
)

df_wim = df_wim.drop(columns=[
    'PREÇO', 'P/L', 'P/VP', 'PSR', 'DIV.YIELD [%]', 'P/ATIVO', 'P/CAP.GIRO',
    'P/EBIT', 'P/ATIV CIRC.LIQ', 'EV/EBITDA', 'LIQ. CORR.', 'PATRIM. LÍQ',
    'VALOR DE MERCADO', 'YEARS DIVIDEND'
    ])

df_wim = df_wim[
    (df_wim['MRG EBIT [%]'] > 10)
    & (df_wim['MRG. LÍQ. [%]'] > 10)
    & (df_wim['ROIC [%]'] > 10)
    & (df_wim['ROE [%]'] > 10)
    & (df_wim['LIQ.2MESES'] > 10e6)
    & (df_wim['DÍV.LÍQ/ PATRIM.'] < 2)
    & (df_wim['CRESC. REC.5A [%]'] > 10)
    & (df_wim['DÍVIDA LÍQUIDA/EBITDA'] < 2)
]

df_wim = (
    df_wim.sort_values(
        ['SETOR_SUBSETOR_SEGMENTO', 'RECEITA_PROXY', 'ROIC [%]'],
        ascending=[True, False, False]
    )
    .drop_duplicates(subset='SETOR_SUBSETOR_SEGMENTO', keep='first')
    .reset_index(drop=True)
    .sort_values('MARKET_SHARE_RECEITA_%', ascending=False)
)

df_wim = df_wim.sort_values(by='EV/EBIT', ascending=True)

df_wim = df_wim.drop(columns=[
    'SETOR_SUBSETOR_SEGMENTO', 'RECEITA_PROXY', 'MARKET_SHARE_RECEITA_%'
    ])

pprint(df_wim)

# ---------------------------------------------------------------------------

xlsx_path = os.path.join(os.path.dirname(__file__), "data.xlsx")
df.to_excel(xlsx_path, index=True)

