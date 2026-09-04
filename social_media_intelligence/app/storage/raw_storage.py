import json
import os
from datetime import datetime
from typing import Dict, Any, List
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

class RawStorage:
    def __init__(self, platform: str):
        self.platform = platform
        self.base_dir = os.path.join(settings.DATA_DIRECTORY, "raw", platform)
        
    def save(self, data: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        """Save raw data to JSON file."""
        try:
            now = get_utc_now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%Y%m%d_%H%M%S")
            batch_id = metadata.get("source", {}).get("batch_id", time_str)
            
            dir_path = os.path.join(self.base_dir, date_str, batch_id)
            os.makedirs(dir_path, exist_ok=True)
            
            file_name = f"collection_{time_str}.json"
            file_path = os.path.join(dir_path, file_name)
            
            output = {
                "collection_metadata": metadata,
                "data": data
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=4)
                
            return file_path
        except Exception as e:
            raise StorageError(f"Failed to save raw data: {str(e)}")

    def save_stream(self, data_chunk: List[Dict[str, Any]], metadata: Dict[str, Any], batch_id: str, is_first_chunk: bool) -> str:
        """Save streaming raw data incrementally to a JSONL file."""
        try:
            now = get_utc_now()
            date_str = now.strftime("%Y-%m-%d")
            
            dir_path = os.path.join(self.base_dir, date_str, batch_id)
            os.makedirs(dir_path, exist_ok=True)
            
            metadata_file = os.path.join(dir_path, f"collection_{batch_id}_metadata.json")
            data_file = os.path.join(dir_path, f"collection_{batch_id}.jsonl")
            
            if data_chunk:
                with open(data_file, 'a', encoding='utf-8') as f:
                    for record in data_chunk:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        
            # Only save/overwrite metadata if it is the final chunk, or if it is the only chunk and it is marked final.
            # But wait, what if it fails mid-stream? It's better to save it at the end to avoid incomplete totals.
            # If the user stops early, the last received chunk could write it.
            if metadata.get("is_final_chunk"):
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=4)
                        
            return data_file
        except Exception as e:
            raise StorageError(f"Failed to save raw streaming data: {str(e)}")
