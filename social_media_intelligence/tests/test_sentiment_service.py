import os
import json
import pytest
import tempfile
from app.services.sentiment_analysis_service import SentimentAnalysisService

@pytest.fixture
def mock_nlp_data():
    return [
        {"platform": "x", "post_id": "1", "status": "usable", "model_text": "Good day"},
        {"platform": "x", "post_id": "2", "status": "partially_usable", "model_text": "Bad"},
        {"platform": "x", "post_id": "3", "status": "usable", "model_text": "Neutral day"},
        {"platform": "x", "post_id": "4", "status": "unusable_empty", "model_text": ""},
        {"platform": "x", "post_id": "5", "status": "usable", "model_text": "Great day"},
    ]

def test_filtering_and_identity_preservation(mock_nlp_data):
    with tempfile.TemporaryDirectory() as td:
        input_path = os.path.join(td, "input.jsonl")
        with open(input_path, 'w', encoding='utf-8') as f:
            for r in mock_nlp_data:
                f.write(json.dumps(r) + '\n')
                
        import app.config as config
        original_data_dir = config.settings.DATA_DIRECTORY
        config.settings.DATA_DIRECTORY = td
        
        try:
            service = SentimentAnalysisService(batch_id="test_batch", batch_size=2)
            # Update usable count for test
            service.process_dataset(input_path)
            
            output_path = os.path.join(td, "processed", "sentiment", "test_batch", "sentiment_results.jsonl")
            assert os.path.exists(output_path)
            
            results = []
            with open(output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    results.append(json.loads(line))
                    
            assert len(results) == 3
            assert results[0]['post_id'] == "1"
            assert results[1]['post_id'] == "3"
            assert results[2]['post_id'] == "5"
            
            assert "sentiment_label" in results[0]
            assert "probability_negative" in results[0]
            assert results[0]['sentiment_label'] in ['negative', 'neutral', 'positive']
            
        finally:
            config.settings.DATA_DIRECTORY = original_data_dir

def test_resume_does_not_duplicate_records(mock_nlp_data):
    with tempfile.TemporaryDirectory() as td:
        input_path = os.path.join(td, "input.jsonl")
        with open(input_path, 'w', encoding='utf-8') as f:
            for r in mock_nlp_data:
                f.write(json.dumps(r) + '\n')
                
        import app.config as config
        original_data_dir = config.settings.DATA_DIRECTORY
        config.settings.DATA_DIRECTORY = td
        
        try:
            service = SentimentAnalysisService(batch_id="test_resume", batch_size=1)
            service.process_dataset(input_path, max_records=2)
            
            output_path = os.path.join(td, "processed", "sentiment", "test_resume", "sentiment_results.jsonl")
            
            # Restart
            service2 = SentimentAnalysisService(batch_id="test_resume", batch_size=1)
            service2.process_dataset(input_path)
            
            results = []
            with open(output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    results.append(json.loads(line))
                    
            assert len(results) == 3
            ids = [r['post_id'] for r in results]
            assert ids == ["1", "3", "5"]
            
        finally:
            config.settings.DATA_DIRECTORY = original_data_dir

def test_checkpoint_identity_mismatch_fails(mock_nlp_data):
    with tempfile.TemporaryDirectory() as td:
        input_path = os.path.join(td, "input.jsonl")
        with open(input_path, 'w', encoding='utf-8') as f:
            for r in mock_nlp_data:
                f.write(json.dumps(r) + '\n')
                
        import app.config as config
        original_data_dir = config.settings.DATA_DIRECTORY
        config.settings.DATA_DIRECTORY = td
        
        try:
            output_dir = os.path.join(td, "processed", "sentiment", "test_mismatch")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "sentiment_results.jsonl")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps({"platform": "x", "post_id": "999", "sentiment_label": "positive"}) + '\n')
                
            service = SentimentAnalysisService(batch_id="test_mismatch", batch_size=2)
            with pytest.raises(ValueError, match="FATAL RESUME MISMATCH"):
                service.process_dataset(input_path)
                
        finally:
            config.settings.DATA_DIRECTORY = original_data_dir
