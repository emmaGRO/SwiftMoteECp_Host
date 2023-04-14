# FIND DEVICE

import asyncio
import bleak
# from bleak import BleakScanner
# from bleak import BleakClient
import nest_asyncio

nest_asyncio.apply()

devices_dict = {}
devices_list = []

async def run():
    devices = await bleak.BleakScanner.discover()
    for i, device in enumerate(devices):
        # Print the devices discovered
        print([i], device.address, device.name, device.metadata["uuids"])
        # Put devices information into list
        devices_dict[device.address] = []
        devices_dict[device.address].append(device.name)
        devices_dict[device.address].append(device.metadata["uuids"])
        devices_list.append(device.address)

def callback(sender, data):
    print(f"{sender}: {data}")


async def main(address):
    print("Connecting to device...")
    async with bleak.BleakClient(address) as client:
        print("Connected")

        ch = await client.read_gatt_char(16)
        #ch = await client.read_gatt_char(client.services.services[16].uuid)
        await client.start_notify(16, callback)
        #client.services.services[16].uuid
        while 1:
            await asyncio.sleep(1)

        #model_number = client.read_gatt_char()
        #print("Model Number: {0}".format("".join(map(chr, model_number))))
        # t = await client.get_services()
        # print(t.services)


loop = asyncio.get_event_loop()

asyncio.run(run())

address = "DD:B0:D5:10:15:C9"
asyncio.run(main(address))
