from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import os
from time import sleep
import platform
import json

from dotenv import load_dotenv
load_dotenv()


def _get_elements(
    driver: webdriver.Chrome, selector: str, return_first: bool = True
) -> WebElement | list[WebElement]:
    for _ in range(100):
        print(f"find element {selector}")
        elements = driver.find_elements(By.XPATH, selector)
        if elements:
            sleep(0.2)
            return elements[0] if return_first else elements
        else:
            sleep(0.1)
    raise Exception(f"Element by selector {selector} not found.")


def get_element(driver: webdriver.Chrome, selector: str) -> WebElement:
    res = _get_elements(driver, selector, True)
    if isinstance(res, list):
        raise
    return res


def get_elements(driver: webdriver.Chrome, selector: str) -> list[WebElement]:
    res = _get_elements(driver, selector, True)
    if isinstance(res, WebElement):
        raise
    return res


class AFIP:
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self.home_container = None

        self.home_container = None

        current_dir = os.getcwd()
        target_url = "https://afip.gob.ar/"
        with open("blank.html", "w") as f:
            f.write(f'<a href="{target_url}" target="_blank">link</a>')

        option = webdriver.ChromeOptions()
        option.add_argument("start-maximized")

        # Определяем архитектуру системы
        architecture = platform.machine()
        driver_path = ChromeDriverManager().install()

        # Установка драйвера, учитывая архитектуру
        if architecture == "arm64":
            driver_path = driver_path.replace(
                "chromedriver_mac64", "chromedriver_mac_arm64"
            )

        service = Service(driver_path)
        self.driver = webdriver.Chrome(service=service, options=option)

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
            raise Exception("Driver not initialized")

    def login(self):
        print("start login")
        login_btn = get_element(
            self.driver,
            '//a[@href="https://auth.afip.gob.ar/contribuyente_/login.xhtml"]',
        )
        login_btn.click()
        self.driver.switch_to.window(self.driver.window_handles[-1])

        print("find username field")
        login_field = get_element(self.driver, '//input[@id="F1:username"]')
        login_field.send_keys(os.getenv("CUIT", ""))

        submit_btn = get_element(self.driver, '//input[@id="F1:btnSiguiente"]')
        submit_btn.click()

        print("find password field")
        pass_field = get_element(self.driver, '//input[@id="F1:password"]')
        pass_field.send_keys(os.getenv("PASS", ""))

        submit_btn = get_element(self.driver, '//input[@id="F1:btnIngresar"]')
        submit_btn.click()

    def waiting_for_modal(self):
        try:
            # Ожидание, пока элемент с классом "modal-content" не станет видимым в течение 3 секунд
            modal_content = WebDriverWait(self.driver, 2).until(
                EC.visibility_of_element_located(
                    (By.CLASS_NAME, "modal-content")
                )
            )

            # Если элемент найден, нахождение и нажатие кнопки закрытия модального окна по её идентификатору "novolveramostrar"
            close_button = modal_content.find_element(By.ID, "novolveramostrar")
            close_button.click()
            print("Модальное окно закрыто.")
        except TimeoutException:
            # Если элемент не найден за 3 секунды, ничего не делать
            print("Модальное окно не найдено за 3 секунды.")

    def go_to_linea(self):

        linea_btn = get_element(
            self.driver, '//a[.//div[.//h3[text()="Comprobantes en línea"]]]'
        )
        linea_btn.click()
        sleep(1)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        sergei_btn = get_element(
            self.driver, '//input[@value="NAZAROV SERGEI"]'
        )
        sergei_btn.click()
        self.waiting_for_modal()

    def make_invoice(self, date: str, price: int | str):
        def click_continuar():
            continuar_btn = get_element(
                self.driver, '//input[@value="Continuar >"]'
            )
            continuar_btn.click()

        generar_btn = get_element(self.driver, '//a[@id="btn_gen_cmp"]')
        generar_btn.click()

        self.waiting_for_modal()

        punto_de_ventas = get_element(
            self.driver, '//select[@name="puntoDeVenta"]'
        )
        select = Select(punto_de_ventas)
        select.select_by_index(1)

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

        # filling serviosios page

        # Consumidor final
        cons_fin = get_element(self.driver, '//select[@id="idivareceptor"]')
        select = Select(cons_fin)
        select.select_by_index(3)

        # Otra checkbox
        otra_chb = get_element(self.driver, '//input[@id="formadepago7"]')
        otra_chb.click()

        click_continuar()

        # filling table page
        producto_text = get_element(
            self.driver, '//textarea[@id="detalle_descripcion1"]'
        )
        producto_text.clear()
        producto_text.send_keys("Servicios prestados")

        # filling unidades
        unidades = get_element(self.driver, '//select[@id="detalle_medida1"]')
        select = Select(unidades)
        select.select_by_index(7)

        # filling precio
        precio = get_element(self.driver, '//input[@id="detalle_precio1"]')
        precio.clear()
        precio.send_keys(str(price))

        click_continuar()

        # final page
        confirmar_datos = get_element(
            self.driver, '//input[@value="Confirmar Datos..."]'
        )
        confirmar_datos.click()

        # ожидание появления окна подтверждения
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.alert_is_present())

        # переключаемся на окно подтверждения и нажимаем "OK"
        alert = self.driver.switch_to.alert
        alert.accept()
        self.driver.switch_to.default_content()

        menu_principal = get_element(
            self.driver, '//input[@value="Menú Principal"]'
        )
        menu_principal.click()
        sleep(0.5)

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()


def save_data_to_file(data, file_path):
    """
    Save the data object to a file in JSON format.

    :param data: The data object to be saved.
    :param file_path: The path of the file where the data will be saved.
    """
    with open(file_path, "w") as file:
        json.dump(data, file)


def read_data_from_file(file_path):
    """
    Read data from a JSON file and convert it into a Python object.

    :param file_path: The path of the file from which to read the data.
    :return: The Python object obtained from the JSON file.
    """
    with open(file_path, "r") as file:
        return json.load(file)
