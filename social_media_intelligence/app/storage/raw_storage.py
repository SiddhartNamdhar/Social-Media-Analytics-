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
            
            dir_path = os.path.join(self.base_dir, date_str)
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
