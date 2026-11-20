#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import sys

from bumble.core import AdvertisingData
from bumble.device import Device, DeviceConfiguration
from bumble.gatt import (
    GATT_BATTERY_LEVEL_CHARACTERISTIC,
    GATT_BATTERY_SERVICE,
    GATT_DEVICE_INFORMATION_SERVICE,
    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
    GATT_SOFTWARE_REVISION_STRING_CHARACTERISTIC,
    Characteristic,
    CharacteristicValue,
    Service,
)
from types import SimpleNamespace

from bumble.hci import (
    Address,
    HCI_Error,
    HCI_LE_Set_Event_Mask_Command,
    HCI_Read_Local_Extended_Features_Command,
)
from bumble.keys import JsonKeyStore
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.transport.common import PacketParser, Transport


class StpbtSource:
    def __init__(self, loop: asyncio.AbstractEventLoop, fd: int):
        self.loop = loop
        self.fd = fd
        self.parser = PacketParser(self)
        self.terminated = loop.create_future()
        self.loop.add_reader(self.fd, self._on_readable)

    def set_packet_sink(self, sink):
        self.parser.set_packet_sink(sink)

    def _on_readable(self):
        try:
            data = os.read(self.fd, 4096)
            if not data:
                self.close()
                return
            self.parser.feed_data(data)
        except BlockingIOError:
            pass
        except Exception as exc:
            logging.error("stpbt read error: %s", exc)
            self.close()

    def close(self):
        try:
            self.loop.remove_reader(self.fd)
        except Exception:
            pass
        if not self.terminated.done():
            self.terminated.set_result(None)


class StpbtSink:
    def __init__(self, fd: int):
        self.fd = fd

    def on_packet(self, packet: bytes):
        try:
            os.write(self.fd, packet)
        except Exception as exc:
            logging.error("stpbt write error: %s", exc)

    def close(self):
        pass


class StpbtTransport(Transport):
    def __init__(self, loop: asyncio.AbstractEventLoop, path: str = "/dev/stpbt"):
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self._source = StpbtSource(loop, self.fd)
        self._sink = StpbtSink(self.fd)
        super().__init__(self._source, self._sink)

    async def close(self):
        self._source.close()
        try:
            os.close(self.fd)
        except Exception:
            pass


def read_battery_level() -> int:
    for path in (
        "/sys/class/power_supply/battery/capacity",
        "/sys/class/power_supply/BAT0/capacity",
    ):
        try:
            val = int(open(path).read().strip())
            return max(0, min(100, val))
        except Exception:
            pass
    return 100


def read_nvram_bt_address() -> Address:
    for path in (
        "/nvdata/APCFG/APRDEB/BT_Addr",
        "/data/nvram/APCFG/APRDEB/BT_Addr",
    ):
        try:
            raw = open(path, "rb").read(6)
            if len(raw) == 6 and any(raw):
                # Use static random address derived from NVRAM if needed, or public
                addr_str = ":".join(f"{b:02X}" for b in raw)
                return Address(addr_str, address_type=Address.PUBLIC_DEVICE_ADDRESS)
        except Exception:
            pass
    return Address("02:AA:BB:CC:DD:EE", address_type=Address.PUBLIC_DEVICE_ADDRESS)


