import re
from typing import List

class EntityExtractor:
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        if not text:
            return []
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags

    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        if not text:
            return []
        mentions = re.findall(r'@(\w+)', text)
        return mentions

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        if not text:
            return []
        urls = re.findall(r'https?://[^\s]+', text)
        return urls
