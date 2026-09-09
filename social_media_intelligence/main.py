import asyncio
import json
# pyright: ignore[reportMissingImports]
from dotenv import load_dotenv

import argparse
from app.logging_config import setup_logging
from app.config import PROJECT_ROOT


async def test_telegram_collector():
    """Test the Telegram live data collector."""
    from app.services.telegram_collection_service import TelegramCollectionService
    
    service = TelegramCollectionService()

    print("--- Testing Telegram Data Collector ---")
    print("WARNING: Make sure you replace @telegram with a public channel you can legitimately access.")
    channel_to_scrape = "@Artificial_intelligence_in"

    try:
        is_connected = await service.collector.validate_connection()
        if not is_connected:
            print("Please check your .env file and authenticate via interactive CLI first!")
            return
            
        print(f"Connection OK. Collecting messages from {channel_to_scrape}...")
        
        result = await service.collect_and_process(
            channel=channel_to_scrape,
            limit=600,
            keywords=None
        )

        print("\nCollection Result:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
    finally:
        await service.collector.client.disconnect()


async def test_x_dataset_collector():
    """Test the X dataset collector with a local CSV file."""
    from app.services.x_collection_service import XCollectionService
    
    service = XCollectionService()
    
    # Path to sample dataset (relative to project root)
    dataset_path = str(PROJECT_ROOT / "datasets/x/posts/output.json")

    print("\n--- Testing X Dataset Collector ---")
    print(f"Dataset: {dataset_path}")
    print()

    try:
        result = await service.collect_and_process(
            dataset_path=dataset_path,
            limit = None,
            source_name="x_output"
        )

        print("\nCollection Summary:")
        print(f"  Platform:           {result['platform']}")
        print(f"  Dataset:            {result['dataset']}")
        print(f"  Records discovered: {result['total_records']}")
        print(f"  Records processed:  {result['processed_records']}")
        print(f"  Records skipped:    {result['skipped_records']}")
        print(f"  Duplicates:         {result['duplicate_records']}")
        print(f"  Raw output:         {result['raw_output_path']}")
        print(f"  Processed output:   {result['processed_output_path']}")

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

async def test_x_network_collector():
    """Test the X network edge collector with a local edgelist file."""
    from app.services.x_network_service import XNetworkService
    
    service = XNetworkService()
    
    # Path to sample dataset
    # Note: higgs-retweet_network.edgelist has columns: source target timestamp
    dataset_path = str(PROJECT_ROOT / "datasets/x/network/higgs-retweet_network.edgelist")

    print("\n--- Testing X Network Collector ---")
    print(f"Dataset: {dataset_path}")
    print()

    try:
        result = await service.collect_and_process(
            dataset_path=dataset_path,
            relationship_type="REPOST",
            delimiter=" ",
            has_header=False,
            source_column=0,
            target_column=1,
            timestamp_column=2,
            weight_column=None,
            batch_id="higgs_retweets_demo"
        )

        print("\nCollection Summary:")
        print(f"  Platform:           {result['platform']}")
        print(f"  Dataset Type:       {result['dataset_type']}")
        print(f"  Relationship:       {result['relationship_type']}")
        print(f"  Edges discovered:   {result['total_edges']}")
        print(f"  Edges processed:    {result['processed_edges']}")
        print(f"  Edges skipped:      {result['skipped_edges']}")
        print(f"  Duplicates:         {result['duplicate_edges']}")
        print(f"  Raw output:         {result['raw_output_path']}")
        print(f"  Processed output:   {result['processed_output_path']}")

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

async def test_youtube_keyword_collection():
    """Test the official YouTube Data API collector (Keyword Search)."""
    from app.services.youtube_collection_service import YouTubeCollectionService
    
    service = YouTubeCollectionService()
    
    query = "Artificial Intelligence"
    print("\n--- Testing YouTube Collector ---")
    print(f"Keyword: '{query}'")
    print("NOTE: This uses the official YouTube Data API. Quota usage applies.")
    
    try:
        # Default quota-safe settings
        result = await service.collect_by_keyword(
            query="artificial intelligence",
            video_limit=2,
            comments_per_video=10,
            include_replies=True
        )

        if "error" in result:
            print(f"\nConfiguration Error: {result['error']}")
            return

        print("\nCollection Summary:")
        print(f"  Platform:             {result.get('platform')}")
        print(f"  Videos Found:         {result.get('videos_found')}")
        print(f"  Videos Processed:     {result.get('videos_processed')}")
        print(f"  Comments Collected:   {result.get('comments_collected')}")
        print(f"  Replies Collected:    {result.get('replies_collected')}")
        print(f"  Normalized Posts:     {result.get('normalized_posts')}")
        print(f"  Persisted Posts:      {result.get('persisted_posts')}")
        print(f"  Storage Duplicates:   {result.get('storage_duplicates')}")
        print(f"  Normalization Skips:  {result.get('normalization_skips')}")
        print(f"  Skipped Videos:       {result.get('skipped_videos')}")
        print(f"  Raw output:           {result.get('raw_output_path')}")
        print(f"  Processed output:     {result.get('processed_output_path')}")

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")


async def test_x_network_datasets(limit=None):
    """Run real-data validation on HIGGS X network datasets."""
    from app.services.x_network_service import XNetworkService
    
    service = XNetworkService()
    
    datasets = [
        ("higgs-mention_network.edgelist", "MENTION", "higgs_mention_full"),
        ("higgs-reply_network.edgelist", "REPLY", "higgs_reply_full"),
        ("higgs-retweet_network.edgelist", "REPOST", "higgs_retweet_full"),
        ("higgs-social_network.edgelist", "UNKNOWN", "higgs_social_full")
    ]
    
    results_summary = []
    
    print("\n--- Testing HIGGS X Network Datasets (Validation) ---")
    
    for filename, relationship, batch_id in datasets:
        print("-" * 60)
        print(f"Dataset: {filename}")
        
        dataset_path = PROJECT_ROOT / "datasets" / "x" / "network" / filename
        
        if not dataset_path.exists():
            print(f"Status: FAILED")
            print(f"Error: File not found at {dataset_path}")
            results_summary.append((filename, relationship, "FAILED"))
            continue
            
        if relationship == "UNKNOWN":
            print("SKIPPED: HIGGS social network relationship semantics are not yet confirmed.")
            results_summary.append((filename, relationship, "SKIPPED"))
            continue
            
        print(f"Relationship: {relationship}")
        
        try:
            result = await service.collect_and_process(
                dataset_path=str(dataset_path),
                relationship_type=relationship,
                limit=limit,
                delimiter=" ",
                has_header=False,
                source_column=0,
                target_column=1,
                timestamp_column=2,
                weight_column=None,
                batch_id=batch_id
            )
            
            print("Status: SUCCESS\n")
            print(f"Edges discovered:   {result.get('total_edges')}")
            print(f"Edges processed:    {result.get('processed_edges')}")
            print(f"Edges skipped:      {result.get('skipped_edges')}")
            print(f"Duplicates:         {result.get('duplicate_edges')}\n")
            print(f"Raw output:         {result.get('raw_output_path')}")
            print(f"Processed output:   {result.get('processed_output_path')}")
            
            results_summary.append((filename, relationship, "SUCCESS"))
            
        except Exception as e:
            print(f"Status: FAILED")
            print(f"Error: {str(e)}")
            results_summary.append((filename, relationship, "FAILED"))
            
    print("-" * 60)
    print("\n" + "=" * 60)
    print("HIGGS X NETWORK VALIDATION SUMMARY")
    print("=" * 60 + "\n")
    print(f"{'Dataset':<32}{'Relationship':<16}{'Status'}")
    print("-" * 60)
    for row in results_summary:
        print(f"{row[0]:<32}{row[1]:<16}{row[2]}")
    print("-" * 60)

async def test_unified_timeline():
    """Test building the Unified Timeline from existing processed datasets."""
    from app.services.unified_timeline_service import UnifiedTimelineService
    from app.config import PROJECT_ROOT
    
    service = UnifiedTimelineService()
    
    # Path to existing processed datasets
    processed_dir = PROJECT_ROOT / "data" / "processed"
    input_paths = [
        str(processed_dir / "x"),
        str(processed_dir / "telegram"),
        str(processed_dir / "youtube")
    ]
    
    print("\n--- Building Unified Timeline ---")
    print(f"Inputs:")
    for path in input_paths:
        print(f"  - {path}")
    print("\nProcessing... (this may take a moment for large datasets)")
    
    try:
        stats = service.build_timeline(
            input_paths=input_paths,
            batch_id="full_multiplatform_2026_09_08",
            chunk_size=100_000
        )
        
        print("\nUnified Timeline Summary:")
        print(f"  Total JSONL records read: {stats['total_records_read']}")
        print(f"  Invalid records skipped:  {stats['invalid_records']}")
        print(f"  Valid records parsed:     {stats['valid_records']}")
        print(f"  Duplicate records:        {stats['duplicate_records']}")
        print(f"  Final timeline records:   {stats['final_timeline_records']}")
        print("\n  Records by Platform:")
        for platform, count in stats['records_by_platform'].items():
            print(f"    - {platform}: {count}")
            
        print(f"\n  Records with timestamp:   {stats['records_with_valid_timestamp']}")
        print(f"  Records missing timestamp:{stats['records_without_valid_timestamp']}")
        print(f"\n  Output path: {stats['output_path']}")
        
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

def test_nlp_preprocessing(input_path: str, chunk_size: int, skip_lines: int, workers: int):
    """Test running the NLP Preprocessing stage on a timeline JSONL."""
    from app.services.nlp_preprocessing_service import NLPPreprocessingService
    
    print("\n--- Running NLP Preprocessing ---")
    print(f"Input Timeline: {input_path}")
    print(f"Chunk Size: {chunk_size}")
    print(f"Workers: {workers}")
    print(f"Skip Lines: {skip_lines}")
    
    service = NLPPreprocessingService(chunk_size=chunk_size)
    batch_id = "full_multiplatform_nlp_2026_09_08"
    
    try:
        stats = service.process_timeline(input_path=input_path, batch_id=batch_id, skip_lines=skip_lines, workers=workers)
        
        print("\nNLP Preprocessing Summary:")
        print(f"  Total records read:         {stats['total_records_read']}")
        print(f"  Processed successfully:     {stats['processed_successfully']}")
        print(f"  Status USABLE:              {stats['status_usable']}")
        print(f"  Status PARTIALLY_USABLE:    {stats['status_partially_usable']}")
        print(f"  Status UNUSABLE_EMPTY:      {stats['status_unusable_empty']}")
        print(f"  Status UNUSABLE_URL_ONLY:   {stats['status_unusable_url_only']}")
        print(f"  Status UNUSABLE_MENTION:    {stats['status_unusable_mention_only']}")
        print(f"  Status UNUSABLE_ERROR:      {stats['status_unusable_error']}")
        
        print("\n  Records by Language:")
        for lang, count in stats['records_by_language'].items():
            print(f"    - {lang}: {count}")
            
        print("\n  Output files:")
        for path in stats['output_paths']:
            print(f"    - {path}")
            
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")


async def main():
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Social Media Intelligence - Pipeline Execution")
    parser.add_argument("--telegram", action="store_true", help="Run Telegram collector test")
    parser.add_argument("--x-posts", action="store_true", help="Run X Dataset collector test")
    parser.add_argument("--x-network", action="store_true", help="Run X Network collector test")
    parser.add_argument("--youtube", action="store_true", help="Run YouTube collector test")
    parser.add_argument("--x-network-validation", action="store_true", help="Run real-data validation on HIGGS X network datasets")
    parser.add_argument("--unified-timeline", action="store_true", help="Build the Unified Timeline from processed data")
    parser.add_argument("--nlp-preprocess", action="store_true", help="Run the NLP Preprocessing stage")
    parser.add_argument("--input-timeline", type=str, help="Path to timeline.jsonl for NLP Preprocessing")
    parser.add_argument("--chunk-size", type=int, default=10000, help="Chunk size for NLP Preprocessing output buffering")
    parser.add_argument("--skip-lines", type=int, default=0, help="Number of records to safely skip if resuming NLP preprocessing")
    parser.add_argument("--workers", type=int, default=8, help="Number of worker processes for NLP preprocessing")
    
    args = parser.parse_args()

    print("=" * 60)
    print("  Social Media Intelligence - Data Collection Demo")
    print("=" * 60)
    
    ran_any = False
    
    if args.telegram:
        await test_telegram_collector()
        ran_any = True
    if args.x_posts:
        await test_x_dataset_collector()
        ran_any = True
    if args.x_network:
        await test_x_network_collector()
        ran_any = True
    if args.youtube:
        await test_youtube_keyword_collection()
        ran_any = True
    if args.x_network_validation:
        await test_x_network_datasets(limit=None)
        ran_any = True
    if args.unified_timeline:
        await test_unified_timeline()
        ran_any = True
    if args.nlp_preprocess:
        if not args.input_timeline:
            print("Error: --nlp-preprocess requires --input-timeline to be specified.")
            return
        test_nlp_preprocessing(
            input_path=args.input_timeline, 
            chunk_size=args.chunk_size,
            skip_lines=args.skip_lines,
            workers=args.workers
        )
        ran_any = True
        
    if not ran_any:
        parser.print_help()
        print("No collector specified. Please pass one of the following flags:")
        print("  --telegram")
        print("  --x-posts")
        print("  --x-network")
        print("  --youtube")
        print("  --x-network-validation")
        print("  --unified-timeline")
        print("  --nlp-preprocess")

if __name__ == "__main__":
    asyncio.run(main())
