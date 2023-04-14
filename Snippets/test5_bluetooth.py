import asyncio
from bleak import BleakScanner

async def main():
    devices = await BleakScanner.discover(5)
    for d in devices:
        print(d.__dict__)

asyncio.run(main())

print('end')