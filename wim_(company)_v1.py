# Método Wanderley de Investimentos (MWI)

"""
This is an auto-searching script for evaluating stock investiments in Brazilian companies
on the stock market, using data from the Status Invest website and referencing.
"""

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import os
import numpy as np
import pandas as pd
import numpy as np
import time
import warnings

# Suprimir warnings específicos
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ----------------------------------------------------------------

fundamentus_url = "https://www.fundamentus.com.br/"

# ----------------------------------------------------------------

def click(driver, xpath, wait_time=10):
    try:
        wait = WebDriverWait(driver, wait_time)
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        element.click()
        return element
    except Exception as e:
        print(f"Error clicking element with XPath {xpath}: {e}")

# ----------------------------------------------------------------

_this_path = os.path.dirname(os.path.abspath(__file__))

edge_options = Options()
edge_options.add_argument("--headless")
edge_options.add_argument("--start-maximized")
edge_options.add_argument("--log-level=3")
edge_options.add_argument("--disable-logging")
edge_options.add_argument("--disable-dev-shm-usage")
edge_options.add_argument("--no-sandbox")
edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])

service = Service(
    os.path.join(_this_path, "msedgedriver.exe"),
    log_path=os.devnull
)

try:

    driver = webdriver.Edge(service=service, options=edge_options)
    
    driver.get(fundamentus_url)
    wait = WebDriverWait(driver, 15)

    click(driver, "/html/body/div[1]/div[1]/div[1]/span/a[1]")
    time.sleep(2)
    
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(2)
    
    click(driver, '/html/body/div[1]/div[2]/form/input')
    time.sleep(2)
    
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(2)

    headers = driver.find_elements(By.XPATH, "/html/body/div[1]/div[2]/table/thead/tr/th")
    headers_columns = [h.text for h in headers]

    tbody = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/table/tbody")))
    data = [info.text.split(" ") for info in tbody.find_elements(By.TAG_NAME, "tr")]
    
    df = pd.DataFrame(data, columns=headers_columns)

    df = df.drop(columns=["PSR", "Div.Yield", "P/Ativo", "P/Cap.Giro", "P/EBIT", "P/Ativ Circ.Liq", "Liq. Corr.", "EV/EBIT", "EV/EBITDA", "Patrim. Líq"])
    
    for c in ["Cotação", "P/L", "P/VP", "Mrg Bruta", "Mrg Ebit", "Mrg. Líq.", "ROIC", "ROE", "Liq.2meses", "Dív.Líq/ Patrim.", "Cresc. Rec.5a"]:
        df[c] = (df[c].str.replace("%", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).str.replace(r"^-$", "0", regex=True).astype(float))

    df["LPA"] = np.where(df["P/L"] != 0, df["Cotação"] / df["P/L"], 0)
    df["VPA"] = np.where(df["P/VP"] != 0, df["Cotação"] / df["P/VP"], 0)

    df = df.drop(columns=["P/L", "P/VP"])
    
    df["Graham"] = np.sqrt(22.5 * df["LPA"] * df["VPA"])

    df = df[
        (df["Mrg Bruta"] > 10)
        & (df["Mrg Ebit"] > 10)
        & (df["Mrg. Líq."] > 10)
        & (df["ROIC"] > 10)
        & (df["ROE"] > 10)
        & (df["Cresc. Rec.5a"] > 10)
        & (df["Liq.2meses"]/2 > 1e6)
        & (df["Dív.Líq/ Patrim."] < 1)
        & (df["Graham"] > df["Cotação"] * 1.1)
        ]
    
    df = df.reset_index(drop=True)

    from pprint import pprint
    pprint(df)
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if 'driver' in locals():
        driver.quit()

