'''
This script makes the download from eesc.usp thesis repository
of every thesis.pdf associated with Numerical Analysis

Download: Microsoft Edge WebDriver
'''

import os
import time
import warnings

from bs4 import BeautifulSoup
import requests

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


theme = 0

theme_options = [
    "Todas as áreas de pesquisa",
    "Área indefinida",
    "Estruturas de Concreto e Alvenaria",
    "Estruturas de Madeira",
    "Estruturas Metálicas",
    "Materiais e Mecânica dos Materiais",
    "Mecânica das Estruturas",
    "Métodos Numéricos"
    ]


url = "https://producaocientifica.eesc.usp.br/set"

_this_path = os.path.dirname(__file__)

service = Service(
    os.path.join(_this_path, "msedgedriver.exe"),
    log_path=os.devnull
)

edge_options = Options()
edge_options.add_argument("--headless")
edge_options.add_argument("--start-maximized")
edge_options.add_argument("--log-level=3")
edge_options.add_argument("--disable-logging")
edge_options.add_argument("--disable-dev-shm-usage")
edge_options.add_argument("--no-sandbox")
edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])

driver = webdriver.Edge(service=service, options=edge_options)
driver.get(url)
wait = WebDriverWait(driver, 15)

select_element = wait.until(EC.presence_of_element_located((By.NAME, "area")))
select = Select(select_element)
select.select_by_visible_text(theme_options[theme])
time.sleep(2)

link_names = list()
link_thesis = list()
n_i, n = 0, 1
while n_i < n:
    try:
        soup = BeautifulSoup(driver.page_source, "html5lib")
        
        count = soup('div', 'navbar-brand text-info')[0].text
        n_i = int(count.split()[-3])
        n = int(count.split()[-1])
        
        good_links = [a['href'] 
                      for a in soup('a')
                      if a.has_attr('href') and "producaocientifica.eesc.usp.br/set/" in a['href']]
        
        for a in good_links:
            download_page = requests.get(a).text
            soup_a = BeautifulSoup(download_page, "html5lib")

            pdf_title = soup_a.get_text(strip=True).split("\n,")[1].strip().split("/")[0]
            pdf_link = soup_a.find("a", class_="btn-outline-primary")

            link_names.append(pdf_title)
            link_thesis.append(pdf_link["href"])
        
        select_next = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/nav[1]/ul/li[3]/a')))
        select_next.click()
        time.sleep(2)

    except:
        break

dst_path = os.path.join(_this_path, f"usp_{theme_options[theme]}")
os.makedirs(dst_path, exist_ok=True)

for name, link in zip(link_names, link_thesis):
    try:
        response = requests.get(link)
        file_path = os.path.join(dst_path, f"{name}.pdf")
        with open(file_path, "wb") as f:
            f.write(response.content)

    except Exception as e:
        print(f"Error in {link} - {e}")