class SxmoPairingDelegate(PairingDelegate):
    def __init__(self, peer_label: str = ""):
        super().__init__(
            io_capability=PairingDelegate.IoCapability.DISPLAY_OUTPUT_AND_YES_NO_INPUT
        )
        self.peer_label = peer_label

    async def _ask_dmenu(self, prompt: str, yes_label: str, no_label: str) -> bool:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XDG_RUNTIME_DIR", "/dev/shm/user/0")
        env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        cmd = ["sxmo_dmenu.sh", "-p", prompt]
        if not os.path.exists("/usr/bin/sxmo_dmenu.sh"):
            cmd = ["dmenu", "-i", "-l", "5", "-p", prompt]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            choices = f"{yes_label}\n{no_label}\n".encode()
            stdout, _ = await asyncio.wait_for(proc.communicate(choices), timeout=30.0)
            ans = stdout.decode("utf-8", errors="ignore").strip()
            logging.info("Pairing prompt '%s' -> user selected: '%s'", prompt, ans)
            return ans == yes_label
        except Exception as exc:
            logging.error("Pairing dmenu failed: %s", exc)
            return False

    async def accept(self) -> bool:
        logging.info("Pairing request from %s", self.peer_label)
        return True

    async def confirm(self, auto: bool = False) -> bool:
        if auto:
            logging.info("Auto-confirming pairing with %s", self.peer_label)
            return True
        return await self._ask_dmenu(
            f"Pair {self.peer_label}?",
            "Yes - Confirm",
            "No - Reject",
        )

    async def compare_numbers(self, number: int, digits: int = 6) -> bool:
        code = f"{number:0{digits}d}"
        logging.info("Pairing Numeric Comparison with %s: code=%s", self.peer_label, code)
        return await self._ask_dmenu(
            f"BT Code: {code}",
            f"Yes - Match {code}",
            "No - Reject",
        )

    async def display_number(self, number: int, digits: int = 6) -> None:
        code = f"{number:0{digits}d}"
        logging.info("Pairing Passkey Display for %s: code=%s", self.peer_label, code)
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        try:
            await asyncio.create_subprocess_exec(
                "sxmo_notify_user.sh",
                f"BT Pair Code: {code}",
                env=env,
            )
        except Exception:
            pass


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    loop = asyncio.get_running_loop()

    transport = StpbtTransport(loop, "/dev/stpbt")
    config = DeviceConfiguration(
        name="Lenovo-A2010-Alpine",
        address=read_nvram_bt_address(),
        classic_enabled=True,
        le_enabled=True,
        classic_sc_enabled=False,
        classic_ssp_enabled=True,
        advertising_interval_min=100,
        advertising_interval_max=200,
    )
    # Static random address for BLE advertising (top two bits = 11)
    static_addr = Address("D4:AA:BB:CC:DD:EE", address_type=Address.RANDOM_DEVICE_ADDRESS)
    config.address = static_addr

    device = Device.from_config_with_hci(config, transport.source, transport.sink)
    device.keystore = JsonKeyStore(
        namespace="lenovo_a2010",
        filename="/var/lib/bt-keys.json",
    )
    device.pairing_config_factory = lambda connection: PairingConfig(
        sc=False,
        mitm=True,
        bonding=True,
        delegate=SxmoPairingDelegate(str(connection.peer_address)),
    )

    # MT6625L (BT 4.0) compatibility shim for Bumble 0.0.236
    orig_send_sync = device.host.send_sync_command

    async def compat_send_sync_command(command, *args, **kwargs):
        if isinstance(command, HCI_LE_Set_Event_Mask_Command):
            # BT 4.0 controller only accepts bits 0..4 in LE Event Mask
            command = HCI_LE_Set_Event_Mask_Command(
                le_event_mask=bytes([0x1F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            )
        try:
            return await orig_send_sync(command, *args, **kwargs)
        except HCI_Error as exc:
            if isinstance(command, HCI_Read_Local_Extended_Features_Command):
                logging.warning(
                    "MT6625L: ignoring %s on page %s", exc, command.page_number
                )
                return SimpleNamespace(
                    status=0,
                    page_number=command.page_number,
                    maximum_page_number=0,
                    extended_lmp_features=bytes(8),
                )
            raise

    device.host.send_sync_command = compat_send_sync_command

    def on_connection(connection):
        logging.info(
            "CONNECTED: peer=%s transport=%s handle=0x%04x",
            connection.peer_address,
            connection.transport,
            connection.handle,
        )

        def on_disconnection(reason):
            logging.info(
                "DISCONNECTED: peer=%s reason=%s",
                connection.peer_address,
                reason,
            )

        connection.on("disconnection", on_disconnection)

    device.on("connection", on_connection)

    # Device Information Service
    device.add_service(
        Service(
            GATT_DEVICE_INFORMATION_SERVICE,
            [
                Characteristic(
                    GATT_MANUFACTURER_NAME_STRING_CHARACTERISTIC,
                    Characteristic.Properties.READ,
                    Characteristic.READABLE,
                    b"Lenovo",
                ),
                Characteristic(
                    GATT_MODEL_NUMBER_STRING_CHARACTERISTIC,
                    Characteristic.Properties.READ,
                    Characteristic.READABLE,
                    b"A2010-a (MT6735m)",
                ),
                Characteristic(
                    GATT_SOFTWARE_REVISION_STRING_CHARACTERISTIC,
                    Characteristic.Properties.READ,
                    Characteristic.READABLE,
                    b"Alpine Linux 3.20.3 + Sxmo",
                ),
            ],
        )
    )

    # Battery Service (live battery percentage)
    device.add_service(
        Service(
            GATT_BATTERY_SERVICE,
            [
                Characteristic(
                    GATT_BATTERY_LEVEL_CHARACTERISTIC,
                    Characteristic.Properties.READ,
                    Characteristic.READABLE,
                    CharacteristicValue(read=lambda _conn: bytes([read_battery_level()])),
                ),
            ],
        )
    )

    await device.power_on()
    logging.info(
        "Bluetooth powered on! Public=%s Random=%s",
        device.public_address,
        device.random_address,
    )

    # Make discoverable & connectable over Classic BT
    await device.set_discoverable(True)
    await device.set_connectable(True)

    # Start BLE advertising with device name and Battery Service UUID
    adv_data = bytes(
        AdvertisingData(
            [
                (
                    AdvertisingData.FLAGS,
                    bytes([AdvertisingData.LE_GENERAL_DISCOVERABLE_MODE_FLAG]),
                ),
                (
                    AdvertisingData.COMPLETE_LOCAL_NAME,
                    b"Lenovo-A2010-Alpine",
                ),
                (
                    AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,
                    bytes(GATT_BATTERY_SERVICE),
                ),
            ]
        )
    )
    await device.start_advertising(advertising_data=adv_data, auto_restart=True)
    logging.info("Advertising started as 'Lenovo-A2010-Alpine' (BLE + Classic)")

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await device.power_off()
    await transport.close()


if __name__ == "__main__":
    asyncio.run(main())
