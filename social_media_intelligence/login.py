import asyncio

from telethon import TelegramClient

from app.config import settings


async def main():
    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        int(settings.TELEGRAM_API_ID),
        settings.TELEGRAM_API_HASH
    )

    try:
        print("Connecting to Telegram...")

        await client.start(phone=settings.TELEGRAM_PHONE)

        me = await client.get_me()

        print("\nLogin successful!")
        print(f"Name: {me.first_name}")

        if me.username:
            print(f"Username: @{me.username}")

        print(f"User ID: {me.id}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())