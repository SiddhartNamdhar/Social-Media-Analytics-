# Social Media Intelligence

This project provides a robust, staged pipeline for collecting and normalizing social media data into a unified schema for AI-driven analytics. It currently supports extracting data from local **X/Twitter** datasets, the **Telegram** live network, and the **YouTube Data API v3**.

## Architecture

The system uses a staged ingestion architecture:

1. **Collectors**: Stream data from the source (local files for X, live API for Telegram) and manage the I/O cleanly.
2. **Normalizers**: Convert raw, platform-specific records into a strictly typed unified schema (`UnifiedPost` for posts, `UnifiedEdge` for network relationships). 
3. **Storage**: Provides robust storage layers:
   - **Raw Storage**: Captures immutable raw chunks exactly as received in `.jsonl` formats under `data/raw/<platform>/YYYY-MM-DD/<batch_id>/`.
   - **Processed Storage**: Stores cleanly normalized, deduplicated records in JSONL format under `data/processed/<platform>/YYYY-MM-DD/`.
4. **Services**: Orchestrates the Collectors, Normalizers, and Storage cleanly, accumulating collection statistics dynamically.

## Scope Policy

**Strict Rule:** Do not add scraping, Selenium, Playwright, login automation, YouTube API bypasses, or external X API bypasses. 
- X ingestion works **only** with legitimately obtained local files.
- YouTube ingestion must work **only** with the official YouTube Data API v3. YouTube calls are opt-in and quota-safe by default.

## X / Twitter Data Collection

This collector processes large local JSON, JSONL, CSV, and GZIP compressed files efficiently.

### Posts Data
Use `XDatasetCollector` (via `XCollectionService`) for post extraction. 
Requirements:
- Datasets must contain usable text and a timestamp (e.g., `datasets/x/posts/tweets.csv`).
- A case-insensitive heuristic automatically maps known aliases like `tweetId`, `createdAt`, `retweets`, etc.
- Missing timestamps strictly cause records to be rejected (no fallback to current time).

### Network Data
Use `XNetworkCollector` (via `XNetworkService`) for processing edgelists (e.g., `datasets/x/network/higgs-retweet_network.edgelist`).
Requirements:
- Supports space or comma delimited lists with configurable columns (source, target, timestamp, weight).
- Converts relations into `UnifiedEdge`.

## Telegram Data Collection

Extracts live messages from public Telegram channels.

### Setup
1. Create Telegram API credentials by visiting https://my.telegram.org.
2. Copy `.env.example` to `.env`.
3. Add your `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_PHONE` strictly in the `.env` file.

When you first run the program, Telethon may request a phone verification code or 2FA password in the CLI.

## YouTube Data Collection

Extracts videos, comments, and replies from the official YouTube Data API v3.

### Setup
1. Create a YouTube Data API v3 key via the Google Cloud Console.
2. Add your `YOUTUBE_API_KEY` to the `.env` file. You can also customize `YOUTUBE_DEFAULT_REGION_CODE`, `YOUTUBE_MAX_RESULTS`, etc.

### Collection Modes
- **Keyword Search**: Uses `YouTubeCollectionService.collect_by_keyword(query)` to find videos related to a topic. It saves videos to Raw Storage, then collects top-level comments and replies for each video.
- **Normalization**: Only comments and replies are normalized as `UnifiedPost` items. Videos are stored as raw/context-only records in Raw Storage to conserve storage and complexity.
- **Quota Safety**: 403 quota exhaustion errors from Google are carefully intercepted, pausing collection without crashing the system or discarding already-retrieved data.

## Quickstart

1. Create a virtual environment (`python -m venv venv`) and activate it.
2. Install requirements using `pip install -r requirements.txt`.
3. You can run the various data collections by specifying the appropriate flags:
```powershell
python main.py --youtube
python main.py --x-posts
python main.py --x-network
python main.py --telegram
```
