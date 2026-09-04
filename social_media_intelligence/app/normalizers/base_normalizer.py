from abc import ABC, abstractmethod
from typing import Any, Dict, TypeVar, Generic

T = TypeVar('T')

class BaseNormalizer(ABC, Generic[T]):
    """Abstract base class for all normalizers."""
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any], raw_reference: Dict[str, str], collection_metadata: Dict[str, Any]) -> T:
        """Convert raw platform-specific data into a unified schema object."""
        pass
