# Project Directory Structure

## Overview
This document provides a comprehensive view of the Social Media Intelligence project's directory structure, along with detailed descriptions of the purpose and functionality of each file and module within the architecture.

## Tree Structure
```text
/
├── .vscode
│   └── settings.json
├── app
│   ├── collectors
│   │   ├── __init__.py
│   │   ├── base_collector.py
│   │   ├── telegram_collector.py
│   │   ├── x_dataset_collector.py
│   │   ├── x_network_collector.py
│   │   └── youtube_collector.py
│   ├── normalizers
│   │   ├── __init__.py
│   │   ├── base_normalizer.py
│   │   ├── telegram_normalizer.py
│   │   ├── x_network_normalizer.py
│   │   ├── x_normalizer.py
│   │   └── youtube_normalizer.py
│   ├── schemas
│   │   ├── __init__.py
│   │   ├── nlp_preprocessed_post.py
│   │   ├── sentiment_result.py
│   │   ├── unified_edge.py
│   │   └── unified_post.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── nlp_preprocessing_service.py
│   │   ├── sentiment_analysis_service.py
│   │   ├── telegram_collection_service.py
│   │   ├── unified_timeline_service.py
│   │   ├── x_collection_service.py
│   │   ├── x_network_service.py
│   │   └── youtube_collection_service.py
│   ├── storage
│   │   ├── __init__.py
│   │   ├── network_storage.py
│   │   ├── nlp_storage.py
│   │   ├── processed_storage.py
│   │   ├── raw_storage.py
│   │   └── sentiment_storage.py
│   ├── utils
│   │   ├── __init__.py
│   │   ├── datetime_utils.py
│   │   └── entity_extractor.py
│   ├── __init__.py
│   ├── config.py
│   ├── exceptions.py
│   └── logging_config.py
├── datasets
│   └── x
│       ├── network
│       │   ├── higgs-mention_network.edgelist
│       │   ├── higgs-reply_network.edgelist
│       │   ├── higgs-retweet_network.edgelist
│       │   └── higgs-social_network.edgelist
│       └── posts
│           ├── dataset_network_tweets.csv
│           ├── dataset_tweet_index.csv
│           ├── output.json
│           ├── tweets.csv
│           └── twitter_sentiment_dataset.csv
├── tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_network_storage.py
│   ├── test_nlp_preprocessing_service.py
│   ├── test_sentiment_service.py
│   ├── test_telegram_normalizer.py
│   ├── test_unified_timeline_service.py
│   ├── test_x_collection_service.py
│   ├── test_x_dataset_collector.py
│   ├── test_x_network_collector.py
│   ├── test_x_network_normalizer.py
│   ├── test_x_network_service.py
│   ├── test_x_normalizer.py
│   ├── test_youtube_collection_service.py
│   ├── test_youtube_collector.py
│   └── test_youtube_normalizer.py
├── .env
├── generate_structure.py
├── login.py
├── main.py
├── README.md
├── requirements.txt
├── social_media_intelligence.session
├── stage8_audit.py
└── stage8_production.py
```

## File Descriptions

### `/.vscode`
- **`settings.json`**: VS Code workspace settings tailored to the project (e.g. formatters, linters, and python pathing).

### `/app/collectors`
*Contains classes responsible for ingesting raw data from various social media datasets or APIs.*
- **`__init__.py`**: Module initialization for collectors.
- **`base_collector.py`**: Defines the abstract base class and core interfaces that all platform-specific collectors inherit from.
- **`telegram_collector.py`**: Ingests and parses raw Telegram channel exports and message data.
- **`x_dataset_collector.py`**: Ingests and parses X (Twitter) post datasets (e.g. CSVs and JSON exports).
- **`x_network_collector.py`**: Ingests X (Twitter) network graph data (e.g., retweets, mentions, replies edgelists).
- **`youtube_collector.py`**: Ingests raw YouTube comments and metadata.

### `/app/normalizers`
*Responsible for transforming raw platform-specific data formats into a standardized internal schema.*
- **`__init__.py`**: Module initialization for normalizers.
- **`base_normalizer.py`**: Abstract base class defining the normalization interface.
- **`telegram_normalizer.py`**: Maps Telegram fields to the unified schema.
- **`x_network_normalizer.py`**: Formats X edgelist data into unified relationship edges (Source, Target, Timestamp).
- **`x_normalizer.py`**: Maps X (Twitter) post data (tweets, retweets) to the unified schema.
- **`youtube_normalizer.py`**: Maps YouTube comment/video data to the unified schema.

