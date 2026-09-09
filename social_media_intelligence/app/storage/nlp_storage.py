import json
import os
from typing import List, Dict, Any
from ..schemas.nlp_preprocessed_post import NLPPreprocessedPost
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

class NLPStorage:
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.base_dir = os.path.join(settings.DATA_DIRECTORY, "processed", "nlp")
        self.dir_path = os.path.join(self.base_dir, self.batch_id)
        self.file_path = os.path.join(self.dir_path, "nlp_posts.jsonl")

    def save_chunk(self, posts: List[NLPPreprocessedPost]) -> str:
        """Save a chunk of NLP preprocessed posts to JSONL file incrementally."""
        if not posts:
            return ""

        try:
            os.makedirs(self.dir_path, exist_ok=True)
            with open(self.file_path, 'a', encoding='utf-8') as f:
                for post in posts:
                    f.write(post.model_dump_json(exclude_none=False) + '\n')
            return self.file_path
        except Exception as e:
            raise StorageError(f"Failed to save NLP preprocessed data: {str(e)}")

    def validate_and_truncate_checkpoint(self) -> (int, Dict[str, Any]):
        """
        Validates the existing NLP output file.
        Returns (valid_record_count, last_valid_record_dict).
        If the file has a partial final write due to an interruption, it is truncated.
        Returns (0, None) if the file doesn't exist or is completely empty.
        """
        if not os.path.exists(self.file_path):
            return 0, None

        valid_count = 0
        last_valid_record = None
        valid_bytes = 0

        with open(self.file_path, 'r+b') as f:
            while True:
                last_offset = f.tell()
                line = f.readline()
                if not line:
                    break
                
                try:
                    # Try parsing as JSON to ensure completeness
                    line_str = line.decode('utf-8')
                    if not line_str.strip():
                        continue
                        
                    record = json.loads(line_str)
                    valid_count += 1
                    last_valid_record = record
                    valid_bytes = f.tell()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Found an incomplete or corrupt line, truncate here
                    print(f"Warning: Corrupt or partial JSONL record found at line {valid_count + 1}. Truncating file.")
                    break
            
            # Truncate the file to the last complete valid byte
            f.truncate(valid_bytes)

        return valid_count, last_valid_record
