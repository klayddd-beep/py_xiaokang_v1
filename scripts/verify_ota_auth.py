import asyncio

from src.core.ota import Ota


async def main() -> None:
    ota = await Ota.get_instance()
    headers = ota.build_headers()
    print(f"has_auth={ 'Authorization' in headers }")
    print(headers.get("Authorization", ""))


if __name__ == "__main__":
    asyncio.run(main())