### `/app/schemas`
*Defines Pydantic data models used to enforce typing, validation, and consistency across the pipeline.*
- **`__init__.py`**: Module initialization for schemas.
- **`nlp_preprocessed_post.py`**: Defines the schema for posts that have undergone NLP cleaning (e.g., entity extraction, URL removal).
- **`sentiment_result.py`**: Defines the schema for the output of the Sentiment Analysis model (labels, confidences, probability distributions).
- **`unified_edge.py`**: Unified Edge Schema for representing social network relationships (graph edges).
- **`unified_post.py`**: Unified Post Schema standardizing fields like text, author, timestamp, and platform across all sources.

### `/app/services`
*The core business logic layer. Orchestrates data flow between collectors, normalizers, AI models, and storage.*
- **`__init__.py`**: Module initialization for services.
- **`nlp_preprocessing_service.py`**: Handles text cleaning, regex matching, hashtag/mention extraction, and preparing text for AI models.
- **`sentiment_analysis_service.py`**: Loads the XLM-RoBERTa sentiment model on the GPU, handles batched tensor tokenization, and computes sentiment predictions.
- **`telegram_collection_service.py`**: Orchestrates the collection, normalization, and saving of Telegram data.
- **`unified_timeline_service.py`**: Merges normalized data from all platforms into a single chronologically sorted timeline.
- **`x_collection_service.py`**: Orchestrates the collection, normalization, and saving of X post data.
- **`x_network_service.py`**: Orchestrates the processing and storage of X relationship/network graph datasets.
- **`youtube_collection_service.py`**: Orchestrates the collection, normalization, and saving of YouTube data.

### `/app/storage`
*Handles file-system I/O, dataset chunking, DuckDB integration, and JSONL disk writing.*
- **`__init__.py`**: Module initialization for storage.
- **`network_storage.py`**: Handles writing network edgelists and relationship graphs.
- **`nlp_storage.py`**: Handles writing chunked NLP-preprocessed posts.
- **`processed_storage.py`**: Handles the storage of fully normalized unified posts.
- **`raw_storage.py`**: Manages the ingestion of raw, unparsed data.
- **`sentiment_storage.py`**: Handles appending and checkpointing ML sentiment inferences to JSONL files safely.

### `/app/utils`
*Helper functions and utilities.*
- **`__init__.py`**: Module initialization for utilities.
- **`datetime_utils.py`**: Standardizes date parsing, timezone handling, and UTC conversions across heterogeneous dataset timestamps.
- **`entity_extractor.py`**: Regex and string manipulation utilities for extracting handles, URLs, and hashtags.

### `/app`
- **`__init__.py`**: Main app module initialization.
- **`config.py`**: Centralized configuration management (paths, batch sizes, environment variable loading).
- **`exceptions.py`**: Custom domain-specific exception classes for the application.
- **`logging_config.py`**: Configures Python's built-in `logging` (formatters, handlers, log levels).

### `/datasets`
*Local data storage for raw inputs.*
- **`x/network/higgs-*.edgelist`**: HIGGS dataset raw edgelists containing network relationships (mentions, replies, retweets, social).
- **`x/posts/*.csv` & `*.json`**: Raw dataset files containing millions of tweets and labeled sentiment data.

### `/tests`
*Pytest test suite covering core logic and data pipelines.*
- **`conftest.py`**: Pytest fixtures (mock data, temp directories) shared across tests.
- **`test_*.py`**: Unit tests corresponding to their respective modules in `app/normalizers`, `app/services`, and `app/storage`.

### `/ (Root Files)`
- **`.env`**: Environment variables (secrets, paths).
- **`generate_structure.py`**: Utility script written to dynamically generate this directory structure markdown file.
- **`login.py`**: Standalone script for testing Telegram or other API authentications.
- **`main.py`**: The primary CLI entry point for the application. Orchestrates full end-to-end runs.
- **`README.md`**: Main project documentation.
- **`requirements.txt`**: Python package dependencies.
- **`social_media_intelligence.session`**: Telethon session file for persistent Telegram API login.
- **`stage8_audit.py`**: Executes the deterministic identity and sequence audit for the Stage 8 Sentiment Analysis outputs.
- **`stage8_production.py`**: Production entry point for processing the 25.4 million records via the Stage 8 pipeline.
