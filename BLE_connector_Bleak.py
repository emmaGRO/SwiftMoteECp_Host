import asyncio
import importlib

import bleak

from Utils import debug


class BLE_connector:
    def __init__(self, address="", to_connect=True):
        importlib.reload(bleak)  # to prevent deadlock
        self.address = address
        self.to_connect = to_connect
        try:
            asyncio.get_running_loop().run_until_complete(self.client.disconnect())
        except Exception as e:
            pass
        try:
            del self.client
        except Exception as e:
            pass
        if self.to_connect:
            self.client = bleak.BleakClient(address)
            self.connected_flag = False
            # asyncio.get_running_loop().run_until_complete(self.client.pair(1))

    async def keep_connections_to_device(self, uuids, callbacks):
        assert len(uuids) == len(callbacks)  # length and respective order must be the same,
        # the same function may be used twice with different UUIDs
        # (eg if there are 2 similar electrodes generating similar data at the same time)
        while True:
            try:
                if self.to_connect:
                    # workaround, without this line it sometimes cannot reconnect or takes a lot of time to reconnect
                    self.__init__(self.address, self.to_connect)
                    await self.client.connect(timeout=32)  # timeout should be the same as in firmware
                    if self.client.is_connected:
                        print("Connected to Device")
                        self.connected_flag = True

                        def on_disconnect(client):
                            print("Client with address {} got disconnected!".format(client.address))
                            self.connected_flag = False

                        self.client.set_disconnected_callback(on_disconnect)
                        for uuid, callback in zip(uuids, callbacks):
                            await self.client.start_notify(uuid, callback)
                        while True:
                            if not self.client.is_connected or not self.connected_flag:
                                print("Lost connection, reconnecting...")
                                await self.client.disconnect()
                                break
                            # else:
                            #     await self.test()

                            await asyncio.sleep(1)
                    else:
                        print(f"Not connected to Device, reconnecting...")
            except Exception as e:
                print(e)
                debug()
                print("Connection error, reconnecting...")
                await self.client.disconnect()  # accelerates reconnection
            self.connected_flag = False
            await asyncio.sleep(1)

    # async def scan(self):
    #    try:
    #        devices_list = []
    #
    #        devices = await bleak.BleakScanner.discover(5)
    #        devices.sort(key=lambda x: -x.rssi)  # sort by signal strength
    #        for device in devices:
    #            devices_list.append(str(device.address) + "/" + str(device.name) + "/" + str(device.rssi))
    #        #
    #        return devices_list
    #
    #        # scanner = bleak.BleakScanner()
    #        # scanner.register_detection_callback(self.detection_callback)
    #        # await scanner.start()
    #        # await asyncio.sleep(5.0)
    #        # await scanner.stop()
    #
    #
    #    except Exception as e:
    #        print(e)

    # def detection_callback(device, advertisement_data):
    #    print(device.address, "RSSI:", device.rssi, advertisement_data)

    async def start_scanning(self):
        try:
            dict_of_devices = {}

            def detection_callback(device, advertisement_data):
                # print(device.address, "RSSI:", device.rssi, advertisement_data)
                dict_of_devices[device.address] = device  # overwrites device object

            scanner = bleak.BleakScanner(scanning_mode="passive")
            scanner.register_detection_callback(detection_callback)
            await scanner.start()

            return scanner.stop, dict_of_devices

        except Exception as e:
            print(e)
            debug()
            return (-1, -1)

    async def read_characteristic(self, char_uuid='340a1b80-cf4b-11e1-ac36-0002a5d5c51b'):
        try:
            if self.connected_flag:
                return await self.client.read_gatt_char(char_uuid)
            return None
        except Exception as e:
            print(e)
            debug()
            return None

    async def write_characteristic(self, char_uuid="330a1b80-cf4b-11e1-ac36-0002a5d5c51b", data=b"Hello World!"):
        try:
            if self.connected_flag:
                return await self.client.write_gatt_char(char_uuid,
                                                         data,
                                                         response=True
                                                         )
            return None
        except Exception as e:
            print(e)
            debug()
            return None

    async def read_all_characteristics(self):
        services = await self.client.get_services()
        for characteristic in services.characteristics.values():
            try:
                print(characteristic.uuid, await self.client.read_gatt_char(characteristic))
            except Exception as e:
                pass

    async def test(self):
        print("test")
        print(self.client.mtu_size)
        try:
            print("qwer")
            print(await self.client.write_gatt_char("330a1b80-cf4b-11e1-ac36-0002a5d5c51b",
                                                    b"Hello World!",
                                                    response=True
                                                    )
                  )
            print("qwer2")
            await asyncio.sleep(0.1)
            # a = await self.client.get_services()  #
            # # print(a)
            # # b=a.descriptors.values()
            # # print(b)
            # for i, c in enumerate(a.characteristics.values()):
            #     # print(c.uuid, c.__dict__)
            #     #
            #     print(i, c.uuid, c.properties, c.__dict__)
            #     if "write" not in c.properties:
            #         continue
            #     try:
            #         # self.client.p
            #         # await self.client.pair(1)
            #         # await self.client.write_gatt_descriptor(c, B"123ABC")
            #         print("qwer")
            #         print(await self.client.write_gatt_char(c, bytearray(b'\x02\x03\x05\x07'), response=True))  # TODO
            #         await asyncio.sleep(0.1)
            #         print(await self.client.read_gatt_char(c))
            #         await asyncio.sleep(0.1)
            #         # bytearray(b'\x02\x03\x05\x07')
            #         # print(b)
            #     #
            #     except Exception as e:
            #         print("Test error 2:", e)
            #         if "Access Denied" not in str(e):
            #             print("Have a look!", e)
            #     await asyncio.sleep(0.1)
            # # '330a1b80-cf4b-11e1-ac36-0002a5d5c51b'
            # # print(a.characteristics[20])
        except Exception as e:
            debug()
            print("Test error:", e)

    async def disconnect(self):
        try:
            if self.client.is_connected:
                print("Disconnecting...")
                # del self.client
                await self.client.disconnect()
                print("Disconnected")
        except Exception as e:
            # debug()
            pass