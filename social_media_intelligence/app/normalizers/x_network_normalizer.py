import logging
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .base_normalizer import BaseNormalizer
from ..schemas.unified_edge import UnifiedEdge, RelationshipType
from ..schemas.unified_post import RawReference
from ..utils.datetime_utils import ensure_utc
from ..exceptions import NormalizationError
from .x_normalizer import TWITTER_DATE_FORMATS

logger = logging.getLogger(__name__)

class XNetworkNormalizer(BaseNormalizer[UnifiedEdge]):
    """Normalize raw network edges into UnifiedEdge objects."""

    def normalize(
        self,
        raw_data: Dict[str, Any],
        raw_reference: Dict[str, str],
        collection_metadata: Optional[Dict[str, Any]] = None
    ) -> UnifiedEdge:
        try:
            collection_metadata = collection_metadata or {}
            source_info = collection_metadata.get('source', {})
            
            source_user = str(raw_data.get('source', ''))
            target_user = str(raw_data.get('target', ''))
            rel_type_str = str(raw_data.get('relationship_type', 'UNKNOWN')).upper()
            
            if not source_user or not target_user:
                raise NormalizationError("Missing source or target user ID")
                
            try:
                rel_type = RelationshipType(rel_type_str)
            except ValueError:
                rel_type = RelationshipType.UNKNOWN
                
            timestamp = self._parse_timestamp(raw_data.get('timestamp'))
            
            weight = 1.0
            weight_val = raw_data.get('weight')
            if weight_val is not None:
                try:
                    weight = float(weight_val)
                except ValueError:
                    pass
                    
            dataset_name = source_info.get('dataset_file')
            collected_at_str = collection_metadata.get('collected_at')
            try:
                collected_at = datetime.fromisoformat(collected_at_str) if collected_at_str else datetime.now(timezone.utc)
            except Exception:
                collected_at = datetime.now(timezone.utc)
                
            # Deterministic Edge ID
            ts_str = timestamp.isoformat() if timestamp else ""
            hash_input = f"x|{source_user}|{target_user}|{rel_type.value}|{ts_str}"
            edge_id = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
            
            raw_ref_obj = RawReference(
                platform=raw_reference.get('platform', 'x_network'),
                raw_file=raw_reference.get('raw_file', '')
            )
            
            return UnifiedEdge(
                edge_id=edge_id,
                platform="x",
                source_user_id=source_user,
                target_user_id=target_user,
                relationship_type=rel_type,
                timestamp=timestamp,
                weight=weight,
                dataset_name=dataset_name,
                collected_at=collected_at,
                raw_reference=raw_ref_obj
            )
            
        except Exception as e:
            raise NormalizationError(f"Failed to normalize X network data: {str(e)}")

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if value is None:
            return None
            
        value_str = str(value).strip()
        if not value_str or value_str.lower() in ('none', 'nan', 'nat', ''):
            return None
            
        try:
            ts = float(value_str)
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
            
        try:
            dt = datetime.fromisoformat(value_str.replace('Z', '+00:00'))
            return ensure_utc(dt)
        except (ValueError, AttributeError):
            pass
            
        for fmt in TWITTER_DATE_FORMATS:
            try:
                dt = datetime.strptime(value_str, fmt)
                return ensure_utc(dt)
            except ValueError:
                continue
                
        # For network edges, timestamp is optional. If invalid, we return None rather than fail.
        # But wait, in XDatasetCollector we raised an error to avoid data corruption.
        # For network, it's safer to return None if it is unparseable and let it be optional.
        return None
