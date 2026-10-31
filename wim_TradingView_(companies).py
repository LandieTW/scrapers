# Método Wanderley de Investimentos (MWI) — versão paralela

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from threading import Lock
from tqdm import tqdm

import time
import os
import re
import warnings
import traceback
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ----------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------

trading_view_url = "https://br.tradingview.com/markets/stocks-brazil/market-movers-all-stocks/"

_this_path = os.path.dirname(os.path.abspath(__file__))
xlsx_path = os.path.join(_this_path, "data_per_ticker.xlsx")


DEFAULT_WORKERS = int(os.environ.get("MWI_WORKERS", "10"))

DEFAULT_TIMEOUT = int(os.environ.get("MWI_TIMEOUT", "15"))

EDGE_DRIVER_PATH = os.path.join(_this_path, "msedgedriver.exe")

UNICODE_PATTERN = r'[\u2000-\u206F\u202A-\u202E\u2066-\u2069]'
SUFFIX_MULT = {'B': 1e9, 'M': 1e6, 'K': 1e3}
EMPTY_MARKERS = {'—', '——————', 'вҖ”', '', '‚Äî'}


def _build_edge_options() -> Options:
    """
    Edge builder
     - Browser execution without graph interface
     - Presents only critical issues
     - Optimized to deal with shared low memmory (containers/Docker)
    """
    opts = Options()
    
    opts.add_argument("--headless")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-logging")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    
    return opts


def clean_data(data: dict) -> dict:
    """
    Clean list of numerical values
    - Translate from unicode pattern to float values
    """
    cleaned = dict()
    for key, value_list in data.items():
        clean_list = list()
        for item in value_list:
            if item is None:
                clean_list.append('')
                continue
            clean_text = re.sub(UNICODE_PATTERN, '', str(item)).strip()

            if clean_text in EMPTY_MARKERS or (clean_text and set(clean_text) == {'—'}):
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

            try:
                value = float(number_part)
            except ValueError:
                clean_list.append('')
                continue

            if suffix:
                value *= SUFFIX_MULT[suffix]
            clean_list.append(value)

        cleaned[key] = clean_list
    return cleaned


def clean_labels(text: str) -> list:
    """
    Clean compiled single text with labels
    and delivery a list with separated labels
    """
    labels = list()
    for line in text.split('\n'):
        clean_line = re.sub(UNICODE_PATTERN, '', line).replace('\u202f', ' ').strip()
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


class DriverSession:
    """
    Encapsulates Edge builder call and quit, 
    click and table reader functions
    - Used to make it possible a single instance per thread
    """


    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.service = Service(EDGE_DRIVER_PATH, log_path=os.devnull)
        self.driver = webdriver.Edge(service=self.service, options=_build_edge_options())
        self.wait = WebDriverWait(self.driver, timeout)
        self.timeout = timeout


    def click(self, xpath: str, return_elem: bool = False, name: str = None) -> Optional[bool]:
        """
        Click function
        """
        try:
            element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            try:
                element.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", element)
            time.sleep(2)
            if return_elem:
                return element
            return True
        except Exception as e:
            print(f"\n[click] failed ({name}) — {type(e).__name__}: {e}")
            return None


    def quit(self) -> None:
        """
        Edge quit
        """
        try:
            self.driver.quit()
        except Exception:
            pass


    def get_data_from_table(self, xpath) -> dict:
        """
        Function to extract data from tables in trading view website
        """
        table = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

        labels = clean_labels(table.text)

        labels_to_delete = ['Principais estatísticas', 'Razão Valuation',
                            'Índice de Rentabilidade', 'Índice de Liquidez',
                            'Índice de Solvência', 'Métricas por ação']
        labels = [l for l in labels if l not in labels_to_delete]

        for l in range(1, len(labels)):
            if labels[l] == labels[l - 1]:
                labels[l - 1] += " (1)"
                labels[l] += " (2)"

        lines = table.find_elements(By.XPATH, ".//div[starts-with(@class, 'value')]")

        head_texts = [self.driver.execute_script("return arguments[0].textContent;", line)
                      for line in lines[:7]]
        head_lens = [len(t) if t else 0 for t in head_texts]
        if not head_lens:
            return {}

        k_lim = 7 if head_lens[0] >= sum(head_lens[1:]) else 6

        table_data = {}
        data_packs = []
        k = 0

        for line in lines:
            text = self.driver.execute_script("return arguments[0].textContent;", line)

            if text is not None and k != 0:
                data_packs.append(text)

            k += 1
            if k == k_lim:
                if len(table_data) < len(labels):
                    label = labels[len(table_data)]
                    table_data[label] = data_packs.copy()
                else:
                    table_data[f"__extra_{len(table_data)}"] = data_packs.copy()
                data_packs.clear()
                k = 0

        return clean_data(table_data)


