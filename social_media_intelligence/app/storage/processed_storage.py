import json
import os
from typing import List, Set, Dict, Any
from ..schemas.unified_post import UnifiedPost
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

class ProcessedStorage:
    def __init__(self, platform: str):
        self.platform = platform
        self.base_dir = os.path.join(settings.DATA_DIRECTORY, "processed", platform)
        self._existing_ids: Optional[Set[str]] = None
        self._current_file: Optional[str] = None
        
    def save(self, posts: List[UnifiedPost]) -> str:
        """Save normalized posts to JSONL file with duplicate handling."""
        try:
            if not posts:
                return ""
                
            now = get_utc_now()
            date_str = now.strftime("%Y-%m-%d")
            
            dir_path = os.path.join(self.base_dir, date_str)
            os.makedirs(dir_path, exist_ok=True)
            
            file_path = os.path.join(dir_path, "posts.jsonl")
            
            # Simple duplicate check for this implementation
            if self._existing_ids is None or self._current_file != file_path:
                self._existing_ids = set()
                self._current_file = file_path
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            try:
                                item = json.loads(line)
                                self._existing_ids.add(item.get("post_id"))
                            except json.JSONDecodeError:
                                pass
            
            added_count = 0
            with open(file_path, 'a', encoding='utf-8') as f:
                for post in posts:
                    if post.post_id not in self._existing_ids:
                        f.write(post.model_dump_json(exclude_none=False) + '\n')
                        self._existing_ids.add(post.post_id)
                        added_count += 1
                        
            return file_path
        except Exception as e:
            raise StorageError(f"Failed to save processed data: {str(e)}")

    def save_and_report(self, posts: List[UnifiedPost]) -> Dict[str, Any]:
        """Save normalized posts and return detailed counts."""
        if not posts:
            return {"file_path": None, "added_count": 0, "duplicate_count": 0}
            
        try:
            now = get_utc_now()
            date_str = now.strftime("%Y-%m-%d")
            dir_path = os.path.join(self.base_dir, date_str)
            os.makedirs(dir_path, exist_ok=True)
            
            file_path = os.path.join(dir_path, "posts.jsonl")
            
            if self._existing_ids is None or self._current_file != file_path:
                self._existing_ids = set()
                self._current_file = file_path
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if not line.strip():
                                continue
                            try:
                                item = json.loads(line)
                                self._existing_ids.add(item.get("post_id"))
                            except json.JSONDecodeError:
                                pass
            
            added_count = 0
            duplicate_count = 0
            
            with open(file_path, 'a', encoding='utf-8') as f:
                for post in posts:
                    if post.post_id not in self._existing_ids:
                        f.write(post.model_dump_json(exclude_none=False) + '\n')
                        self._existing_ids.add(post.post_id)
                        added_count += 1
                    else:
                        duplicate_count += 1
                        
            return {
                "file_path": file_path,
                "added_count": added_count,
                "duplicate_count": duplicate_count
            }
        except Exception as e:
            raise StorageError(f"Failed to save processed data: {str(e)}")
