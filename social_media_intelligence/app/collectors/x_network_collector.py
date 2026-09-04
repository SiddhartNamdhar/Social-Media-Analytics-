import csv
import gzip
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator, Tuple

from .base_collector import BaseCollector
from ..exceptions import (
    XDatasetError,
    XDatasetFileNotFoundError,
    XDatasetFormatError
)
from ..utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {'edgelist'}

class XNetworkCollector(BaseCollector):
    """Collector for local X/Twitter network datasets (.edgelist)."""

    def __init__(
        self,
        dataset_path: str,
        relationship_type: str = "UNKNOWN",
        limit: Optional[int] = None,
        delimiter: Optional[str] = None,
        has_header: bool = False,
        source_column: int = 0,
        target_column: int = 1,
        timestamp_column: Optional[int] = None,
        weight_column: Optional[int] = None,
        batch_id: Optional[str] = None
    ):
        self.dataset_path = Path(dataset_path)
        self.relationship_type = relationship_type.upper()
        self.limit = limit
        self.delimiter = delimiter
        self.has_header = has_header
        
        self.source_column = source_column
        self.target_column = target_column
        self.timestamp_column = timestamp_column
        self.weight_column = weight_column
        self.batch_id = batch_id
        
        suffixes = self.dataset_path.suffixes
        self.compressed = False
        self.dataset_format = None

        if suffixes and suffixes[-1].lower() == '.gz':
            self.compressed = True
            if len(suffixes) > 1:
                self.dataset_format = suffixes[-2].lower().lstrip('.')
        elif suffixes:
            self.dataset_format = suffixes[-1].lower().lstrip('.')

        if self.dataset_format not in SUPPORTED_FORMATS:
            raise XDatasetFormatError(
                f"Unsupported dataset format: '{self.dataset_format}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        if not self.dataset_path.exists() or not self.dataset_path.is_file():
            raise XDatasetFileNotFoundError(f"Dataset file not found: {self.dataset_path}")

    def _open_text_file(self, encoding='utf-8', **kwargs):
        if self.compressed:
            return gzip.open(self.dataset_path, "rt", encoding=encoding, **kwargs)
        else:
            return open(self.dataset_path, "r", encoding=encoding, **kwargs)

    async def validate_connection(self) -> bool:
        try:
            if not self.dataset_path.exists():
                return False
            with self._open_text_file() as f:
                f.read(1)
            return True
        except Exception as e:
            logger.error(f"Cannot read dataset file: {str(e)}")
            return False

    async def collect(self, *args, **kwargs):
        """Deprecated for X collections. Use collect_stream() instead."""
        raise NotImplementedError("Use collect_stream() for chunk-based ingestion of network datasets.")

    def collect_stream(
        self,
        limit: Optional[int] = None,
        chunk_size: int = 5000,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        
        effective_limit = limit or self.limit
        logger.info(f"Starting X network collection from: {self.dataset_path}")
        
        skipped_count = 0
        duplicate_count = 0
        valid_yielded = 0
        
        chunk = []
        
        try:
            with self._open_text_file() as f:
                # If delimiter is not provided, try to detect it by sniffing the first few bytes (or just fallback to whitespace)
                delim = self.delimiter
                if not delim:
                    sample = f.read(1024)
                    f.seek(0)
                    if '\t' in sample:
                        delim = '\t'
                    elif ',' in sample:
                        delim = ','
                    else:
                        delim = None # whitespace split
                        
                reader = csv.reader(f, delimiter=delim) if delim else (line.split() for line in f)
                
                for row_num, row in enumerate(reader):
                    if not row:
                        continue
                        
                    if row_num == 0 and self.has_header:
                        continue
                        
                    try:
                        if len(row) <= max(self.source_column, self.target_column):
                            skipped_count += 1
                            continue
                            
                        source = row[self.source_column].strip()
                        target = row[self.target_column].strip()
                        
                        if not source or not target:
                            skipped_count += 1
                            continue
                            
                        mapped = {
                            "_original": row,
                            "source": source,
                            "target": target,
                            "relationship_type": self.relationship_type
                        }
                        
                        if self.timestamp_column is not None and len(row) > self.timestamp_column:
                            mapped["timestamp"] = row[self.timestamp_column].strip()
                            
                        if self.weight_column is not None and len(row) > self.weight_column:
                            mapped["weight"] = row[self.weight_column].strip()
                            
                        chunk.append(mapped)
                        valid_yielded += 1
                        
                        if len(chunk) >= chunk_size:
                            yield self._create_chunk_response(chunk, valid_yielded, skipped_count, duplicate_count, effective_limit, delim, is_final=False)
                            chunk = []
                            
                        if effective_limit and valid_yielded >= effective_limit:
                            break
                    except Exception as e:
                        skipped_count += 1
                        logger.warning(f"Error parsing row {row_num}: {str(e)}")
                        
                if chunk or valid_yielded == 0:
                    yield self._create_chunk_response(chunk, valid_yielded, skipped_count, duplicate_count, effective_limit, delim, is_final=True)
                    
        except Exception as e:
            raise XDatasetError(f"Failed to read dataset stream: {str(e)}")

    def _create_chunk_response(self, data, valid_count, skipped_count, duplicate_count, limit, delimiter, is_final=False):
        now = get_utc_now()
        total_records_read = valid_count + skipped_count + duplicate_count
        
        return {
            "collection_metadata": {
                "platform": "x",
                "collected_at": now.isoformat(),
                "dataset_type": "network",
                "source": {
                    "dataset_file": self.dataset_path.name,
                    "dataset_path": str(self.dataset_path),
                    "file_format": self.dataset_format,
                    "compression": "gzip" if self.compressed else None,
                    "batch_id": self.batch_id,
                },
                "statistics": {
                    "total_edges_read": total_records_read,
                    "valid_edges": valid_count,
                    "skipped_edges": skipped_count,
                    "duplicate_edges": duplicate_count,
                    "relationship_type": self.relationship_type,
                    "delimiter": delimiter if delimiter else "whitespace"
                },
                "filters": {
                    "limit": limit,
                },
                "is_final_chunk": is_final
            },
            "data": data
        }
