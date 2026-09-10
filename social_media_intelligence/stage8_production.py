import os
import json
import time
from app.services.sentiment_analysis_service import SentimentAnalysisService
from app.config import settings

def main():
    print("==================================================")
    print("STAGE 8: PRODUCTION SENTIMENT INFERENCE")
    print("==================================================")
    
    input_path = os.path.join(settings.DATA_DIRECTORY, "processed", "nlp", "full_multiplatform_nlp_2026_09_08", "nlp_posts.jsonl")
    if not os.path.exists(input_path):
        print(f"Error: Could not find authoritative NLP JSONL at {input_path}")
        return
        
    batch_id = "full_multiplatform_sentiment_2026_09_08"
    
    print(f"Starting production sentiment job for batch: {batch_id}")
    start_time = time.time()
    
    try:
        service = SentimentAnalysisService(batch_id=batch_id, batch_size=32)
        stats = service.process_dataset(input_path)
    except Exception as e:
        print(f"\n[FATAL ERROR] Production job failed: {e}")
        return
        
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n==================================================")
    print("PRODUCTION JOB COMPLETE")
    print("==================================================")
    print(f"Total time: {elapsed/3600:.2f} hours")
    print(f"Total usable records processed: {stats['total_usable_processed']}")
    print(f"Total usable expected: {stats['total_usable_input']}")
    
    if stats['total_usable_processed'] == stats['total_usable_input']:
        print("[PASS] Processed exactly all expected USABLE records.")
    else:
        print("[FAIL] WARNING: Processed count does not match expected input.")
        
    print(f"Errors encountered: {stats['errors']}")
    print(f"Batches processed: {stats['batches_processed']}")
    
if __name__ == "__main__":
    main()
