import os
import json
import logging
import re
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

import ftfy
import emoji
from langdetect import detect_langs, LangDetectException

from ..schemas.unified_post import UnifiedPost
from ..schemas.nlp_preprocessed_post import NLPPreprocessedPost, NLPStatus
from ..storage.nlp_storage import NLPStorage
from ..utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

PREPROCESSING_VERSION = "1.0.0"

# Global worker state for multiprocessing
_worker_service = None

def _worker_init():
    """Initialize the NLPPreprocessingService once per worker process."""
    global _worker_service
    _worker_service = NLPPreprocessingService(chunk_size=0) # chunk size not used in worker

def _process_chunk(chunk_lines: List[str]) -> List[Dict[str, Any]]:
    """Process a chunk of JSONL strings into dictionaries of NLPPreprocessedPosts."""
    results = []
    try:
        for line in chunk_lines:
            if not line.strip():
                continue
            try:
                post = UnifiedPost.model_validate_json(line)
                nlp_post = _worker_service.process_record(post)
                results.append(nlp_post.model_dump(exclude_none=False))
            except Exception as e:
                pass
        return results
    except Exception as exc:
        print(f"CRITICAL WORKER ERROR: {exc}")
        raise

class NLPPreprocessingService:
    def __init__(self, chunk_size: int = 10000):
        self.chunk_size = chunk_size
        
        # Regex for repeated punctuation (more than 3 times)
        self.re_punct = re.compile(r'([!?.,;:])\1{3,}')
        # Regex for repeated characters (more than 3 times) - simplistic approach
        self.re_chars = re.compile(r'([a-zA-Z])\1{3,}')

    def _normalize_text(self, text: str) -> str:
        """Apply ftfy and basic whitespace normalization."""
        fixed = ftfy.fix_text(text)
        fixed = re.sub(r'\s+', ' ', fixed).strip()
        return fixed

    def _create_model_text(self, normalized_text: str, urls: List[str], mentions: List[str]) -> str:
        """Create model_text by replacing URLs, mentions, capping punctuation, and demojizing."""
        model_text = normalized_text
        
        for url in sorted(urls, key=len, reverse=True):
            if url:
                model_text = model_text.replace(url, "<URL>")
                
        for mention in sorted(mentions, key=len, reverse=True):
            if mention:
                target_with_at = mention if mention.startswith('@') else f"@{mention}"
                if target_with_at in model_text:
                    model_text = model_text.replace(target_with_at, "<USER>")
                elif mention in model_text:
                    model_text = model_text.replace(mention, "<USER>")

        model_text = emoji.demojize(model_text)

        model_text = self.re_punct.sub(r'\1\1\1', model_text)
        model_text = self.re_chars.sub(r'\1\1\1', model_text)
        
        return model_text

    def _extract_emojis(self, text: str) -> List[str]:
        """Extract unique Unicode emojis from text."""
        extracted = [d['emoji'] for d in emoji.emoji_list(text)]
        return list(dict.fromkeys(extracted))

    def _detect_language(self, text: str) -> tuple[str, bool, Optional[float]]:
        if len(text.strip()) < 10 or len(text.split()) < 3:
            return "unknown", True, None
            
        try:
            langs = detect_langs(text)
            if langs:
                best_match = langs[0]
                return best_match.lang, True, float(best_match.prob)
        except LangDetectException:
            pass
            
        return "unknown", True, None

    def _determine_status(self, model_text: str) -> NLPStatus:
        stripped = model_text.strip()
        
        if not stripped:
            return NLPStatus.UNUSABLE_EMPTY
            
        if not model_text.replace("<URL>", "").strip():
            return NLPStatus.UNUSABLE_URL_ONLY
            
        if not model_text.replace("<USER>", "").strip():
            return NLPStatus.UNUSABLE_MENTION_ONLY
            
        remaining = model_text.replace("<URL>", "").replace("<USER>", "").strip()
        if len(remaining) < 5:
            return NLPStatus.PARTIALLY_USABLE
            
        return NLPStatus.USABLE

    def process_record(self, post: UnifiedPost) -> NLPPreprocessedPost:
        start_time = datetime.now()
        error_msg = None
        
        original_text = post.content.text or ""
        urls = post.content.urls or []
        mentions = post.content.mentions or []
        hashtags = post.content.hashtags or []
        
        try:
            normalized_text = self._normalize_text(original_text)
            model_text = self._create_model_text(normalized_text, urls, mentions)
            emojis_list = self._extract_emojis(normalized_text)
            
            language_detected = False
            language_detection_probability = None
            if post.content.language and post.content.language.lower() not in ["und", "undefined", "unknown"]:
                language = post.content.language
            else:
                language, language_detected, language_detection_probability = self._detect_language(normalized_text)
                
            status = self._determine_status(model_text)
            
        except Exception as e:
            logger.error(f"Error processing record {post.record_id}: {str(e)}")
            normalized_text = original_text
            model_text = original_text
            emojis_list = []
            language = "unknown"
            language_detected = False
            language_detection_probability = None
            status = NLPStatus.UNUSABLE_ERROR
            error_msg = str(e)

        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        metadata = {
            "processed_at": get_utc_now().isoformat(),
            "processing_time_ms": round(processing_time_ms, 2),
            "char_count_original": len(original_text),
            "char_count_model": len(model_text)
        }
        if error_msg:
            metadata["error"] = error_msg

        return NLPPreprocessedPost(
            record_id=post.record_id,
            platform=post.platform,
            post_id=post.post_id,
            timestamp=post.timestamp,
            source_reference=post.raw_reference,
            original_text=original_text,
            normalized_text=normalized_text,
            model_text=model_text,
            urls=urls,
            mentions=mentions,
            hashtags=hashtags,
            emojis=emojis_list,
            language=language,
            language_detected=language_detected,
            language_detection_probability=language_detection_probability,
            status=status,
            preprocessing_version=PREPROCESSING_VERSION,
            processing_metadata=metadata
        )

    def process_timeline(self, input_path: str, batch_id: str, skip_lines: int = 0, workers: int = 8) -> Dict[str, Any]:
        stats = {
            "total_records_read": 0,
            "processed_successfully": 0,
            "status_usable": 0,
            "status_partially_usable": 0,
            "status_unusable_empty": 0,
            "status_unusable_url_only": 0,
            "status_unusable_mention_only": 0,
            "status_unusable_error": 0,
            "records_by_language": {},
            "output_paths": []
        }

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Timeline file not found: {input_path}")

        storage = NLPStorage(batch_id=batch_id)
        
        # 1. Automatic Checkpoint Detection and Validation
        valid_count, last_valid_record = storage.validate_and_truncate_checkpoint()
        
        if valid_count > 0:
            if skip_lines > 0 and skip_lines != valid_count:
                raise ValueError(f"Requested --skip-lines {skip_lines} does not match actual existing valid records {valid_count}.")
            print(f"Resuming safely from checkpoint at {valid_count} records.")
        elif skip_lines > 0:
            raise ValueError(f"--skip-lines {skip_lines} specified, but no existing valid checkpoint was found.")
            
        actual_skip_lines = valid_count

        # 2. Skip lines in input and validate deterministic identity of the final skipped line
        f = open(input_path, 'r', encoding='utf-8')
        for i in range(actual_skip_lines):
            line = f.readline()
            if not line:
                f.close()
                raise ValueError("Input timeline has fewer lines than the checkpoint count.")
                
            if i == actual_skip_lines - 1:
                # This is the last skipped record. It MUST match the last valid output record.
                input_post = json.loads(line)
                in_platform = input_post.get("platform")
                in_post_id = input_post.get("post_id")
                out_platform = last_valid_record.get("platform")
                out_post_id = last_valid_record.get("post_id")
                
                if in_platform != out_platform or in_post_id != out_post_id:
                    f.close()
                    raise ValueError(f"FATAL RESUME MISMATCH at record {actual_skip_lines}.\n"
                                     f"Timeline has: platform={in_platform}, post_id={in_post_id}\n"
                                     f"Output has:   platform={out_platform}, post_id={out_post_id}\n"
                                     f"Safe resume is impossible. Please delete the output batch and restart.")
                print(f"Checkpoint match SUCCESS: (platform={in_platform}, post_id={in_post_id}) at record {actual_skip_lines}.")

        stats["total_records_read"] = actual_skip_lines
        stats["processed_successfully"] = actual_skip_lines
        # We don't historically load past stats into memory, just start tracking new ones

        # 3. Multiprocessing execution with bounding
        print(f"Starting ProcessPoolExecutor with {workers} workers.")
        executor = ProcessPoolExecutor(max_workers=workers, initializer=_worker_init)
        
        max_futures = workers * 2
        futures_map = {}  # seq_id -> future
        next_seq_to_yield = 0
        next_seq_to_submit = 0
        
        chunk = []
        
        def flush_completed(block=False):
            """Writes completed sequential chunks to disk."""
            nonlocal next_seq_to_yield
            while next_seq_to_yield in futures_map:
                future = futures_map[next_seq_to_yield]
                if block or future.done():
                    try:
                        result_dicts = future.result()
                        if result_dicts:
                            posts = [NLPPreprocessedPost.model_validate(d) for d in result_dicts]
                            output_path = storage.save_chunk(posts)
                            if output_path and output_path not in stats["output_paths"]:
                                stats["output_paths"].append(output_path)
                                
                            for post in posts:
                                stats["processed_successfully"] += 1
                                status_key = f"status_{post.status.value}"
                                stats[status_key] = stats.get(status_key, 0) + 1
                                lang = post.language
                                stats["records_by_language"][lang] = stats["records_by_language"].get(lang, 0) + 1
                                if post.status == NLPStatus.UNUSABLE_ERROR:
                                    stats["status_unusable_error"] += 1
                            print(f"Flushed batch {next_seq_to_yield}. Total processed: {stats['processed_successfully']}")
                    except Exception as exc:
                        logger.error(f"Batch {next_seq_to_yield} raised an exception: {exc}")
                        raise
                        
                    del futures_map[next_seq_to_yield]
                    next_seq_to_yield += 1
                else:
                    break

        try:
            for line in f:
                chunk.append(line)
                stats["total_records_read"] += 1
                
                if len(chunk) >= self.chunk_size:
                    # If we reached max bounded futures, block and flush the oldest one
                    if len(futures_map) >= max_futures:
                        flush_completed(block=True)
                        
                    future = executor.submit(_process_chunk, chunk)
                    futures_map[next_seq_to_submit] = future
                    next_seq_to_submit += 1
                    chunk = []
                    
                    flush_completed(block=False)
                    
            if chunk:
                if len(futures_map) >= max_futures:
                    flush_completed(block=True)
                future = executor.submit(_process_chunk, chunk)
                futures_map[next_seq_to_submit] = future
                next_seq_to_submit += 1
                
            # Wait for all remaining to finish and flush
            while futures_map:
                flush_completed(block=True)
                
        finally:
            f.close()
            executor.shutdown(wait=True)

        return stats
