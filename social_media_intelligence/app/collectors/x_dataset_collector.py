import csv
import json
import hashlib
import logging
import gzip
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator, Tuple

import ijson

from .base_collector import BaseCollector
from ..config import settings
from ..exceptions import (
    XDatasetError,
    XDatasetFileNotFoundError,
    XDatasetFormatError
)
from ..utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# Supported data formats (compression is handled separately)
SUPPORTED_FORMATS = {'csv', 'json', 'jsonl'}

# Field alias mappings: canonical name -> list of possible column names in datasets
FIELD_ALIASES: Dict[str, List[str]] = {
    "post_id": ["id", "tweet_id", "tweetid", "status_id", "post_id", "id_str"],
    "text": ["text", "full_text", "tweet", "content", "tweet_text"],
    "author_id": ["user_id", "author_id", "userid", "authorid", "user.id", "author.id"],
    "username": ["username", "screen_name", "user_name", "author_username", "handle", "user"],
    "display_name": ["name", "display_name", "author_name"],
    "created_at": ["created_at", "createdat", "timestamp", "date", "time", "tweet_created_at"],
    "like_count": ["like_count", "likes", "favorite_count", "favourites", "favoritecount"],
    "retweet_count": ["retweet_count", "retweets", "repost_count", "share_count", "retweetcount"],
    "reply_count": ["reply_count", "replies", "replycount"],
    "quote_count": ["quote_count", "quotes", "quotecount"],
    "view_count": ["view_count", "views", "impression_count", "impressions"],
    "language": ["lang", "language", "tweet_language"],
    "reply_to_status_id": ["in_reply_to_status_id", "reply_to_tweet_id", "in_reply_to_id", "parent_id"],
    "mentions": ["mentions", "user_mentions"],
    "hashtags": ["hashtags"],
    "urls": ["urls", "links"],
}


