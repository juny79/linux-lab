#!/usr/bin/env bash
# On-Premises VLAN 30 Sandbox Egress Isolation (nftables)
# - 외부 인터넷(Egress) 전면 차단
# - VLAN 20 로컬 APT/YUM 미러 서버(10.20.0.10:80,443)만 예외 허용
set -euo pipefail

SANDBOX_SUBNET="10.30.0.0/16"
LOCAL_MIRROR_IP="10.20.0.10"

nft add table inet linux_lab_sandbox
nft flush table inet linux_lab_sandbox

nft add chain inet linux_lab_sandbox forward '{ type filter hook forward priority 0; policy accept; }'

# 1. 이미 수립된 연결 허용
nft add rule inet linux_lab_sandbox forward ct state established,related accept

# 2. Sandbox -> 로컬 패키지 미러(80, 443)만 허용
nft add rule inet linux_lab_sandbox forward ip saddr "${SANDBOX_SUBNET}" ip daddr "${LOCAL_MIRROR_IP}" tcp dport '{ 80, 443 }' accept

# 3. Sandbox -> 외부 인터넷 및 타 VLAN 접근 전면 차단
nft add rule inet linux_lab_sandbox forward ip saddr "${SANDBOX_SUBNET}" counter drop

echo "[linux-lab] VLAN 30 Sandbox Egress isolation rules applied successfully."
