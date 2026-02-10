import asyncio
import sys
import os

# Add the project root to sys.path to allow imports within the package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polymarket_lab.lab_engine import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLab halted.")
