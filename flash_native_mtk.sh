#!/usr/bin/env bash
# ==============================================================================
# Lenovo A2010 — Нативная прошивка Alpine Linux через mtkclient (BROM/PreLoader)
# Использование:
#   sudo ./flash_native_mtk.sh [boot|userdata|all]
# Перед запуском: выключить телефон; после "Waiting for PreLoader" подключить USB.
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MTK_DIR="$BASE_DIR/tools/mtkclient"
MTK="env PYTHONPATH=$MTK_DIR:$MTK_DIR/.venv/lib/python3.14/site-packages python3 $MTK_DIR/mtk.py"

cd "$BASE_DIR"

case "${1:-boot}" in
  boot)
    echo "[*] Прошивка нативного ядра + initramfs (boot_alpine.img)..."
    $MTK w boot "$BASE_DIR/boot_alpine.img"
    ;;
  userdata)
    echo "[*] Прошивка нативного корневого раздела Alpine Linux (userdata_alpine.img)..."
    $MTK w userdata "$BASE_DIR/userdata_alpine.img"
    ;;
  all)
    echo "[*] Полная нативная прошивка (boot_alpine.img + userdata_alpine.img)..."
    $MTK w boot,userdata "$BASE_DIR/boot_alpine.img,$BASE_DIR/userdata_alpine.img"
    ;;
  *)
    echo "Использование: $0 [boot|userdata|all]"
    exit 1
    ;;
esac

echo "[+] Готово! Отсоедини кабель и включи телефон."
