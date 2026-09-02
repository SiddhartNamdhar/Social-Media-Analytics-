class SocialMediaIntelligenceError(Exception):
    """Base exception for all social media intelligence errors."""
    pass

class ConfigurationError(SocialMediaIntelligenceError):
    """Raised when there is a configuration issue."""
    pass

class TelegramConnectionError(SocialMediaIntelligenceError):
    """Raised when failing to connect to Telegram."""
    pass

class TelegramCollectionError(SocialMediaIntelligenceError):
    """Raised when there is an error during collection."""
    pass

class TelegramChannelNotFoundError(SocialMediaIntelligenceError):
    """Raised when a specified channel is not found or not accessible."""
    pass

class NormalizationError(SocialMediaIntelligenceError):
    """Raised when an error occurs during data normalization."""
    pass

class StorageError(SocialMediaIntelligenceError):
    """Raised when an error occurs during data storage."""
    pass
