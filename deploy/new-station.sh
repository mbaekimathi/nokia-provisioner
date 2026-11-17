#!/usr/bin/env bash
# Onboard a provisioning station. Run on the VPS:
#   sudo bash deploy/new-station.sh <station-name>
#
# Generates a keypair, authorizes it for a block of relay ports, and prints
# the instructions to run on the station PC. Takes effect immediately —
# no container restart needed (sshd re-reads authorized_keys per connection).
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-}"
if [ -z "$name" ]; then
    echo "usage: sudo bash deploy/new-station.sh <station-name>"
    exit 1
fi

KEYDIR=deploy/relay/keys
STATIONS=deploy/relay/stations.tsv
KEYS=deploy/relay/authorized_keys
mkdir -p "$KEYDIR"

key="$KEYDIR/$name.ed25519"
if [ -f "$key" ]; then
    echo "station '$name' already exists ($key)"
    exit 1
fi

# each station owns a block of 4 consecutive ports: base..base+3
base=18443
while grep -q "	$base	" "$STATIONS"; do base=$((base + 10)); done

ssh-keygen -t ed25519 -N "" -f "$key" -C "station-$name" -q

opts="no-pty,no-X11-forwarding,no-agent-forwarding"
for p in $(seq "$base" $((base + 3))); do
    opts="$opts,permitlisten=\"0.0.0.0:$p\""
done
pub=$(cut -d' ' -f2 "$key.pub")
echo "$opts ssh-ed25519 $pub station-$name" >> "$KEYS"
printf '%s\t%s\t%s\n' "$name" "$base" "$(date -u +%F)" >> "$STATIONS"

cat <<EOF

Station '$name' created.  Ports $base-$((base + 3)).

1. Copy the private key to the station PC:
     $key

2. On the station PC (Windows PowerShell), keep the tunnel running:
     .\\nokia-station.ps1 -Key .\\$(basename "$key") -Port $base -Router 192.168.1.254

   Linux/macOS:
     bash nokia-station.sh -k $(basename "$key") -p $base -r 192.168.1.254

   Extra routers on that station's LAN: comma-separate them, e.g.
   -Router 192.168.1.254,192.168.100.55  ->  they map to ports $base,$((base + 1))

3. In the web UI, use these as the "router IP":
     relay:$base   relay:$((base + 1))   relay:$((base + 2))   relay:$((base + 3))
EOF
