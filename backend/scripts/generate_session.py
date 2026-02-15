"""Generate a Pyrogram session string for MTProto access.

Run once locally, then paste the session string into your .env file.

Usage:
    cd backend
    python -m scripts.generate_session
"""

import asyncio


async def main() -> None:
    from pyrogram import Client

    print("=== Pyrogram Session String Generator ===\n")
    print("You need api_id and api_hash from https://my.telegram.org\n")

    api_id = int(input("Enter api_id: ").strip())
    api_hash = input("Enter api_hash: ").strip()

    client = Client(
        name="session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    )

    async with client:
        session_string = await client.export_session_string()
        print("\n=== Session String (paste into .env as MTPROTO_SESSION_STRING) ===\n")
        print(session_string)
        print()


if __name__ == "__main__":
    asyncio.run(main())
