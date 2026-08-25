import argparse
import asyncio

from trolley.client import PantryClient
from trolley.config import TrolleySettings


async def run(settings: TrolleySettings | None = None) -> None:
    settings = settings or TrolleySettings()
    await PantryClient(settings).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Trolley runtime")
    parser.add_argument("command", choices=["run"])
    parser.parse_args()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
