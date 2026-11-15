# Lenovo A2010-a (MT6735M) — Native Alpine Linux Port (PoC)

**Language / Язык:** **English** | [Русский](README.ru.md)

> **Disclaimer:** This is an experimental, AI-assisted proof-of-concept port built on top of the stock MediaTek Linux `3.10.65` downstream kernel. Published **AS IS** so that the working hardware bring-up scripts (MT6328 audio routing, `mtkfb` overlay trigger, WMT Wi-Fi/GPS, `android_usb` RNDIS + Mass Storage gadget) can save time for other developers and postmarketOS / 4PDA tinkerers.

## Hardware Target
- **Device:** Lenovo A2010-a (`MT6735M`, 4x Cortex-A53, 1 GB RAM, 8 GB eMMC, 4.5" 854x480)
- **Kernel:** Stock downstream `3.10.65` (`armv7l` userspace, Alpine Linux `3.20`)
- **UI:** Sxmo (`dwm` / `dmenu`) + custom cyberdeck/phone utilities

## What Works
- **Boot & Storage:** Boots directly into Alpine Linux from `userdata` via custom `boot` image (flashed with `SP Flash Tool` / `mtkclient` using `MT6735M_Android_scatter.txt`).
- **Display & Touch:** Framebuffer output (`mtkfb`) with periodic overlay trigger (`mtk_flusher.py`, `reset_mtk_overlays.py`), touchscreen bridge (`touch_bridge.py`), hardware keys (`hw_keys_daemon.py`), screen rotation & brightness.
- **USB Gadget (`android_usb`):**
  - **RNDIS network (`usbnet-daemon`):** Static USB Ethernet (`10.42.0.2/24`, SSH access).
  - **Bootable USB Flash (`usb-mode`):** Switches `android_usb` to `mass_storage` exposing a raw disk image (e.g. `/var/lib/usbboot/alpine-usb.img`) to boot x86_64 PCs over UEFI.
- **Audio (`setup-audio`, `cyberrec`):** ALSA mixer routing for MediaTek MT6328 codec (speaker, headset, microphone recording — verified with Whisper on 1–3m speech).
- **Wi-Fi / GPS / Camera / Torch:** `10-mtk-wifi.start`, `wifi-menu.sh`, `mtk-gps.sh`, `cybercam` + `camshot`, `torch-toggle.sh`.


## How Boot & Hardware Bring-Up Work (Kernel & Ramdisk)
- **Kernel:** Uses the **unmodified stock MediaTek `3.10.65` kernel** extracted from Lenovo A2010 `boot.img` (`S260` firmware) — no custom kernel compilation required.
- **Custom Ramdisk (`boot/init`, `boot/init.sh`):** Replaces the Android initramfs inside `boot.img` with a minimal static `busybox` environment that mounts `/dev/mmcblk0p22` (`userdata`) and `switch_root`s into Alpine Linux `/sbin/init`.
- **Vendor Blobs Reuse (`/system` on `/dev/mmcblk0p20`):** The stock Android `/system` partition is kept read-only and mounted at `/system` so Alpine can initialize MTK hardware via `native_scripts/etc/local.d/`:
  - `05-android-props.start` + `mk-android-props.py` — sets up Android property files needed by vendor daemons.
  - `10-mtk-wifi.start` — mounts `/nvdata` (`ro`), creates `/dev/wmtWifi` (`c 153 0`) & `/dev/stpwmt` (`c 190 0`), runs `/system/bin/wmt_loader` and `/system/bin/6620_launcher -p /system/etc/firmware/`, then enables `wlan0` via `echo 1 > /dev/wmtWifi`.

## Repository Layout
- `boot/` — Prebuilt `boot_alpine.img` (stock `3.10.65` kernel + custom ramdisk), plus extracted `init` and `init.sh`.
- `native_scripts/usr_local_bin/` — Core daemons and CLI utilities (`usbnet-daemon`, `usb-mode`, `setup-audio`, `cyberrec`, `cybercam`, `cyberview`, `hw_keys_daemon.py`, `touch_bridge.py`, `mtk_flusher.py`, etc.).
- `native_scripts/sxmo_hooks/` — Modified `sxmo_hook_contextmenu.sh` with Wi-Fi, Audio, GPS, Flashlight, Screen Rotate, and USB Flash/RNDIS toggle.
- `native_scripts/etc/` — OpenRC services (`usbnet`, `cyberdeck`), `fstab`, `network/interfaces`.
- `native_scripts/configs/` & `native_scripts/applications/` — WM/UI configs and `.desktop` entries.
- `tools/` — SSH/SCP automation helpers over USB RNDIS (`10.42.0.2`).
- `deploy_native.sh` & `flash_native_mtk.sh` — Deployment and flashing scripts.
- `MT6735M_Android_scatter.txt` — Partition layout for MTK flashing tools.

## Note on Proprietary Blobs & Backups
Device-specific NVRAM/NVDATA partitions, IMEI/MAC calibrations, Wi-Fi credentials, and full `rootfs` tarballs are intentionally excluded. Take a full `mtkclient` / `SP Flash Tool` backup of your own device before flashing.
