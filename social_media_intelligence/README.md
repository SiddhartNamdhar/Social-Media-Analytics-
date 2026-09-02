# README for Social Media Intelligence - Telegram Collector

# Task: Build a Telegram Data Collector for an AI-Driven Social Media Analytics Framework

This project contains a data collection module for Telegram that extracts public telegram messages and normalizes them into a `UnifiedPost` JSON format.

## Setup

1. Create Telegram API credentials by visiting https://my.telegram.org.
2. Create a virtual environment (`python -m venv venv`) and activate it.
3. Install requirements using `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Add your `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_PHONE` strictly in the `.env` file.

## First Run

When you first run the program, Telethon may request:
- A phone verification code
- Your Two-factor authentication password (if enabled)

The generated `.session` file should allow future runs without repeatedly authenticating.

## Run

Modify `main.py` configuration to use a public channel you want to test with.
```bash
python main.py
```

## Output

- **`data/raw/telegram/`**: Contains immutable/raw Telegram data exactly as extracted from Telethon in JSON format.
- **`data/processed/telegram/`**: Contains standardized `UnifiedPost` records in JSON Lines format (`posts.jsonl`).
