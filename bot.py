import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from parser import parse_city, preprocessing, save_to_excel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("parser.log", encoding="utf-8"),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

CITY, QUERY = range(2)

WELCOME_TEXT = (
    "Привет! Я бот для сбора данных об организациях с Яндекс.Карт.\n\n"
    "Как пользоваться:\n"
    "1. Отправьте город, в котором нужно искать\n"
    "2. Отправьте поисковый запрос (например: «Стоматологическая клиника»)\n"
    "3. Я соберу данные (название, телефон, рейтинг, сайт, соцсети и т.д.) "
    "и пришлю готовый Excel-файл\n\n"
    "Команда /cancel — отменить текущий поиск.\n\n"
    "Введите город, с которого начнём:"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(WELCOME_TEXT)
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    city = update.message.text.strip()
    if not city:
        await update.message.reply_text("Город не может быть пустым. Введите город:")
        return CITY

    context.user_data["city"] = city
    await update.message.reply_text(
        "Теперь введите поисковый запрос (например: «Ремонт квартир под ключ»):"
    )
    return QUERY


async def get_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Запрос не может быть пустым. Введите запрос:")
        return QUERY

    city = context.user_data["city"]
    chat_id = update.effective_chat.id

    await update.message.reply_text(f"Парсинг начался: {city} / {query}")

    loop = asyncio.get_running_loop()

    def progress_callback(count: int) -> None:
        asyncio.run_coroutine_threadsafe(
            context.bot.send_message(
                chat_id=chat_id,
                text=f"Найдено заведений: {count}. Собираю данные, это может занять время...",
            ),
            loop,
        )

    try:
        df = await asyncio.to_thread(
            parse_city, city, query, progress_callback=progress_callback
        )
    except Exception:
        logger.exception("Ошибка парсинга %s / %s", city, query)
        await update.message.reply_text(
            "Произошла ошибка при парсинге. Попробуйте позже или начните заново: /start"
        )
        return ConversationHandler.END

    if df.empty:
        await update.message.reply_text(
            "Ничего не найдено по этому запросу. Начните заново: /start"
        )
        return ConversationHandler.END

    df.insert(0, "Город", city)
    df_filtered = preprocessing(df)

    try:
        path_to_excel = await asyncio.to_thread(save_to_excel, df_filtered, query)
    except Exception:
        logger.exception("Не удалось сохранить файл для %s / %s", city, query)
        await update.message.reply_text("Не удалось сохранить файл результатов.")
        return ConversationHandler.END

    await update.message.reply_text(f"Парсинг завершен. Найдено записей: {len(df_filtered)}.")

    with open(path_to_excel, "rb") as f:
        await update.message.reply_document(f)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создайте файл .env (см. .env.example) и укажите "
            "токен, полученный у @BotFather."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_query)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    logger.info("Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()
