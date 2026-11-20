# Lenovo A2010-a (MT6735M) — Нативный порт Alpine Linux (PoC)

**Язык / Language:** [English](README.md) | **Русский**

> **Дисклеймер:** Это экспериментальный прототип (PoC), собранный с помощью ИИ поверх стокового ядра MediaTek Linux `3.10.65`. Публикуется **«как есть» (AS IS)**, чтобы рабочие решения по запуску железа (маршрутизация звука MT6328, обновление экрана `mtkfb`, инициализация Wi-Fi/GPS через WMT, USB-гаджет `android_usb` для RNDIS и загрузочной флешки) могли сэкономить время другим разработчикам и энтузиастам `postmarketOS` / 4PDA.

## Целевое устройство
- **Модель:** Lenovo A2010-a (`MT6735M`, 4× Cortex-A53, 1 ГБ RAM, 8 ГБ eMMC, экран 4.5" 854×480)
- **Ядро:** Стоковое downstream-ядро `3.10.65` (пользовательское окружение `armv7l`, Alpine Linux `3.20`)
- **Интерфейс:** Sxmo (`dwm` / `dmenu`) + кастомные утилиты

## Что работает
- **Загрузка и хранение:** Прямой запуск Alpine Linux из раздела `userdata` через кастомный `boot.img` (прошивается через `SP Flash Tool` / `mtkclient` по `MT6735M_Android_scatter.txt`).
- **Экран, тач и кнопки:** Вывод через фреймбуфер (`mtkfb`) с триггером обновления оверлеев (`mtk_flusher.py`, `reset_mtk_overlays.py`), мост тачскрина (`touch_bridge.py`), перехват аппаратных кнопок (`hw_keys_daemon.py`), поворот и яркость экрана.
- **USB-гаджет (`android_usb`):**
  - **Сеть RNDIS (`usbnet-daemon`):** Статический USB Ethernet (`10.42.0.2/24`, доступ по SSH).
  - **Загрузочная USB-флешка (`usb-mode`):** Переключает `android_usb` в режим `mass_storage`, отдавая сырой образ диска (например, `/var/lib/usbboot/alpine-usb.img`) для загрузки обычных ПК (`x86_64` UEFI) прямо с телефона.
- **Звук (`setup-audio`, `cyberrec`):** Маршрутизация ALSA-микшеров кодека MediaTek MT6328 (динамик, наушники, запись с микрофона — проверено распознаванием речи через Whisper на дистанции 1–3 м).
- **Wi-Fi / Bluetooth / GPS / Камера / Фонарик:** `10-mtk-wifi.start`, `wifi-menu.sh`, `bt-server.py` + `bt-menu.sh` (Bluetooth 4.0 BLE + Classic поверх `/dev/stpbt` и Google Bumble с окном подтверждения спаривания в Sxmo `dmenu`), `mtk-gps.sh`, `cybercam` + `camshot`, `torch-toggle.sh`.
- **4G LTE модем (`modem-ctl.sh`, `property_service.py`):** Запускает стоковый модемный стек MediaTek CCCI (`ccci_fsd`, `ccci_mdinit`, `gsm0710muxd`) с симлинками `/dev/block/platform/mtk-msdc.0/by-name/*` для MASP и разделами `/protect_f` + `/protect_s` + `rw /nvdata`, поднимая AT-каналы `/dev/radio/pttycmd1` и интерфейсы `ccmni0`–`ccmni2` (проверено сканирование живых 2G/3G/4G LTE вышек через `AT+ECELL` / `AT+COPS=?`).

## Как устроены загрузка и запуск железа (ядро и ramdisk)
- **Ядро:** Используется **немодифицированное стоковое ядро MediaTek `3.10.65`** из заводского `boot.img` (прошивка `S260`) — пересборка ядра не требуется.
- **Кастомный `ramdisk` (`boot/init`, `boot/init.sh`):** Стандартный initramfs Android внутри `boot.img` заменён на минимальное окружение со статическим `busybox`, которое монтирует `/dev/mmcblk0p22` (`userdata`) и передаёт управление (`/sbin/init` Alpine Linux) через `switch_root`.
- **Использование стоковых блобов (`/system` на `/dev/mmcblk0p20`):** Заводской раздел `/system` остаётся в режиме только для чтения (`ro`), чтобы Alpine мог поднимать железо MTK через скрипты в `native_scripts/etc/local.d/`:
  - `05-android-props.start` + `mk-android-props.py` — подготавливает файлы свойств Android для вендорных демонов.
  - `10-mtk-wifi.start` — монтирует `/nvdata` (`ro`), создаёт узлы `/dev/wmtWifi` (`c 153 0`), `/dev/stpwmt` (`c 190 0`) и `/dev/stpbt` (`c 192 0`), запускает `/system/bin/wmt_loader` и `/system/bin/6620_launcher -p /system/etc/firmware/`, после чего включает `wlan0` командой `echo 1 > /dev/wmtWifi`.

## Структура репозитория
- `boot/` — Готовый образ `boot_alpine.img` (стоковое ядро `3.10.65` + кастомный ramdisk), а также извлечённые `init` и `init.sh`.
- `native_scripts/usr_local_bin/` — Основные демоны и утилиты (`usbnet-daemon`, `usb-mode`, `setup-audio`, `cyberrec`, `cybercam`, `cyberview`, `hw_keys_daemon.py`, `touch_bridge.py`, `mtk_flusher.py` и др.).
- `native_scripts/sxmo_hooks/` — Модифицированный `sxmo_hook_contextmenu.sh` с пунктами Wi-Fi, Bluetooth, Audio, GPS, фонарика, поворота экрана и переключателя USB-флешки/RNDIS.
- `native_scripts/etc/` — Сервисы OpenRC (`usbnet`, `cyberdeck`), скрипты `local.d`, `fstab`, `network/interfaces`.
- `native_scripts/configs/` и `native_scripts/applications/` — Конфиги оконного менеджера/UI и `.desktop`-ярлыки.
- `tools/` — Скрипты автоматизации по SSH/SCP через USB RNDIS (`10.42.0.2`).
- `deploy_native.sh` и `flash_native_mtk.sh` — Скрипты деплоя и прошивки.
- `MT6735M_Android_scatter.txt` — Таблица разделов для прошивальщиков MTK.

## Примечание о проприетарных разделах и бэкапах
Уникальные разделы устройства (`nvram`, `nvdata`), калибровки IMEI/MAC, сохранённые пароли Wi-Fi и полные дампы `rootfs` намеренно исключены. Перед любыми экспериментами обязательно снимите полный бэкап своего устройства через `mtkclient` или `SP Flash Tool`.
