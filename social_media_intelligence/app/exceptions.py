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

class XDatasetError(SocialMediaIntelligenceError):
    """Raised when there is an error during X dataset collection."""
    pass

class XDatasetFileNotFoundError(XDatasetError):
    """Raised when the specified X dataset file is not found."""
    pass

class XDatasetFormatError(XDatasetError):
    """Raised when the X dataset format is unsupported or malformed."""
    pass

class YouTubeError(SocialMediaIntelligenceError):
    """Base exception for YouTube related errors."""
    pass

class YouTubeConfigurationError(YouTubeError):
    """Raised when YouTube API configuration is invalid or missing."""
    pass

class YouTubeAPIError(YouTubeError):
    """Raised when the YouTube API returns an error."""
    pass

class YouTubeQuotaExceededError(YouTubeAPIError):
    """Raised when YouTube API quota is exceeded."""
    pass

class YouTubeVideoNotFoundError(YouTubeError):
    """Raised when a requested YouTube video is not found or is private."""
    pass

class YouTubeChannelNotFoundError(YouTubeError):
    """Raised when a requested YouTube channel is not found."""
    pass
