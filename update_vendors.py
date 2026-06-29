import asyncio

from mac_vendor_lookup import AsyncMacLookup


async def main() -> None:
    lookup = AsyncMacLookup()
    await lookup.update_vendors()
    print("Vendor database updated")


if __name__ == "__main__":
    asyncio.run(main())
