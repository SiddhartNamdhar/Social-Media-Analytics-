import asyncio
# pyright: ignore[reportMissingImports]
from dotenv import load_dotenv

from app.logging_config import setup_logging

async def main():
    # Load .env first
    load_dotenv()
    
    # Needs to be imported after dotenv is loaded so config values are present if instantiated immediately, 
    # though Pydantic BaseSettings loads from file anyway.
    setup_logging()
    
    from app.services.telegram_collection_service import TelegramCollectionService
    
    service = TelegramCollectionService()

    print("--- Testing Telegram Data Collector ---")
    print("WARNING: Make sure you replace @telegram with a public channel you can legitimately access.")
    # You can replace this with any accessible channel like '@example_channel'
    channel_to_scrape = "@telegram" 

    try:
        # Validate connection credentials implicitly by calling validate connection
        is_connected = await service.collector.validate_connection()
        if not is_connected:
            print("Please check your .env file and authenticate via interactive CLI first!")
            return
            
        print(f"Connection OK. Collecting messages from {channel_to_scrape}...")
        
        result = await service.collect_and_process(
            channel=channel_to_scrape,
            limit=50,
            keywords=None
        )

        print("\nCollection Result:")
        import json
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
    finally:
        await service.collector.client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
