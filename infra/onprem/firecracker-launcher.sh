#!/usr/bin/env bash
# On-Premises Bare-metal Firecracker MicroVM Launcher
# Usage: ./firecracker-launcher.sh <create|destroy> <session_id> [vcpu] [ram_mb]
set -euo pipefail

ACTION="${1:-}"
SESSION_ID="${2:-}"
VCPU="${3:-1}"
RAM_MB="${4:-512}"

BASE_DIR="/var/lib/linux-lab"
KERNEL_IMG="${BASE_DIR}/images/vmlinux.bin"
ROOTFS_BASE="${BASE_DIR}/images/ubuntu-24.04-base.ext4"
WORK_DIR="${BASE_DIR}/sessions/${SESSION_ID}"
SOCK_PATH="${WORK_DIR}/firecracker.socket"

if [[ -z "${ACTION}" || -z "${SESSION_ID}" ]]; then
  echo "Usage: $0 <create|destroy> <session_id> [vcpu] [ram_mb]"
  exit 1
fi

case "${ACTION}" in
  create)
    mkdir -p "${WORK_DIR}"
    # Copy-on-Write 복제 (ZFS/XFS reflink 환경 권장)
    cp --reflink=auto "${ROOTFS_BASE}" "${WORK_DIR}/rootfs.ext4"
    echo "[linux-lab] Launching Firecracker MicroVM for session=${SESSION_ID} (${VCPU} vCPU, ${RAM_MB}MB RAM)"
    firecracker --api-sock "${SOCK_PATH}" --daemonize
    curl --unix-socket "${SOCK_PATH}" -s -X PUT "http://localhost/machine-config" \
      -H "Content-Type: application/json" \
      -d "{\"vcpu_count\": ${VCPU}, \"mem_size_mib\": ${RAM_MB}}"
    curl --unix-socket "${SOCK_PATH}" -s -X PUT "http://localhost/boot-source" \
      -H "Content-Type: application/json" \
      -d "{\"kernel_image_path\": \"${KERNEL_IMG}\", \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off\"}"
    curl --unix-socket "${SOCK_PATH}" -s -X PUT "http://localhost/drives/rootfs" \
      -H "Content-Type: application/json" \
      -d "{\"drive_id\": \"rootfs\", \"path_on_host\": \"${WORK_DIR}/rootfs.ext4\", \"is_root_device\": true, \"is_read_only\": false}"
    curl --unix-socket "${SOCK_PATH}" -s -X PUT "http://localhost/actions" \
      -H "Content-Type: application/json" \
      -d '{"action_type": "InstanceStart"}'
    echo "[linux-lab] Session ${SESSION_ID} started."
    ;;
  destroy)
    pkill -f "${SOCK_PATH}" || true
    rm -rf "${WORK_DIR}"
    echo "[linux-lab] Session ${SESSION_ID} destroyed and cleaned up."
    ;;
  *)
    echo "Unknown action: ${ACTION}"
    exit 1
    ;;
esac
