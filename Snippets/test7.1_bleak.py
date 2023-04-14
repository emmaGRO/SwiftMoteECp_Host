import asyncio
import logging

from bleak import discover
from bleak import BleakClient

devices_dict = {}
devices_list = []
#receive_data = []


# To discover BLE devices nearby
async def scan():
    dev = await discover(10)
    for i, device in enumerate(dev):
        # Print the devices discovered
        print([i], device.address, device.name, device.metadata["uuids"])
        # Put devices information into list
        devices_dict[device.address] = []
        devices_dict[device.address].append(device.name)
        devices_dict[device.address].append(device.metadata["uuids"])
        devices_list.append(device.address)


# An easy notify function, just print the recieve data
N=0
def notification_handler(sender, data):
    global N
    #print(data)
    print(N, data.hex())
    N+=1
    #print(', '.join('{:02x}'.format(x) for x in data))
    #print('---')


async def run(address, debug=False):
    log = logging.getLogger(__name__)
    if debug:
        import sys

        log.setLevel(logging.DEBUG)
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.DEBUG)
        log.addHandler(h)

    async with BleakClient(address) as client:
        x = await client.is_connected()
        log.info("Connected: {0}".format(x))

        for service in client.services:
            log.info("[Service] {0}: {1}".format(service.uuid, service.description))
            for char in service.characteristics:
                if "read" in char.properties:
                    try:
                        b = await client.read_gatt_char(char.uuid)
                        #print(b)
                        value = bytes(b)
                    except Exception as e:
                        value = str(e).encode()
                    #print(value)
                    #print('---')
                else:
                    value = None
                log.info(
                    "\t[Characteristic] {0}: (Handle: {1}) ({2}) | Name: {3}, Value: {4} ".format(
                        char.uuid,
                        char.handle,
                        ",".join(char.properties),
                        char.description,
                        value,
                    )
                )
                for descriptor in char.descriptors:
                    value = await client.read_gatt_descriptor(descriptor.handle)
                    log.info(
                        "\t\t[Descriptor] {0}: (Handle: {1}) | Value: {2} ".format(
                            descriptor.uuid, descriptor.handle, bytes(value)
                        )
                    )

        # Characteristic uuid
        CHARACTERISTIC_UUID = ['340a1b80-cf4b-11e1-ac36-0002a5d5c51b']
        for uuid in CHARACTERISTIC_UUID:
            print(uuid)
            await client.start_notify(uuid, notification_handler)
            await asyncio.sleep(10.0)
            await client.stop_notify(uuid)


if __name__ == "__main__":
    print("Scanning for peripherals...")

    # Build an event loop
    loop = asyncio.get_event_loop()
    # Run the discover event
    loop.run_until_complete(scan())

    # let user chose the device
    index = input('please select device from 0 to ' + str(len(devices_list)) + ":")
    index = int(index)
    address = devices_list[index]
    print("Address is " + address)

    # Run notify event
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(run(address, True))
