import json
import os
from typing import List, Dict, Any, Tuple, Optional
from ..schemas.sentiment_result import SentimentResult
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

class SentimentStorage:
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.base_dir = os.path.join(settings.DATA_DIRECTORY, "processed", "sentiment")
        self.dir_path = os.path.join(self.base_dir, self.batch_id)
        self.file_path = os.path.join(self.dir_path, "sentiment_results.jsonl")

    def save_chunk(self, results: List[SentimentResult]) -> str:
        if not results:
            return ""
        try:
            os.makedirs(self.dir_path, exist_ok=True)
            with open(self.file_path, 'a', encoding='utf-8') as f:
                for result in results:
                    f.write(result.model_dump_json() + '\n')
            return self.file_path
        except Exception as e:
            raise StorageError(f"Failed to save sentiment data: {str(e)}")

    def validate_and_truncate_checkpoint(self) -> Tuple[int, Optional[Dict[str, Any]]]:
        if not os.path.exists(self.file_path):
            return 0, None

        valid_count = 0
        last_valid_record = None
        valid_bytes = 0

        with open(self.file_path, 'r+b') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                
                try:
                    line_str = line.decode('utf-8')
                    if not line_str.strip():
                        continue
                        
                    record = json.loads(line_str)
                    valid_count += 1
                    last_valid_record = record
                    valid_bytes = f.tell()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    print(f"Warning: Corrupt partial JSONL record at line {valid_count + 1}. Truncating.")
                    break
            
            f.truncate(valid_bytes)

        return valid_count, last_valid_record
