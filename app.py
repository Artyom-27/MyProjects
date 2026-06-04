
# =========================================================
# IMPORTS
# =========================================================

import streamlit as st
import pandas as pd
import requests
import re
import time
from io import BytesIO
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
from tenacity import retry, stop_after_attempt, wait_exponential


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="App Store Reviews Parser",
    layout="wide"
)

DetectorFactory.seed = 0

REGION = "ru"
MAX_PAGES = 10
MAX_WORKERS = 8
REQUEST_TIMEOUT = 20


# =========================================================
# UI
# =========================================================

st.title("🍏 App Store Reviews Parser")

st.markdown("""
Сбор отзывов из Apple App Store:

✅ Только регион RU  
✅ Только отзывы с текстом  
✅ Только последние 4 месяца  
✅ Автоопределение языка  
✅ Перевод на русский  
✅ Экспорт CSV / XLSX  
""")

app_id = st.text_input(
    "Введите App Store ID",
    placeholder="Например: 686449807"
)


# =========================================================
# HELPERS
# =========================================================

def log(message):
    st.write(message)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=20)
)
def safe_get(url, params=None):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code in [429, 500, 502, 503, 504]:
        raise Exception(f"HTTP Error: {response.status_code}")

    response.raise_for_status()

    return response


def sanitize_filename(name):

    name = name.lower().strip()

    name = re.sub(r"[^a-zA-Zа-яА-Я0-9_]+", "_", name)

    return name.strip("_")


def get_app_info(app_id):

    url = "https://itunes.apple.com/lookup"

    params = {
        "id": app_id,
        "country": REGION
    }

    response = safe_get(url, params=params)

    data = response.json()

    if data.get("resultCount", 0) == 0:
        raise Exception("Приложение не найдено")

    result = data["results"][0]

    return result.get("trackName", f"app_{app_id}")


# =========================================================
# FETCH REVIEWS
# =========================================================

def fetch_reviews(app_id, progress_bar):

    all_reviews = []

    four_months_ago = datetime.now(
        timezone.utc
    ) - timedelta(days=120)

    for page in range(1, MAX_PAGES + 1):

        progress_bar.progress(page / MAX_PAGES)

        log(f"📄 Загрузка страницы {page}")

        url = (
            f"https://itunes.apple.com/{REGION}/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json"
        )

        try:

            response = safe_get(url)

            data = response.json()

        except Exception as e:

            log(f"❌ Ошибка страницы {page}: {e}")

            continue

        feed = data.get("feed", {})
        entries = feed.get("entry", [])

        if len(entries) <= 1:

            log("Отзывы закончились")

            break

        page_count = 0

        for entry in entries[1:]:

            try:

                review_text = (
                    entry.get("content", {})
                    .get("label", "")
                    .strip()
                )

                if not review_text:
                    continue

                review_date_str = (
                    entry.get("updated", {})
                    .get("label")
                )

                review_date = datetime.fromisoformat(
                    review_date_str.replace("Z", "+00:00")
                )

                if review_date < four_months_ago:
                    continue

                review = {
                    "review_title": (
                        entry.get("title", {})
                        .get("label", "")
                    ),

                    "review_text": review_text,

                    "rating": int(
                        entry.get("im:rating", {})
                        .get("label", 0)
                    ),

                    "date": review_date,

                    "user_name": (
                        entry.get("author", {})
                        .get("name", {})
                        .get("label", "")
                    ),

                    "app_version": (
                        entry.get("im:version", {})
                        .get("label", "")
                    ),

                    "country": REGION.upper(),

                    "developer_response": (
                        entry.get("im:developerResponse", {})
                        .get("im:content", {})
                        .get("label", "")
                    )
                }

                all_reviews.append(review)

                page_count += 1

            except Exception as e:

                log(f"Ошибка обработки отзыва: {e}")

        log(f"✅ Страница {page}: {page_count} отзывов")

        time.sleep(1)

    return all_reviews


# =========================================================
# LANGUAGE + TRANSLATION
# =========================================================

def detect_language(text):

    try:
        return detect(text)

    except:
        return "unknown"


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=15)
)
def translate_to_russian(text, lang):

    if not text:
        return ""

    if lang == "ru":
        return text

    try:

        translated = GoogleTranslator(
            source="auto",
            target="ru"
        ).translate(text)

        return translated

    except:

        return text


