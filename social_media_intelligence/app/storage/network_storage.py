import json
import os
from typing import List, Set, Dict, Any
from ..schemas.unified_edge import UnifiedEdge
from ..utils.datetime_utils import get_utc_now
from ..config import settings
from ..exceptions import StorageError

class NetworkStorage:
    def __init__(self, platform: str):
        self.platform = platform
        self.base_dir = os.path.join(settings.DATA_DIRECTORY, "processed", f"{platform}_network")
        self._existing_ids: Optional[Set[str]] = None
        self._current_file: Optional[str] = None
        
    def save_and_report(self, edges: List[UnifiedEdge]) -> Dict[str, Any]:
        """Save normalized edges to JSONL file with duplicate handling based on edge_id."""
        if not edges:
            return {"file_path": None, "added_count": 0, "duplicate_count": 0}
            
        try:
            now = get_utc_now()
            date_str = now.strftime("%Y-%m-%d")
            
            dir_path = os.path.join(self.base_dir, date_str)
            os.makedirs(dir_path, exist_ok=True)
            
            file_path = os.path.join(dir_path, "edges.jsonl")
            
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
                                self._existing_ids.add(item.get("edge_id"))
                            except json.JSONDecodeError:
                                pass
            
            added_count = 0
            duplicate_count = 0
            
            with open(file_path, 'a', encoding='utf-8') as f:
                for edge in edges:
                    if edge.edge_id not in self._existing_ids:
                        f.write(edge.model_dump_json(exclude_none=False) + '\n')
                        self._existing_ids.add(edge.edge_id)
                        added_count += 1
                    else:
                        duplicate_count += 1
                        
            return {
                "file_path": file_path,
                "added_count": added_count,
                "duplicate_count": duplicate_count
            }
        except Exception as e:
            raise StorageError(f"Failed to save processed network data: {str(e)}")