def get_ticker_links(session: DriverSession) -> dict:
    """
    Collects links for each ticker
    """
    session.driver.get(trading_view_url)

    session.click(xpath='/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[3]/button/span', name='expand_1')
    session.click(xpath='/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[3]/button/span', name='expand_2')

    table = session.wait.until(EC.presence_of_element_located(
        (By.XPATH,
         '/html/body/div[3]/main/div/div[2]/div[4]/div[1]/div[2]/div[2]/div/div/div/table/tbody')))
    lines = table.find_elements(By.TAG_NAME, 'tr')

    ticker_links = dict()
    for line in lines:
        try:
            ticker = line.find_element(By.TAG_NAME, 'a')
            ticker_links[ticker.text] = ticker.get_attribute('href')
        except Exception:
            continue

    return ticker_links


def scrape_ticker(name: str, link: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Load ticker link and gets data from tables
    """
    
    session = DriverSession(timeout=timeout)
    payload: dict = {}
    try:
        session.driver.get(link)

        # finanças
        session.click(xpath='/html/body/div[3]/main/div[2]/div[1]/div/div[2]/div/a[2]',
                      name=f"{name}·financas")

        # DRE
        session.click(xpath='/html/body/div[3]/main/div[2]/div[2]/div/div/div[1]/div[2]/div/div/a[2]',
                      name=f"{name}·dre")
        payload.update(session.get_data_from_table(
            '/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

        # Balanço
        session.click(xpath='/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[1]/div/div/a[2]/span',
                      name=f"{name}·balanco")
        payload.update(session.get_data_from_table(
            '/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

        # Fluxo de caixa
        session.click(xpath='/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[1]/div/div/a[3]/span',
                      name=f"{name}·fluxo")
        payload.update(session.get_data_from_table(
            '/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[3]/div[2]/div[2]/div/div[1]'))

        # Estatística
        session.click(xpath='/html/body/div[3]/main/div[2]/div[2]/div/div/div[1]/div[2]/div/div/a[3]',
                      name=f"{name}·estatistica")
        payload.update(session.get_data_from_table(
            '/html/body/div[3]/main/div[2]/div[2]/div/div/div[3]/div[2]/div[3]/div[2]/div[2]/div/div[1]'))

    finally:
        session.quit()

    return payload


def run_parallel(ticker_links: dict, workers: int, timeout: int) -> dict:
    """
    Triggers workers in parallel, then accumulate results thread-safe
    """
    data: dict = {}
    errors: dict = {}
    lock = Lock()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(scrape_ticker, name, link, timeout): name
            for name, link in ticker_links.items()
        }

        with tqdm(total=len(futures), desc=f"Processing ({workers} workers)") as pbar:
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    payload = fut.result()
                    if payload:
                        with lock:
                            data[name] = payload
                    else:
                        with lock:
                            errors[name] = "empty payload"
                except Exception as exc:
                    with lock:
                        errors[name] = f"{type(exc).__name__}: {exc}"
                    print(f"\n[worker] fail at {name}:")
                    traceback.print_exc()
                finally:
                    pbar.update(1)

    if errors:
        print(f"\n{len(errors)} failed tickers:")
        for t, msg in errors.items():
            print(f"   - {t}: {msg}")

    return data


def ensure_none(v):
    """
    Ensure empty value is None formating
    """
    if v is None or v == '':
        return None
    return v


def sanitize_sheet_name(name: str) -> str:
    """
    Generates sheet name according to ticker name
    """
    name = re.sub(r'[:\\/?*\[\]]', '_', str(name))
    return name[:31] or "sheet"


def export_to_excel(data: dict, path: str) -> None:
    """
    Generates xlsx file compilating results organized by sheets
    """
    if not data:
        print("Empty data — any sheet will be generated.")
        return

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        written = 0
        for ticker, payload in data.items():
            if not payload:
                print(f"{ticker}: without data, skipping.")
                continue

            series = {}
            for label, values in payload.items():
                if not isinstance(values, (list, tuple)):
                    values = [values]
                clean_values = [ensure_none(v) for v in values]
                series[label] = pd.Series(clean_values)

            df_t = pd.DataFrame(series).T
            df_t.columns = [f"Period_{i+1}" for i in range(df_t.shape[1])]

            df_t.to_excel(writer, sheet_name=sanitize_sheet_name(ticker))
            written += 1

    print(f"{written} sheets written in {path}")


def main(workers: int = DEFAULT_WORKERS, timeout: int = DEFAULT_TIMEOUT) -> None:
    print(f"Configuration: workers={workers}, timeout={timeout}s")

    bootstrap = DriverSession(timeout=timeout)
    try:
        ticker_links = get_ticker_links(bootstrap)
    finally:
        bootstrap.quit()

    if not ticker_links:
        raise RuntimeError("Any ticker was found — aborting.")

    print(f"{len(ticker_links)} tickers found.")

    if workers <= 1:
        print("Sequential mode (workers=1).")
        data = {}
        for name, link in tqdm(ticker_links.items(), desc="Processing"):
            try:
                payload = scrape_ticker(name, link, timeout)
                if payload:
                    data[name] = payload
            except Exception:
                print(f"\n[main] fails at {name}:")
                traceback.print_exc()
    else:
        data = run_parallel(ticker_links, workers, timeout)

    export_to_excel(data, xlsx_path)


if __name__ == "__main__":
    main()

