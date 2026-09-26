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

from typing import Optional
from pprint import pprint
from collections import defaultdict
from tqdm import tqdm

import os
import re
import time
import warnings
import re

import pandas as pd
import numpy as np

# Suprimir warnings específicos
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ----------------------------------------------------------------

trading_view_url = "https://br.tradingview.com/markets/stocks-brazil/market-movers-all-stocks/"

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

# ----------------------------------------------------------------


class Scrap:

    def __init__(self):
        self.service = Service(os.path.join(_this_path, "msedgedriver.exe"), 
                               log_path=os.devnull)
        self.driver = webdriver.Edge(service=self.service, 
                                     options=edge_options)
        self.wait = WebDriverWait(self.driver, 15)

        self.ticker_links = self.get_ticker_links()

        self.data = self.get_data()


    def click(self, xpath: str, return_elem: bool = False) -> Optional[bool]:
        """Clicks in elements which xpath is given"""
        try:
            element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            try: 
                element.click()
            except:
                self.driver.execute_script("arguments[0].click();", element)
            time.sleep(2)
            if return_elem:
                return element
        except Exception as e:
            print(f"Error clicking element with XPath {xpath}: \n{e}")


    def get_ticker_links(self) -> list:
        """Get ticker links from Trading View"""
        try:
            self.driver.get(trading_view_url)

            self.click(xpath='/html/body/div[3]/main/div/div[2]/div/div[4]/div/div[3]/button/span')
            self.click(xpath='/html/body/div[3]/main/div/div[2]/div/div[4]/div/div[3]/button/span')

            table = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, 
                 '/html/body/div[3]/main/div/div[2]/div/div[4]/div/div[2]/div[2]/div/div/div/table/tbody')))
            lines = table.find_elements(By.TAG_NAME, 'tr')

            ticker_links = defaultdict()

            for line in lines:
                ticker = line.find_element(By.TAG_NAME, 'a')
                ticker_links[ticker.text] = ticker.get_attribute('href')

            return ticker_links

        except:
            pass


    def clean_data(self, data: dict) -> dict:
        """Remove unicode charsets from Trading View data"""
        pattern = r'[\u2000-\u206F\u202A-\u202E\u2066-\u2069]'
        suffix_multiplier = {'B': 1e9, 'M': 1e6, 'K': 1e3}
        empty_markers = {'—', '——————', 'вҖ”', ''}

        cleaned = {}
        for key, value_list in data.items():
            clean_list = []
            for item in value_list:
                clean_text = re.sub(pattern, '', item).strip()

                if clean_text in empty_markers or set(clean_text) == {'—'}:
                    clean_list.append('')
                    continue

                suffix = ''
                for s in ('B', 'M', 'K'):
                    if clean_text.endswith(s):
                        suffix = s
                        break

                number_part = clean_text[:-len(suffix)].strip() if suffix else clean_text
                number_part = number_part.replace(',', '.').replace('−', '-').strip()

                if not number_part:
                    clean_list.append('')
                    continue

                value = float(number_part)
                if suffix:
                    value *= suffix_multiplier[suffix]
                clean_list.append(value)

            cleaned[key] = clean_list
        return cleaned


    def clean_labels(self, text: str) -> list:
        """Get labels of each data from Trading View"""
        lines = text.split('\n')
        labels = list()
        
        for line in lines:
            clean_line = re.sub(r'[\u2000-\u206F\u202A-\u202E\u2066-\u2069]', '', line)
            clean_line = clean_line.replace('\u202f', ' ')
            clean_line = clean_line.strip()
            
            if not clean_line:
                continue
            
            normalized_line = clean_line.replace('−', '-')
            
            has_numeric_data = bool(re.search(r'[\d,]+[BMK%]', normalized_line)) or \
                            bool(re.match(r'^[+-]?\d+[,.]\d+%?$', normalized_line))
            
            is_separator = clean_line in ['—', '‚Äî', '>']
            
            is_numeric = bool(re.match(r'^[+-]?\d+[,.]\d+%?$', normalized_line))
            
            if not has_numeric_data and not is_separator and not is_numeric and len(clean_line) > 1:
                labels.append(clean_line)
        
        return labels


    def get_data_from_table(self, xpath) -> dict:
        """
        """
        table_data = defaultdict()
        table = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

        labels = self.clean_labels(table.text)

        labels_to_delete = ['Principais estatísticas', 'Razão Valuation', 
                            'Índice de Rentabilidade', 'Índice de Liquidez', 
                            'Índice de Solvência', 'Métricas por ação']

        lines = table.find_elements(By.XPATH, ".//div[starts-with(@class, 'value')]")
        
        for label in labels:
            if label in labels_to_delete:
                labels.remove(label)

        for l in range(1, len(labels)):
            if labels[l] == labels[l - 1]:
                labels[l - 1] += " (1)"
                labels[l] += " (2)"

        data_packs = list()
        k = 0

        count = [len(self.driver.execute_script("return arguments[0].textContent;", line)) 
                 for line in lines[:7]]

        k_lim = 7 if count[0] >= sum(count[1:]) else 6
        
        for line in lines:

            label = labels[len(table_data)]

            text = self.driver.execute_script("return arguments[0].textContent;", line)

            if text and k != 0:
                data_packs.append(text)

            k += 1

            if k == k_lim:
                k = 0
                table_data[label] = data_packs.copy()
                data_packs.clear()

        return self.clean_data(table_data)
    

    def get_data(self) -> pd.DataFrame:
        """Get data from each ticker"""

        main_window = self.driver.current_window_handle

        data = defaultdict()

        for name, link in tqdm(self.ticker_links.items(), desc="Processing..."):
            try:
                data[name] = defaultdict()
                self.driver.execute_script("window.open(arguments[0]);", link)
                
                all_windows = self.driver.window_handles
                self.driver.switch_to.window(all_windows[-1])

                # finanças
                self.click(xpath='/html/body/div[3]/main/div[2]/div[1]/div/div[2]/div/a[2]')

                # --------------------------
                # DEMONSTRATIVOS FINANCEIROS
                # --------------------------

                # DECLARAÇÃO DE RENDA
                self.click('/html/body/div[3]/main/div[2]/div[2]/div/div/div[1]/div[2]/div/div/a[2]')
                data[name].update(self.get_data_from_table('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

                # BALANÇO PATRIMONIAL
                self.click('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[1]/div/div/a[2]/span')
                data[name].update(self.get_data_from_table('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

                # FLUXO DE CAIXA
                self.click('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[1]/div/div/a[3]/span')
                data[name].update(self.get_data_from_table('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

                # ------------
                # ESTATÍTSTICA
                # ------------

                self.click('/html/body/div[3]/main/div[2]/div[2]/div/div/div[1]/div[2]/div/div/a[3]')
                data[name].update(self.get_data_from_table('/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[3]/div[2]/div[2]/div/div[1]'))

            except:
                if name in data.keys():
                    del data[name]
                pass

            self.driver.close()
            self.driver.switch_to.window(main_window)

        self.data = data


result = Scrap()


def ensure_none(v):
    """Turns '' into None, and keep values"""
    if v is None or v == '':
        return None
    return v


with pd.ExcelWriter("data_per_ticker.xlsx", engine="xlsxwriter") as writer:
    for ticker, data in result.data.items():
        if not hasattr(data, "items"):
            continue

        series = {}
        for d, values in data.items():
            if not isinstance(values, (list, tuple)):
                values = [values]
            valores_limpos = [ensure_none(v) for v in values]
            series[d] = pd.Series(valores_limpos)

        df_t = pd.DataFrame(series).T
        df_t.columns = [f"Período_{i+1}" for i in range(df_t.shape[1])]
        df_t.to_excel(writer, sheet_name=ticker)

print("STOP")

