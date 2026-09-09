import os
import json
import uuid
import heapq
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from tempfile import NamedTemporaryFile

from ..schemas.unified_post import UnifiedPost
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

logger = logging.getLogger(__name__)

class UnifiedTimelineService:
    """Service to combine normalized UnifiedPost JSONL files into a single, sorted, deduplicated timeline."""

    def __init__(self):
        self.base_output_dir = os.path.join(settings.DATA_DIRECTORY, "processed", "unified")

    def _discover_jsonl_files(self, input_paths: List[str]) -> List[str]:
        """Recursively discover all .jsonl files from a list of paths."""
        jsonl_files = []
        for path_str in input_paths:
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"Input path does not exist: {path}")
                continue
                
            if path.is_file() and path.suffix == '.jsonl':
                jsonl_files.append(str(path))
            elif path.is_dir():
                for p in path.rglob('*.jsonl'):
                    if p.is_file():
                        jsonl_files.append(str(p))
        return jsonl_files

    def build_timeline(
        self, 
        input_paths: List[str], 
        batch_id: Optional[str] = None, 
        chunk_size: int = 100000
    ) -> Dict[str, Any]:
        """
        Build a unified timeline from a list of input paths containing normalized JSONL files.
        Uses an external merge-sort to handle large datasets efficiently.
        """
        batch_id = batch_id or str(uuid.uuid4())[:8]
        
        stats = {
            "total_records_read": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "duplicate_records": 0,
            "final_timeline_records": 0,
            "records_by_platform": {},
            "records_with_valid_timestamp": 0,
            "records_without_valid_timestamp": 0,
            "output_path": None
        }

        # 1. Discover files
        files_to_process = self._discover_jsonl_files(input_paths)
        if not files_to_process:
            logger.warning("No .jsonl files found in the provided input paths.")
            return stats

        temp_chunk_files = []
        current_chunk = []

        def flush_chunk(chunk_data: List[UnifiedPost]):
            if not chunk_data:
                return
            # Sort by timestamp (chronological)
            chunk_data.sort(key=lambda p: p.timestamp)
            
            temp_file = NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8')
            for post in chunk_data:
                temp_file.write(post.model_dump_json(exclude_none=False) + '\n')
            temp_file.close()
            temp_chunk_files.append(temp_file.name)

        # 2. Chunking phase
        for file_path in files_to_process:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue
                            
                        stats["total_records_read"] += 1
                        
                        try:
                            # Strict validation: Only valid UnifiedPost records pass
                            post = UnifiedPost.model_validate_json(line)
                            
                            # Timestamps are strictly required and parsed by Pydantic
                            # If it parses successfully, it's a valid timestamp.
                            # If it's missing or invalid, ValidationError is raised and caught.
                            stats["valid_records"] += 1
                            stats["records_with_valid_timestamp"] += 1
                            
                            current_chunk.append(post)
                            
                            if len(current_chunk) >= chunk_size:
                                flush_chunk(current_chunk)
                                current_chunk.clear()
                                
                        except Exception as e:
                            # e.g., missing timestamp, invalid schema, not a UnifiedPost
                            stats["invalid_records"] += 1
                            stats["records_without_valid_timestamp"] += 1
                            if stats["invalid_records"] <= 10:  # Avoid log spam
                                logger.warning(f"Invalid record in {file_path}:{line_num} - {str(e)}")
                            
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")

        # Flush the last chunk
        if current_chunk:
            flush_chunk(current_chunk)
            current_chunk.clear()

        # 3. Output paths
        now = get_utc_now()
        date_str = now.strftime("%Y-%m-%d")
        
        output_dir = os.path.join(self.base_output_dir, date_str, batch_id)
        os.makedirs(output_dir, exist_ok=True)
        final_output_path = os.path.join(output_dir, "timeline.jsonl")

        # 4. Merge Phase
        seen_ids = set()
        
        # We need to yield (timestamp, platform, post_id, line_json) from each file
        # We parse the file line by line again, but these are known-valid from the chunking phase
        def read_chunk(filepath: str):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    # Minimal parsing to get the key and dedup tuple
                    parsed = json.loads(line)
                    # We can rely on fields being present because it was already validated
                    yield (parsed['timestamp'], parsed['platform'], parsed['post_id'], line)

        generators = [read_chunk(f) for f in temp_chunk_files]
        
        try:
            with open(final_output_path, 'w', encoding='utf-8') as f_out:
                # heapq.merge will sort based on the entire tuple, which starts with timestamp
                for record in heapq.merge(*generators):
                    timestamp_str, platform, post_id, json_line = record
                    
                    dedup_key = (platform, post_id)
                    if dedup_key in seen_ids:
                        stats["duplicate_records"] += 1
                        continue
                        
                    seen_ids.add(dedup_key)
                    
                    f_out.write(json_line)
                    
                    stats["final_timeline_records"] += 1
                    stats["records_by_platform"][platform] = stats["records_by_platform"].get(platform, 0) + 1
                    
            stats["output_path"] = final_output_path
            
        finally:
            # 5. Cleanup
            for temp_f in temp_chunk_files:
                try:
                    os.remove(temp_f)
                except Exception as e:
                    logger.error(f"Failed to delete temp chunk file {temp_f}: {e}")

        return stats
