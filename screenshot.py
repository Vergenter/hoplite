from ppadb.client import Client as AdbClient
from ppadb.device import Device

DEFAULT_DEVICE_SERIAL = "emulator-5554"


device = AdbClient(host="localhost", port=5037).device(DEFAULT_DEVICE_SERIAL)
if not device:
    raise ConnectionRefusedError(
        "Cannot connect to device with serial", DEFAULT_DEVICE_SERIAL)
if not isinstance(device, Device):  # Should never occur
    raise ConnectionRefusedError()
result = device.screencap()
with open("screen.png", "wb") as fp:
    fp.write(result)
