import time
import psutil
from app.services.nlp_preprocessing_service import NLPPreprocessingService
from app.storage.nlp_storage import NLPStorage
import os
import shutil

def run_benchmark():
    timeline_path = r"data\processed\unified\2026-09-08\full_multiplatform_2026_09_08\timeline.jsonl"
    
    # We will read exactly 100k lines to a temp file so we don't process the whole 27M
    temp_timeline = r"data\processed\nlp\benchmark_timeline.jsonl"
    os.makedirs(os.path.dirname(temp_timeline), exist_ok=True)
    
    print("Creating 100k record benchmark timeline...")
    with open(timeline_path, 'r', encoding='utf-8') as fin, open(temp_timeline, 'w', encoding='utf-8') as fout:
        for _ in range(100000):
            line = fin.readline()
            if not line: break
            fout.write(line)
            
    workers_to_test = [1, 4, 8, 10]
    
    print("\nStarting NLP Multiprocessing Benchmark...")
    print(f"{'Workers':<10} | {'Time (s)':<10} | {'Rec/sec':<10} | {'Rec/min':<10}")
    print("-" * 50)
    
    for w in workers_to_test:
        batch_id = f"benchmark_nlp_w{w}"
        # Clean up any previous runs
        if os.path.exists(rf"data\processed\nlp\{batch_id}"):
            shutil.rmtree(rf"data\processed\nlp\{batch_id}")
            
        service = NLPPreprocessingService(chunk_size=10000)
        
        start_time = time.time()
        stats = service.process_timeline(input_path=temp_timeline, batch_id=batch_id, skip_lines=0, workers=w)
        elapsed = time.time() - start_time
        
        recs_per_sec = stats["processed_successfully"] / elapsed
        recs_per_min = recs_per_sec * 60
        
        print(f"{w:<10} | {elapsed:<10.2f} | {recs_per_sec:<10.2f} | {recs_per_min:<10.2f}")
        
    print("-" * 50)
    print("Benchmark complete.")

if __name__ == "__main__":
    run_benchmark()
