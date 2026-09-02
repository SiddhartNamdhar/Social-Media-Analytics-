from abc import ABC, abstractmethod

class BaseCollector(ABC):
    """Abstract base class for all data collectors."""
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection and authentication."""
        pass
        
    @abstractmethod
    async def collect(self, *args, **kwargs):
        """Perform data collection and return raw dictionaries."""
        pass