def process_review(review):

    text = review["review_text"]

    lang = detect_language(text)

    translated = translate_to_russian(text, lang)

    review["language"] = lang

    review["translated_review_ru"] = translated

    return review


# =========================================================
# EXCEL EXPORT
# =========================================================

def create_excel_file(df):

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="reviews"
        )

        ws = writer.sheets["reviews"]

        for column_cells in ws.columns:

            length = max(
                len(str(cell.value)) if cell.value else 0
                for cell in column_cells
            )

            adjusted_width = min(length + 5, 80)

            ws.column_dimensions[
                column_cells[0].column_letter
            ].width = adjusted_width

    output.seek(0)

    return output


# =========================================================
# MAIN
# =========================================================

if st.button("🚀 Начать сбор отзывов"):

    if not app_id.strip():

        st.error("Введите App Store ID")

    else:

        try:

            # -------------------------------------------------
            # APP INFO
            # -------------------------------------------------

            with st.spinner("Получение информации о приложении..."):

                app_name = get_app_info(app_id)

                safe_app_name = sanitize_filename(app_name)

            st.success(f"Найдено приложение: {app_name}")

            # -------------------------------------------------
            # FETCH REVIEWS
            # -------------------------------------------------

            progress_bar = st.progress(0)

            reviews = fetch_reviews(
                app_id,
                progress_bar
            )

            if not reviews:

                st.warning("Отзывы не найдены")

                st.stop()

            # -------------------------------------------------
            # REMOVE DUPLICATES
            # -------------------------------------------------

            unique_reviews = []

            seen = set()

            for r in reviews:

                key = (
                    r["review_text"],
                    r["user_name"],
                    str(r["date"])
                )

                if key not in seen:

                    seen.add(key)

                    unique_reviews.append(r)

            reviews = unique_reviews

            st.info(f"Отзывы после удаления дублей: {len(reviews)}")

            # -------------------------------------------------
            # MULTITHREADING
            # -------------------------------------------------

            st.write("🌍 Определение языка и перевод...")

            processed_reviews = []

            translation_progress = st.progress(0)

            with ThreadPoolExecutor(
                max_workers=MAX_WORKERS
            ) as executor:

                futures = [
                    executor.submit(process_review, review)
                    for review in reviews
                ]

                completed = 0

                for future in as_completed(futures):

                    try:

                        processed_reviews.append(
                            future.result()
                        )

                    except Exception as e:

                        log(f"Ошибка потока: {e}")

                    completed += 1

                    translation_progress.progress(
                        completed / len(futures)
                    )

            # -------------------------------------------------
            # DATAFRAME
            # -------------------------------------------------

            df = pd.DataFrame(processed_reviews)

            df["date"] = pd.to_datetime(df["date"])

            df = df.sort_values(
                by="date",
                ascending=False
            ).reset_index(drop=True)

            # -------------------------------------------------
            # FILENAMES
            # -------------------------------------------------

            csv_filename = (
                f"reviews_{safe_app_name}_ru.csv"
            )

            xlsx_filename = (
                f"reviews_{safe_app_name}_ru.xlsx"
            )

            # -------------------------------------------------
            # CSV
            # -------------------------------------------------

            csv_data = df.to_csv(
                index=False,
                encoding="utf-8-sig"
            ).encode("utf-8-sig")

            # -------------------------------------------------
            # XLSX
            # -------------------------------------------------

            excel_data = create_excel_file(df)

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            st.success("✅ Готово!")

            st.subheader("📊 Preview DataFrame")

            st.dataframe(
                df.head(20),
                use_container_width=True
            )

            # -------------------------------------------------
            # DOWNLOAD BUTTONS
            # -------------------------------------------------

            col1, col2 = st.columns(2)

            with col1:

                st.download_button(
                    label="⬇️ Скачать CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv"
                )

            with col2:

                st.download_button(
                    label="⬇️ Скачать XLSX",
                    data=excel_data,
                    file_name=xlsx_filename,
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    )
                )

        except Exception as e:

            st.error(f"Ошибка: {e}")

