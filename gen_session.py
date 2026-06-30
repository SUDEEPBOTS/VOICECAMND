"""
Pyrogram String Session Generator.
Run this ONCE to generate a session string for cloud deployment.

Usage: python gen_session.py
"""

import asyncio
from pyrogram import Client


async def main():
    print("\n" + "=" * 50)
    print("  🔐 Pyrogram String Session Generator")
    print("=" * 50 + "\n")

    api_id = int(input("Enter API_ID: "))
    api_hash = input("Enter API_HASH: ").strip()

    print("\nStarting Pyrogram client...")
    print("You will be asked for your phone number and OTP.\n")

    async with Client(
        name="session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    ) as app:
        session_string = await app.export_session_string()

        print("\n" + "=" * 60)
        print("✅ SESSION STRING GENERATED SUCCESSFULLY!")
        print("=" * 60)
        print("\nYour string session (copy this ENTIRE string):\n")
        print(session_string)
        print("\n" + "=" * 60)
        print("\nSet it as environment variable:")
        print(f'  export STRING_SESSION="{session_string}"')
        print("\nOr add to .env file:")
        print(f"  STRING_SESSION={session_string}")
        print("\n⚠️  KEEP THIS SECRET! Anyone with this string")
        print("   can access your Telegram account!\n")


if __name__ == "__main__":
    asyncio.run(main())