class XDatasetCollector(BaseCollector):
    """Collector for local X/Twitter dataset files (CSV, JSON, JSONL, optionally GZ compressed).
    
    This collector reads from locally available datasets only.
    It does NOT perform web scraping, API calls, or browser automation.
    """

    def __init__(
        self,
        dataset_path: str,
        dataset_format: Optional[str] = None,
        limit: Optional[int] = None,
        source_name: Optional[str] = None,
        batch_id: Optional[str] = None
    ):
        self.dataset_path = Path(dataset_path)
        self.limit = limit
        self.source_name = source_name or self.dataset_path.stem
        self.batch_id = batch_id
        
        # Auto-detect compression and format
        suffixes = self.dataset_path.suffixes
        self.compressed = False
        self.dataset_format = None

        if suffixes and suffixes[-1].lower() == '.gz':
            self.compressed = True
            if len(suffixes) > 1:
                self.dataset_format = suffixes[-2].lower().lstrip('.')
        elif suffixes:
            self.dataset_format = suffixes[-1].lower().lstrip('.')

        # Override if format explicitly provided
        if dataset_format:
            self.dataset_format = dataset_format.lower().lstrip('.')
            
        if self.dataset_format not in SUPPORTED_FORMATS:
            raise XDatasetFormatError(
                f"Unsupported dataset format: '{self.dataset_format}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        if not self.dataset_path.exists():
            raise XDatasetFileNotFoundError(f"Dataset file not found: {self.dataset_path}")
        
        if not self.dataset_path.is_file():
            raise XDatasetFileNotFoundError(f"Dataset path is not a file: {self.dataset_path}")

    def _open_text_file(self, encoding='utf-8', **kwargs):
        """Common opener for both plain text and gzip compressed files."""
        if self.compressed:
            return gzip.open(self.dataset_path, "rt", encoding=encoding, **kwargs)
        else:
            return open(self.dataset_path, "r", encoding=encoding, **kwargs)

    async def validate_connection(self) -> bool:
        """Validate that the dataset file is accessible and readable."""
        try:
            if not self.dataset_path.exists():
                logger.error(f"Dataset file not found: {self.dataset_path}")
                return False
            # Quick read test
            with self._open_text_file() as f:
                f.read(1)
            return True
        except Exception as e:
            logger.error(f"Cannot read dataset file: {str(e)}")
            return False

    async def collect(self, *args, **kwargs):
        """Deprecated for X collections. Use collect_stream() instead."""
        raise NotImplementedError("Use collect_stream() for chunk-based ingestion of X datasets.")

    def collect_stream(
        self,
        limit: Optional[int] = None,
        chunk_size: int = 5000,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream the dataset file and yield chunks of raw records with collection metadata."""
        effective_limit = limit or self.limit
        
        logger.info(f"Starting X dataset collection from: {self.dataset_path}")
        logger.info(f"Format: {self.dataset_format}, Compressed: {self.compressed}, Limit: {effective_limit or 'None'}")
        
        skipped_count = 0
        duplicate_count = 0
        detected_columns: List[str] = []
        valid_yielded = 0
        
        try:
            if self.dataset_format == 'csv':
                record_generator = self._read_csv_stream()
            elif self.dataset_format == 'json':
                record_generator = self._read_json_stream()
            elif self.dataset_format == 'jsonl':
                record_generator = self._read_jsonl_stream()
            else:
                raise XDatasetFormatError(f"Unhandled format: {self.dataset_format}")
                
            chunk: List[Dict[str, Any]] = []
            
            for item_type, item in record_generator:
                if item_type == "columns":
                    detected_columns = item
                    continue
                    
                # item_type == "record" or "error"
                if item_type == "error":
                    logger.warning(item)
                    skipped_count += 1
                    continue
                    
                # Process mapped record
                mapped = item
                chunk.append(mapped)
                valid_yielded += 1
                
                if len(chunk) >= chunk_size:
                    yield self._create_chunk_response(chunk, valid_yielded, skipped_count, duplicate_count, detected_columns, effective_limit, is_final=False)
                    chunk = []
                    
                if effective_limit and valid_yielded >= effective_limit:
                    break
                    
            if chunk or valid_yielded == 0: # Yield at least once even if empty
                yield self._create_chunk_response(chunk, valid_yielded, skipped_count, duplicate_count, detected_columns, effective_limit, is_final=True)
                
        except (XDatasetFormatError, XDatasetFileNotFoundError):
            raise
        except Exception as e:
            raise XDatasetError(f"Failed to read dataset stream: {str(e)}")
            
        logger.info(f"Dataset reading complete. Total read: {valid_yielded + skipped_count + duplicate_count}, "
                     f"Valid: {valid_yielded}, Skipped: {skipped_count}, "
                     f"Duplicates: {duplicate_count}")

    def _create_chunk_response(self, data, valid_count, skipped_count, duplicate_count, detected_columns, limit, is_final=False):
        now = get_utc_now()
        total_records_read = valid_count + skipped_count + duplicate_count
        
        collection_metadata = {
            "platform": "x",
            "collected_at": now.isoformat(),
            "source": {
                "dataset_file": self.dataset_path.name,
                "dataset_path": str(self.dataset_path),
                "source_name": self.source_name,
                "file_format": self.dataset_format,
                "compression": "gzip" if self.compressed else None,
                "batch_id": self.batch_id,
            },
            "statistics": {
                "total_records_read": total_records_read,
                "valid_records": valid_count,
                "skipped_records": skipped_count,
                "duplicate_records": duplicate_count,
                "detected_columns": detected_columns,
            },
            "filters": {
                "limit": limit,
            },
            "is_final_chunk": is_final
        }

        return {
            "collection_metadata": collection_metadata,
            "data": data
        }

    # =========================================================================
    # Format-specific streaming readers
    # =========================================================================

    def _read_csv_stream(self) -> Generator[Tuple[str, Any], None, None]:
        """Stream records from a CSV file."""
        try:
            with self._open_text_file(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                detected_columns = list(reader.fieldnames or [])
                logger.info(f"Detected CSV columns: {detected_columns}")
                yield ("columns", detected_columns)
                
                for row_num, row in enumerate(reader, start=2):  # row 1 is header
                    try:
                        mapped = self._map_record(dict(row))
                        yield ("record", mapped)
                    except Exception as e:
                        yield ("error", f"CSV row {row_num} skipped: {str(e)}")
                        
        except UnicodeDecodeError:
            raise XDatasetFormatError(f"Encoding error reading CSV: {self.dataset_path}. Ensure the file is UTF-8.")
        except csv.Error as e:
            raise XDatasetFormatError(f"CSV parsing error: {str(e)}")

    def _read_json_stream(self) -> Generator[Tuple[str, Any], None, None]:
        """Stream records from a JSON file. Auto-detects if file is actually JSONL."""
        is_jsonl = False
        try:
            with self._open_text_file(encoding='utf-8') as f:
                dict_lines_count = 0
                for _ in range(5): # Check up to 5 non-empty lines
                    line = f.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            dict_lines_count += 1
                        else:
                            # Found a non-dict line (e.g. `[`, `]`, `""`), it's probably pretty-printed JSON or an array
                            dict_lines_count = 0
                            break
                    except Exception:
                        dict_lines_count = 0
                        break
                        
                # If we found more than 1 consecutive dict line, it's definitely JSONL
                if dict_lines_count > 1:
                    is_jsonl = True
                    
            if is_jsonl:
                logger.info("Auto-detected JSONL content in .json file, switching to JSONL reader")
                yield from self._read_jsonl_stream()
                return

            with self._open_text_file(encoding='utf-8') as f:
                # Find the prefix to stream. We want to stream array items.
                # It could be the root array '' or under 'data', 'tweets', etc.
                parser = ijson.parse(f)
                target_prefix = None
                
                # We need to detect if it's a top-level array or nested
                for prefix, event, value in parser:
                    if event == 'start_array':
                        if prefix == '' or prefix in ('data', 'tweets', 'results', 'records', 'statuses', 'posts'):
                            target_prefix = f"{prefix}.item" if prefix else "item"
                            break
                    elif event == 'start_map' and prefix == '':
                        continue # Top level object, keep searching
                        
                if not target_prefix:
                    # Maybe it's a single object? Re-open and try basic load, 
                    # ijson streaming is mostly for arrays.
                    f.seek(0)
                    try:
                        content = json.load(f)
                        records = self._extract_json_records(content)
                        if records and isinstance(records[0], dict):
                            yield ("columns", list(records[0].keys()))
                        for idx, item in enumerate(records):
                            if not isinstance(item, dict):
                                yield ("error", f"JSON record at index {idx} is not a dict")
                                continue
                            try:
                                yield ("record", self._map_record(item))
                            except Exception as e:
                                yield ("error", f"JSON record at index {idx} skipped: {str(e)}")
                        return
                    except Exception as e:
                        raise XDatasetFormatError(f"Failed to process single JSON object: {str(e)}")

            # If we found a target array prefix, stream it using items
            with self._open_text_file(encoding='utf-8') as f:
                objects = ijson.items(f, target_prefix)
                columns_detected = False
                
                for idx, item in enumerate(objects):
                    if not isinstance(item, dict):
                        yield ("error", f"JSON record at index {idx} is not a dict")
                        continue
                        
                    if not columns_detected:
                        yield ("columns", list(item.keys()))
                        columns_detected = True
                        
                    try:
                        yield ("record", self._map_record(item))
                    except Exception as e:
                        yield ("error", f"JSON record at index {idx} skipped: {str(e)}")
                        
        except (ijson.JSONError, json.JSONDecodeError) as e:
            raise XDatasetFormatError(f"Invalid JSON file: {str(e)}")
        except UnicodeDecodeError:
            raise XDatasetFormatError(f"Encoding error reading JSON: {self.dataset_path}. Ensure the file is UTF-8.")

    def _read_jsonl_stream(self) -> Generator[Tuple[str, Any], None, None]:
        """Stream records from a JSONL file."""
        columns_detected = False
        
        try:
            with self._open_text_file(encoding='utf-8') as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError as e:
                        yield ("error", f"JSONL line {line_num} malformed, skipping: {str(e)}")
                        continue
                    
                    if not isinstance(item, dict):
                        yield ("error", f"JSONL line {line_num} is not a dict, skipping")
                        continue
                    
                    if not columns_detected:
                        yield ("columns", list(item.keys()))
                        columns_detected = True
                    
                    try:
                        yield ("record", self._map_record(item))
                    except Exception as e:
                        yield ("error", f"JSONL line {line_num} skipped: {str(e)}")
                        
        except UnicodeDecodeError:
            raise XDatasetFormatError(f"Encoding error reading JSONL: {self.dataset_path}. Ensure the file is UTF-8.")

    # =========================================================================
    # Field mapping and resolution
    # =========================================================================

    def _resolve_nested_field(self, record: Dict[str, Any], path: str) -> Any:
        """Resolve a field that might be nested (e.g. user.id) using case-insensitive matching."""
        parts = path.lower().split('.')
        current = record
        for part in parts:
            if isinstance(current, dict):
                matched_key = next((k for k in current.keys() if str(k).lower() == part), None)
                if matched_key is not None:
                    current = current[matched_key]
                else:
                    return None
            else:
                return None
        if current is not None and str(current).strip() != '':
            return current
        return None

    def _resolve_field(self, record: Dict[str, Any], aliases: List[str]) -> Any:
        """Return the first available value from a record given a list of possible field names or paths."""
        for alias in aliases:
            val = self._resolve_nested_field(record, alias)
            if val is not None:
                return val
        return None

    def _map_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Map a raw dataset record to a consistent internal representation.
        
        The mapped record preserves the original data under '_original' and adds
        resolved canonical fields.
        """
        mapped = {
            "_original": record,
            "post_id": self._resolve_field(record, FIELD_ALIASES["post_id"]),
            "text": self._resolve_field(record, FIELD_ALIASES["text"]) or "",
            "author_id": self._resolve_field(record, FIELD_ALIASES["author_id"]),
            "username": self._resolve_field(record, FIELD_ALIASES["username"]),
            "display_name": self._resolve_field(record, FIELD_ALIASES["display_name"]),
            "created_at": self._resolve_field(record, FIELD_ALIASES["created_at"]),
            "like_count": self._resolve_field(record, FIELD_ALIASES["like_count"]),
            "retweet_count": self._resolve_field(record, FIELD_ALIASES["retweet_count"]),
            "reply_count": self._resolve_field(record, FIELD_ALIASES["reply_count"]),
            "quote_count": self._resolve_field(record, FIELD_ALIASES["quote_count"]),
            "view_count": self._resolve_field(record, FIELD_ALIASES["view_count"]),
            "language": self._resolve_field(record, FIELD_ALIASES["language"]),
            "reply_to_status_id": self._resolve_field(record, FIELD_ALIASES["reply_to_status_id"]),
            "mentions": self._resolve_field(record, FIELD_ALIASES["mentions"]),
            "hashtags": self._resolve_field(record, FIELD_ALIASES["hashtags"]),
            "urls": self._resolve_field(record, FIELD_ALIASES["urls"]),
        }
        
        # Validation per user requirements
        has_text = bool(mapped.get("text"))
        has_timestamp = bool(mapped.get("created_at"))
        
        if not has_text:
            raise ValueError("Record lacks usable text")
        if not has_timestamp:
            raise ValueError("Record lacks usable timestamp")
            
        return mapped

    @staticmethod
    def _get_unique_id(mapped_record: Dict[str, Any]) -> str:
        """Generate a stable unique identifier for deduplication.
        
        Uses platform + post_id when available, otherwise falls back
        to a deterministic SHA-256 hash of text + created_at + author_id.
        """
        post_id = mapped_record.get("post_id")
        if post_id is not None:
            return f"x:{post_id}"
        
        # Deterministic fallback using SHA-256
        text = mapped_record.get("text", "")
        created_at = mapped_record.get("created_at", "")
        author_id = mapped_record.get("author_id", "")
        hash_input = f"{text}|{created_at}|{author_id}"
        digest = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]
        return f"x:hash:{digest}"

    @staticmethod
    def _extract_json_records(content: Any) -> List[Dict[str, Any]]:
        """Extract a list of records from a JSON structure."""
        if isinstance(content, list):
            return content
        
        if isinstance(content, dict):
            # Check common wrapper keys
            for key in ('data', 'tweets', 'results', 'records', 'statuses', 'posts'):
                if key in content and isinstance(content[key], list):
                    logger.info(f"Using JSON key '{key}' as records source")
                    return content[key]
            
            # If dict has no recognized list key, treat it as a single record
            logger.info("JSON object treated as a single record")
            return [content]
        
        raise XDatasetFormatError(
            "Cannot extract records from JSON. Expected a list or an object "
            "with a recognizable data key (e.g., 'data', 'tweets')."
        )
