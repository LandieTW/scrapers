#!/usr/bin/env python3

"""
This is an auto-searching script for evaluating stock investiments in Brazilian companies
on the stock market, using data from Fundamentus website and referencing.
"""

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional
from pprint import pprint
import os
import numpy as np
import pandas as pd
import numpy as np
import time
import warnings

# ignoring warning outuputs
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ----------------------------------------------------------------

fundamentus_url = "https://www.fundamentus.com.br/resultado.php"

# ----------------------------------------------------------------

def click(driver, xpath: str, wait_time=10) -> Optional[bool]:
    """Clicks in elements which xpath is given"""
    wait = WebDriverWait(driver, wait_time)
    try:
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        try: 
            element.click()
        except:
            driver.execute_script("arguments[0].click();", element)
        time.sleep(2)
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

edge_options = Options()
edge_options.add_argument("--headless")
edge_options.add_argument("--start-maximized")
edge_options.add_argument("--log-level=3")
edge_options.add_argument("--disable-logging")
edge_options.add_argument("--disable-dev-shm-usage")
edge_options.add_argument("--no-sandbox")
edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])

service = Service(os.path.join(_this_path, "msedgedriver.exe"), log_path=os.devnull)

try:
    driver = webdriver.Edge(service=service, options=edge_options)
    
    driver.get(fundamentus_url)
    wait = WebDriverWait(driver, 15)

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

    tbody = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/div[2]/table/tbody")))
    rows = tbody.find_elements(By.TAG_NAME, "tr")

    index, lines = [], []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        values = [parse_cell(cell.text) for cell in cells]
        index.append(values[0])
        lines.append(values[1:])

    df = pd.DataFrame(lines, columns=header, index=index)

    for col in ["COTAÇÃO", "P/L", "P/VP"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["LPA"] = np.where(df["P/L"] != 0, df["COTAÇÃO"] / df["P/L"], 0)
    df["VPA"] = np.where(df["P/VP"] != 0, df["COTAÇÃO"] / df["P/VP"], 0)
    
    produto = 22.5 * df["LPA"] * df["VPA"]
    df["GRAHAM"] = np.sqrt(np.where(produto > 0, produto, np.nan))

    df = df.reset_index(drop=True)

    xlsx_path = os.path.join(os.path.dirname(__file__), "data.xlsx")
    df.to_excel(xlsx_path, index=True)
    pprint(df)
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if 'driver' in locals():
        driver.quit()

