import os
import json
import logging
import torch
import time
import psutil
from datetime import datetime
import transformers
from typing import Dict, Any, List

from ..schemas.sentiment_result import SentimentResult
from ..storage.sentiment_storage import SentimentStorage
from ..utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

class SentimentAnalysisService:
    def __init__(self, batch_id: str, batch_size: int = 32):
        self.batch_id = batch_id
        self.batch_size = batch_size
        self.model_id = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
        self.revision = "f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8"
        self.precision = "fp16"
        self.storage = SentimentStorage(batch_id=batch_id)
        
        print("Loading tokenizer and model...")
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
        self.model = transformers.AutoModelForSequenceClassification.from_pretrained(self.model_id, revision=self.revision)
        self.model = self.model.eval().to('cuda:0')
        print("Model loaded.")

    def process_dataset(self, input_path: str, max_records: int = None) -> Dict[str, Any]:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
            
        valid_count, last_valid_record = self.storage.validate_and_truncate_checkpoint()
        
        target_resume_platform = None
        target_resume_post_id = None
        if valid_count > 0:
            target_resume_platform = last_valid_record.get('platform')
            target_resume_post_id = last_valid_record.get('post_id')
            print(f"Resuming safely from checkpoint at {valid_count} records.")
            print(f"Target identity: ({target_resume_platform}, {target_resume_post_id})")

        stats = {
            "total_usable_processed": valid_count,
            "total_usable_input": 25438916,
            "errors": 0,
            "batches_processed": 0
        }
        
        f = open(input_path, 'r', encoding='utf-8')
        
        # Phase 1: Fast-forward to checkpoint
        if valid_count > 0:
            found_checkpoint = False
            for line in f:
                record = json.loads(line)
                if record.get('status') != 'usable':
                    continue
                if record.get('platform') == target_resume_platform and record.get('post_id') == target_resume_post_id:
                    found_checkpoint = True
                    break
            
            if not found_checkpoint:
                f.close()
                raise ValueError(f"FATAL RESUME MISMATCH: Checkpoint identity ({target_resume_platform}, {target_resume_post_id}) not found in USABLE records.")
            print("Checkpoint matched in input stream. Resuming...")

        # Phase 2: Streaming Inference
        batch_records = []
        batch_texts = []
        
        start_time = time.time()
        last_report_time = start_time
        records_since_report = 0
        
        try:
            for line in f:
                if max_records and (stats["total_usable_processed"] - valid_count) >= max_records:
                    break
                    
                record = json.loads(line)
                if record.get('status') != 'usable':
                    continue
                    
                batch_records.append(record)
                batch_texts.append(record.get('model_text', ''))
                
                if len(batch_records) == self.batch_size:
                    self._process_batch(batch_texts, batch_records)
                    stats["total_usable_processed"] += len(batch_records)
                    stats["batches_processed"] += 1
                    records_since_report += len(batch_records)
                    
                    batch_records = []
                    batch_texts = []
                    
                    if stats["total_usable_processed"] % 100000 < self.batch_size:
                        self._print_progress(stats, start_time, records_since_report, last_report_time)
                        last_report_time = time.time()
                        records_since_report = 0

            if batch_records:
                if max_records is None or (stats["total_usable_processed"] - valid_count) + len(batch_records) <= max_records:
                    self._process_batch(batch_texts, batch_records)
                    stats["total_usable_processed"] += len(batch_records)
                    stats["batches_processed"] += 1
                else:
                    needed = max_records - (stats["total_usable_processed"] - valid_count)
                    if needed > 0:
                        self._process_batch(batch_texts[:needed], batch_records[:needed])
                        stats["total_usable_processed"] += needed
                        stats["batches_processed"] += 1
                
        except Exception as e:
            logger.error(f"Fatal error during processing: {e}")
            stats["errors"] += 1
            raise
        finally:
            f.close()
            
        return stats

    def _process_batch(self, texts: List[str], records: List[Dict[str, Any]]):
        encoded = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        encoded = {k: v.to('cuda:0') for k, v in encoded.items()}
        
        with torch.inference_mode():
            with torch.autocast(device_type='cuda', dtype=torch.float16):
                outputs = self.model(**encoded)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1).cpu().tolist()
            
        results = []
        now = get_utc_now()
        for i, record in enumerate(records):
            p = probs[i]
            label_idx = p.index(max(p))
            label = ["negative", "neutral", "positive"][label_idx]
            
            res = SentimentResult(
                platform=record['platform'],
                post_id=record['post_id'],
                sentiment_label=label,
                probability_negative=p[0],
                probability_neutral=p[1],
                probability_positive=p[2],
                model_id=self.model_id,
                model_revision=self.revision,
                precision=self.precision,
                processed_at=now
            )
            results.append(res)
            
        self.storage.save_chunk(results)

    def _print_progress(self, stats, start_time, recs_since, last_time):
        now = time.time()
        elapsed = now - start_time
        total_recs = stats["total_usable_processed"]
        pct = (total_recs / stats["total_usable_input"]) * 100
        
        interval = now - last_time
        rec_sec = recs_since / interval if interval > 0 else 0
        rec_min = rec_sec * 60
        
        remaining_recs = stats["total_usable_input"] - total_recs
        est_rem_sec = remaining_recs / rec_sec if rec_sec > 0 else 0
        
        mem = psutil.Process(os.getpid()).memory_info().rss / (1024**2)
        vram = torch.cuda.memory_allocated() / (1024**2)
        
        print(f"[PROGRESS] {total_recs}/{stats['total_usable_input']} ({pct:.2f}%) "
              f"| {rec_sec:.1f} rec/s ({rec_min:.1f}/m) | Elapsed: {elapsed/3600:.2f}h "
              f"| ETA: {est_rem_sec/3600:.2f}h | SysRAM: {mem:.1f}MB | VRAM Alloc: {vram:.1f}MB")
