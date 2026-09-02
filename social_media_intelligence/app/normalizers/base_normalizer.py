from abc import ABC, abstractmethod
from typing import Any, Dict
from ..schemas.unified_post import UnifiedPost

class BaseNormalizer(ABC):
    """Abstract base class for all normalizers."""
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str]) -> UnifiedPost:
        """Convert raw platform-specific data into a UnifiedPost."""
        pass
