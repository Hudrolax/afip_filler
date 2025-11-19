# afip.py
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from time import sleep
from typing import List, Optional, Union

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

load_dotenv()


# ---------- helpers ----------

def _get_elements(
    driver: webdriver.Chrome, selector: str, return_first: bool = True
) -> Union[WebElement, List[WebElement]]:
    """Мягкий поллинг элементов по XPATH."""
    for _ in range(100):
        print(f"find element {selector}")
        elements = driver.find_elements(By.XPATH, selector)
        if elements:
            sleep(0.2)
            return elements[0] if return_first else elements
        sleep(0.1)
    raise RuntimeError(f"Element by selector {selector} not found.")


def get_element(driver: webdriver.Chrome, selector: str) -> WebElement:
    res = _get_elements(driver, selector, True)
    if isinstance(res, list):
        raise RuntimeError("get_element(): internal type mismatch")
    return res


def get_elements(driver: webdriver.Chrome, selector: str) -> List[WebElement]:
    # Важно: возвращаем список (раньше тут было True).
    res = _get_elements(driver, selector, False)
    if isinstance(res, WebElement):
        raise RuntimeError("get_elements(): internal type mismatch")
    return res


def _maybe_unquarantine_driver(driver: webdriver.Chrome) -> None:
    """
    Если Selenium Manager скачал chromedriver в локальный кэш,
    на macOS иногда помогает снять карантин/выдать +x.
    Никаких ручных действий не требуется; ошибки глушим.
    """
    try:
        caps = driver.capabilities or {}
        service_bin: Optional[str] = None

        # Разные поля могут встречаться в зависимости от версии selenium/chrome:
        # 'chrome' или 'goog:chromeOptions' -> 'debuggerAddress' и т.п.
        # К пути к драйверу можно добраться из 'chrome'->'chromedriverVersion'
        # но прямого пути нет. Тогда спросим у DevTools:
        # fallback: ничего не делаем, если путь не найти.
        # Оставим «пустышку» — чтобы не падать.
        _ = caps  # просто чтобы линтер не ругался

        # Селениум напрямую не отдает путь драйвера в capabilities,
        # поэтому попробуем косвенно:
        # 1) спросить переменную окружения, которую иногда ставит selenium
        for env_key in ("SELENIUM_MANAGER_CACHE_PATH", ):
            if os.environ.get(env_key):
                # в кэше хранится структура .../chrome/<version>/<platform>/chromedriver
                # рисковать рекурсивным обходом не будем — пропускаем.
                pass

        # если удалось выяснить конкретный путь (у нас нет универсального способа),
        # можно было бы:
        # os.chmod(service_bin, os.stat(service_bin).st_mode | 0o111)
        # и снять xattr. Но без надежного пути — ничего не делаем.
        if service_bin and platform.system() == "Darwin":
            try:
                os.chmod(service_bin, os.stat(service_bin).st_mode | 0o111)
            except Exception:
                pass
            if shutil.which("xattr"):
                try:
                    subprocess.run(
                        ["xattr", "-dr", "com.apple.quarantine", service_bin],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
    except Exception:
        # абсолютно всё глушим — это вспомогательная оптимизация
        pass


# ---------- main class ----------

class AFIP:
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self.home_container = None

        current_dir = os.getcwd()
        target_url = "https://afip.gob.ar/"
        with open("blank.html", "w") as f:
            f.write(f'<a href="{target_url}" target="_blank">link</a>')

        options = webdriver.ChromeOptions()
        options.add_argument("start-maximized")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--force-device-scale-factor=1")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")

        # НЕ указываем никакие пути — Selenium Manager сам подберёт драйвер.
        try:
            self.driver = webdriver.Chrome(options=options)
        except WebDriverException as e:
            raise RuntimeError(
                "Не удалось запустить Chrome через Selenium Manager. "
                "Убедись, что установлен Google Chrome и библиотека selenium>=4.25.0.\n"
                f"Оригинальная ошибка: {e}"
            )

        # (опционально) попробуем снять карантин, если это актуально
        _maybe_unquarantine_driver(self.driver)

        # Навигация
        self.driver.get(f"file://{current_dir}/blank.html")
        links = self.driver.find_elements(By.XPATH, "//a[@href]")
        sleep(0.5)
        links[0].click()
        sleep(0.5)
        self.driver.switch_to.window(self.driver.window_handles[-1])

        sleep(2)
        self.login()

        sleep(1)
        self.go_to_linea()

        sleep(0.5)

        if not self.driver:
            raise RuntimeError("Driver not initialized")

    # ---------- actions ----------

    def login(self):
        print("start login")
        login_btn = get_element(
            self.driver,
            '//a[@href="https://auth.afip.gob.ar/contribuyente_/login.xhtml?action=SYSTEM&system=participacion_ciudadana"]',
        )
        login_btn.click()
        self.driver.switch_to.window(self.driver.window_handles[-1])

        print("find username field")
        login_field = get_element(self.driver, '//input[@id="F1:username"]')
        login_field.send_keys(os.getenv("CUIT", ""))
        sleep(1)

        submit_btn = get_element(self.driver, '//input[@id="F1:btnSiguiente"]')
        submit_btn.click()
        sleep(1)

        print("find password field")
        pass_field = get_element(self.driver, '//input[@id="F1:password"]')
        pass_field.send_keys(os.getenv("PASS", ""))
        sleep(1)

        submit_btn = get_element(self.driver, '//input[@id="F1:btnIngresar"]')
        submit_btn.click()
        sleep(10)

    def waiting_for_modal(self):
        try:
            modal_content = WebDriverWait(self.driver, 2).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "modal-content"))
            )
            close_button = modal_content.find_element(By.ID, "novolveramostrar")
            close_button.click()
            print("Модальное окно закрыто.")
        except TimeoutException:
            print("Модальное окно не найдено за 3 секунды.")

    def go_to_linea(self):
        linea_btn = get_element(
            self.driver, '//a[.//div[.//h3[text()="Comprobantes en línea"]]]'
        )
        linea_btn.click()
        sleep(1)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        sergei_btn = get_element(self.driver, '//input[@value="NAZAROV SERGEI"]')
        sergei_btn.click()
        self.waiting_for_modal()

    def make_invoice(self, date: str, price: int | str):
        def click_continuar():
            continuar_btn = get_element(self.driver, '//input[@value="Continuar >"]')
            continuar_btn.click()

        generar_btn = get_element(self.driver, '//a[@id="btn_gen_cmp"]')
        generar_btn.click()

        self.waiting_for_modal()

        punto_de_ventas = get_element(self.driver, '//select[@name="puntoDeVenta"]')
        select = Select(punto_de_ventas)
        select.select_by_index(1)
        sleep(1.5)

        click_continuar()

        # filling dates page
        date1 = get_element(self.driver, '//input[@id="fc"]')
        date1.clear()
        date1.send_keys(date)

        conceptos = get_element(self.driver, '//select[@id="idconcepto"]')
        select = Select(conceptos)
        select.select_by_index(2)

        date2 = get_element(self.driver, '//input[@id="fsd"]')
        date2.clear()
        date2.send_keys(date)

        date3 = get_element(self.driver, '//input[@id="fsh"]')
        date3.clear()
        date3.send_keys(date)

        date4 = get_element(self.driver, '//input[@id="vencimientopago"]')
        date4.clear()
        date4.send_keys(date)

        click_continuar()

        # filling servicios page

        # Consumidor final
        cons_fin = get_element(self.driver, '//select[@id="idivareceptor"]')
        select = Select(cons_fin)
        select.select_by_index(3)

        # Otra checkbox
        otra_chb = get_element(self.driver, '//input[@id="formadepago7"]')
        otra_chb.click()

        click_continuar()

        # filling table page
        producto_text = get_element(self.driver, '//textarea[@id="detalle_descripcion1"]')
        producto_text.clear()
        producto_text.send_keys("Servicios prestados")

        # unidades
        unidades = get_element(self.driver, '//select[@id="detalle_medida1"]')
        select = Select(unidades)
        select.select_by_index(7)

        # precio
        precio = get_element(self.driver, '//input[@id="detalle_precio1"]')
        precio.clear()
        precio.send_keys(str(price))

        click_continuar()

        # final page
        confirmar_datos = get_element(self.driver, '//input[@value="Confirmar Datos..."]')
        confirmar_datos.click()

        # подтверждение
        wait = WebDriverWait(self.driver, 10)
        confirmar_modal_btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//button[contains(@class,"ui-button") and .//span[text()="Confirmar"]]',
                )
            )
        )
        confirmar_modal_btn.click()
        self.driver.switch_to.default_content()

        menu_principal = get_element(self.driver, '//input[@value="Menú Principal"]')
        menu_principal.click()
        sleep(0.5)

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()


# ---------- simple JSON helpers ----------

def save_data_to_file(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file)


def read_data_from_file(file_path):
    with open(file_path, "r") as file:
        return json.load(file)
