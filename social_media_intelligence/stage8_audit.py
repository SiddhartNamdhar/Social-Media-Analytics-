import os
import json
from app.config import settings

def main():
    print("==================================================")
    print("STAGE 8: POST-PRODUCTION AUDIT")
    print("==================================================")
    
    nlp_path = os.path.join(settings.DATA_DIRECTORY, "processed", "nlp", "full_multiplatform_nlp_2026_09_08", "nlp_posts.jsonl")
    sentiment_path = os.path.join(settings.DATA_DIRECTORY, "processed", "sentiment", "full_multiplatform_sentiment_2026_09_08", "sentiment_results.jsonl")
    
    print("1. Loading required NLP identities (status == USABLE)...")
    expected_identities = []
    platform_counts = {}
    with open(nlp_path, 'r', encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            if rec.get('status') == 'usable':
                plat = rec.get('platform')
                pid = rec.get('post_id')
                ident = f"{plat}|{pid}"
                expected_identities.append(ident)
                platform_counts[plat] = platform_counts.get(plat, 0) + 1
                
    expected_count = len(expected_identities)
    print(f"Expected USABLE count: {expected_count}")
    
    print("2. Validating sentiment results...")
    result_identities = []
    out_platform_counts = {}
    errors = {
        "missing_fields": 0,
        "invalid_label": 0,
        "invalid_probability_bounds": 0,
        "invalid_probability_sum": 0,
        "invalid_metadata": 0,
    }
    
    with open(sentiment_path, 'r', encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            plat = rec.get('platform')
            pid = rec.get('post_id')
            ident = f"{plat}|{pid}"
            result_identities.append(ident)
            out_platform_counts[plat] = out_platform_counts.get(plat, 0) + 1
            
            label = rec.get('sentiment_label')
            if label not in ['negative', 'neutral', 'positive']:
                errors['invalid_label'] += 1
                
            p1 = rec.get('probability_negative', -1)
            p2 = rec.get('probability_neutral', -1)
            p3 = rec.get('probability_positive', -1)
            
            if not (0 <= p1 <= 1) or not (0 <= p2 <= 1) or not (0 <= p3 <= 1):
                errors['invalid_probability_bounds'] += 1
                
            if not (0.99 < (p1 + p2 + p3) < 1.01):
                errors['invalid_probability_sum'] += 1
                
            if rec.get('model_id') != "cardiffnlp/twitter-xlm-roberta-base-sentiment" or rec.get('precision') != "fp16":
                errors['invalid_metadata'] += 1
                
    result_count = len(result_identities)
    print(f"Actual Sentiment count: {result_count}")
    
    print("3. Checking for duplicates, missing, and order mismatches...")
    unique_results = set(result_identities)
    duplicates = result_count - len(unique_results)
    
    expected_set = set(expected_identities)
    missing = len(expected_set - unique_results)
    extra = len(unique_results - expected_set)
    
    order_mismatches = 0
    if duplicates == 0 and missing == 0 and extra == 0:
        for i in range(expected_count):
            if expected_identities[i] != result_identities[i]:
                order_mismatches += 1
                
    print("\n--- AUDIT RESULTS ---")
    print(f"Duplicates       : {duplicates}")
    print(f"Missing          : {missing}")
    print(f"Extra            : {extra}")
    print(f"Order Mismatches : {order_mismatches}")
    print("\n--- SCHEMA / CONTENT ERRORS ---")
    for k, v in errors.items():
        print(f"{k:<30}: {v}")
        
    print("\n--- PLATFORM COUNTS MATCH ---")
    all_match = True
    for plat in platform_counts:
        in_c = platform_counts[plat]
        out_c = out_platform_counts.get(plat, 0)
        match_str = "[PASS]" if in_c == out_c else "[FAIL]"
        if in_c != out_c: all_match = False
        print(f"{plat:<10}: In={in_c:<8} Out={out_c:<8} {match_str}")
        
    overall_pass = (
        expected_count == 25438916 and
        result_count == 25438916 and
        duplicates == 0 and
        missing == 0 and
        extra == 0 and
        order_mismatches == 0 and
        sum(errors.values()) == 0 and
        all_match
    )
    
    print("\n==================================================")
    if overall_pass:
        print("[PASS] FULL AUDIT PASSED: 100% Deterministic & Safe")
    else:
        print("[FAIL] AUDIT FAILED")
    print("==================================================")

if __name__ == "__main__":
    main()
