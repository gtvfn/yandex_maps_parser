import logging
import re
from random import choice, uniform
from time import sleep
from typing import Callable

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


def _get_safe_text(tag, selector, attr_name=None) -> str:
    try:
        element = tag.select_one(selector)
        if not element:
            return ""

        if attr_name:
            return element.get(attr_name, "").strip()

        return element.text.strip()
    except Exception:
        logger.debug("Не удалось извлечь текст по селектору %s", selector, exc_info=True)
        return ""


def preprocessing(
    df: pd.DataFrame,
    min_reviews: int | None = None,
    max_reviews: int | None = None,
    min_rating: float | None = None,
    max_rating: float | None = None,
) -> pd.DataFrame:
    """
    Removes duplicates by URL and filters by review count range
    and rating range. Any parameter can be omitted (None),
    in which case no restriction is applied for it.
    """
    if df.empty:
        logger.warning("Пустой DataFrame, фильтрация пропущена")
        return df

    df = df.drop_duplicates(subset=["URL"])

    condition = pd.Series(True, index=df.index)

    if min_reviews is not None:
        condition &= df["Кол-во отзывов"] >= min_reviews
    if max_reviews is not None:
        condition &= df["Кол-во отзывов"] <= max_reviews
    if min_rating is not None:
        condition &= df["Рейтинг"] >= min_rating
    if max_rating is not None:
        condition &= df["Рейтинг"] <= max_rating

    df_filtered = df[condition]

    logger.info("Строк после фильтрации: %s из %s", len(df_filtered), len(df))

    return df_filtered


def _init_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f"user-agent={choice(USER_AGENTS)}")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)


