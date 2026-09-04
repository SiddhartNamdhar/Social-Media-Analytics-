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
    channel_to_scrape = "@artificial_intelligence_ai"

    try:
        is_connected = await service.collector.validate_connection()
        if not is_connected:
            print("Please check your .env file and authenticate via interactive CLI first!")
            return
            
        print(f"Connection OK. Collecting messages from {channel_to_scrape}...")
        
        result = await service.collect_and_process(
            channel=channel_to_scrape,
            limit=200,
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
    dataset_path = str(PROJECT_ROOT / "datasets/x/posts/tweets.csv")

    print("\n--- Testing X Dataset Collector ---")
    print(f"Dataset: {dataset_path}")
    print()

    try:
        result = await service.collect_and_process(
            dataset_path=dataset_path,
            source_name="tweets_demo"
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
            query=query,
            video_limit=2,
            comments_per_video=10,
            include_replies=False
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


async def main():
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Social Media Intelligence - Data Collection Demo")
    parser.add_argument("--telegram", action="store_true", help="Run Telegram collector test")
    parser.add_argument("--x-posts", action="store_true", help="Run X Dataset collector test")
    parser.add_argument("--x-network", action="store_true", help="Run X Network collector test")
    parser.add_argument("--youtube", action="store_true", help="Run YouTube collector test")
    
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
        
    if not ran_any:
        print("No collector specified. Please pass one of the following flags:")
        print("  --telegram")
        print("  --x-posts")
        print("  --x-network")
        print("  --youtube")

if __name__ == "__main__":
    asyncio.run(main())
