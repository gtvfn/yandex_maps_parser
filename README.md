# Yandex Maps to Excel

A Telegram bot that collects business listings from Yandex Maps and sends the results as an Excel workbook. I built it to turn a city and a search term into a spreadsheet that can be filtered and reused.

## What the workbook contains

The bot removes duplicate listing URLs and exports the business name, rating, review count and contact fields when available. Links in the workbook are clickable.

| Business | Rating | Reviews | Website |
| --- | ---: | ---: | --- |
| Example Coffee | 4.7 | 82 | example.com |
| Sample Bakery | 4.5 | 31 |  |

These sample values are fictional and the table shows a subset of the columns. The current bot prompts and workbook headers are in Russian.

## Run the bot

Use Python 3.10 or later and have Chrome available to Selenium. From the repository root, install the dependencies.

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in the repository root.

```dotenv
BOT_TOKEN=
```

Set `BOT_TOKEN` to your bot token and run `python bot.py`. Open the bot in Telegram, send `/start`, then enter a city and a search term.

Collection depends on the current Yandex Maps page structure. Contact fields can be blank when the source listing omits them.