def parse_city(
    city: str,
    query: str,
    count_of_units: int = 1000,
    progress_callback: Callable[[int], None] | None = None,
    headless: bool = True,
) -> pd.DataFrame:
    logger.info("Парсинг %s по запросу %s", city, query)

    empty_df = pd.DataFrame(
        columns=[
            "URL",
            "Наименование",
            "Телефон",
            "Рейтинг",
            "Кол-во отзывов",
            "Сайт",
            "Instagram",
            "WhatsApp",
            "Telegram",
        ]
    )

    try:
        driver = _init_driver(headless=headless)
    except WebDriverException:
        logger.exception("Не удалось запустить Chrome driver")
        return empty_df

    try:
        url = f"https://yandex.ru/maps/213/moscow/search/{city}%20{query}"
        driver.get(url)

        wait = WebDriverWait(driver, 10)
        try:
            elements = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, ".search-list-view__content")
                )
            )
        except TimeoutException:
            logger.error("Не найден список результатов для %s / %s", city, query)
            return empty_df

        n = 0
        while len(elements) < count_of_units:
            sleep(uniform(0.5, 1))

            elements1 = len(elements)
            elements = driver.find_elements(
                By.CLASS_NAME, "search-business-snippet-view__content"
            )
            if not elements:
                logger.warning("Список заведений пуст при скролле, прекращаем")
                break

            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", elements[-1])
            except WebDriverException:
                logger.warning("Не удалось проскроллить к элементу", exc_info=True)

            elements = driver.find_elements(
                By.CLASS_NAME, "search-business-snippet-view__content"
            )
            elements2 = len(elements)

            if elements1 == elements2:
                n += 1
                if n >= 20:
                    break
            else:
                n = 0

        wait = WebDriverWait(driver, 3)
        try:
            elements = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".search-snippet-view"))
            )
        except TimeoutException:
            logger.error("Не удалось получить карточки заведений для %s / %s", city, query)
            return empty_df

        href_list = []
        for i in elements:
            try:
                link_element = i.find_element(By.TAG_NAME, "a")
                href = link_element.get_attribute("href")
                if href:
                    href_list.append(href)
            except Exception:
                logger.debug("Не удалось получить ссылку на заведение", exc_info=True)

        logger.info("Кол-во заведений: %s", len(href_list))

        if progress_callback is not None:
            try:
                progress_callback(len(href_list))
            except Exception:
                logger.exception("Ошибка в progress_callback")

        keys = {
            "URL": [],
            "Наименование": [],
            "Телефон": [],
            "Рейтинг": [],
            "Кол-во отзывов": [],
            "Сайт": [],
            "Instagram": [],
            "WhatsApp": [],
            "Telegram": [],
        }

        for index, href in enumerate(href_list):
            try:
                driver.get(href)
            except WebDriverException:
                logger.warning("Не удалось открыть %s", href, exc_info=True)
                continue

            if "showcaptcha" in driver.current_url or driver.title == "":
                logger.warning("Возможна капча, пауза 90 сек...")
                sleep(90)
                try:
                    driver.get(href)
                except WebDriverException:
                    logger.warning("Повторно не удалось открыть %s", href, exc_info=True)
                    continue

            try:
                wait.until(
                    EC.presence_of_all_elements_located(
                        (
                            By.CSS_SELECTOR,
                            "span.business-urls-view__text, div.orgpage-phones-view__phone-number, "
                            "[aria-label='Соцсети, instagram'], [aria-label='Соцсети, telegram']",
                        )
                    )
                )
                sleep(uniform(1, 3))
            except TimeoutException:
                logger.info("%s/%s - пропущен (нет контактов)", index + 1, len(href_list))
                continue

            try:
                source = driver.page_source
                soup = BeautifulSoup(source, "html.parser")

                keys["URL"].append(href)
                keys["Наименование"].append(
                    _get_safe_text(soup, "h1.orgpage-header-view__header")
                )

                phone = _get_safe_text(soup, "div.orgpage-phones-view__phone-number")
                clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
                keys["Телефон"].append(clean_phone)

                rate = _get_safe_text(soup, "span.business-rating-badge-view__rating-text")
                if rate:
                    try:
                        keys["Рейтинг"].append(float(rate.replace(",", ".")))
                    except ValueError:
                        logger.debug("Не удалось распарсить рейтинг: %s", rate)
                        keys["Рейтинг"].append(0.0)
                else:
                    keys["Рейтинг"].append(0.0)

                rate_counts = _get_safe_text(
                    soup, "div.business-header-rating-view__text._clickable"
                )
                clean_rate_counts = re.sub(r"\D", "", rate_counts)
                keys["Кол-во отзывов"].append(int(clean_rate_counts) if clean_rate_counts else 0)

                site_url = _get_safe_text(soup, "span.business-urls-view__text")
                full_site_url = "https://" + site_url if site_url != "" else ""
                keys["Сайт"].append(full_site_url)

                keys["Instagram"].append(
                    _get_safe_text(soup, "[aria-label='Соцсети, instagram']", attr_name="href")
                )

                wa = f"https://wa.me/{clean_phone}" if clean_phone else ""
                keys["WhatsApp"].append(wa)

                keys["Telegram"].append(
                    _get_safe_text(soup, "[aria-label='Соцсети, telegram']", attr_name="href")
                )

                logger.info("%s/%s обработан", index + 1, len(href_list))
            except Exception:
                logger.exception("Ошибка при разборе карточки %s", href)
                continue

        df = pd.DataFrame(keys)
        return df

    except Exception:
        logger.exception("Непредвиденная ошибка при парсинге %s / %s", city, query)
        return empty_df
    finally:
        try:
            driver.quit()
        except Exception:
            logger.debug("Ошибка при закрытии driver", exc_info=True)


LINK_COLUMNS = ["URL", "Сайт", "Instagram", "WhatsApp", "Telegram"]


def _make_links_clickable(path_to_excel: str) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Font

    wb = load_workbook(path_to_excel)
    ws = wb.active

    header = [cell.value for cell in ws[1]]
    hyperlink_font = Font(color="0563C1", underline="single")

    for col_name in LINK_COLUMNS:
        if col_name not in header:
            continue
        col_idx = header.index(col_name) + 1
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=col_idx)
            value = cell.value
            if value and str(value).startswith("http"):
                cell.hyperlink = str(value)
                cell.font = hyperlink_font

    wb.save(path_to_excel)


def save_to_excel(df: pd.DataFrame, query: str) -> str:
    """
    Saves the results for a single query into one file (all passed
    cities combined). Links in the URL/Site/Instagram/WhatsApp/Telegram
    columns are made clickable. Returns the path to the saved file.
    """
    clean_query = query.strip().replace(" ", "_")
    path_to_excel = f"{clean_query}.xlsx"

    df.to_excel(path_to_excel, index=False)
    _make_links_clickable(path_to_excel)
    logger.info("Файл сохранен: %s (строк: %s)", path_to_excel, len(df))
    return path_to_excel
