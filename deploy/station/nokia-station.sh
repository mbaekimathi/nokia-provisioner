#!/usr/bin/env bash
# nokia-station.sh — keep the relay tunnel alive from a Linux/macOS station PC.
#
#   bash nokia-station.sh -k mombasa.ed25519 -p 18443 -r 192.168.1.254
#
# -r accepts a comma-separated list; routers map onto consecutive ports.
# For persistence, run under systemd/tmux, or install autossh and swap the
# ssh invocation for: autossh -M 0 -N -T ...
set -u

KEY=./station.ed25519
PORT=18443
ROUTER=192.168.1.254
SERVER=178.162.241.99
SSHPORT=2222

while getopts "k:p:r:s:P:" o; do
    case "$o" in
        k) KEY=$OPTARG ;; p) PORT=$OPTARG ;; r) ROUTER=$OPTARG ;;
        s) SERVER=$OPTARG ;; P) SSHPORT=$OPTARG ;;
    esac
done

IFS=',' read -ra routers <<< "$ROUTER"
if [ "${#routers[@]}" -gt 4 ]; then echo "max 4 routers per station"; exit 1; fi
echo "nokia-station: ${#routers[@]} router(s) on relay ports $PORT..$((PORT + ${#routers[@]} - 1))"

while true; do
    fwd=()
    i=0
    for r in "${routers[@]}"; do
        fwd+=(-R "0.0.0.0:$((PORT + i)):${r}:443")
        i=$((i + 1))
    done
    ssh -N -T -i "$KEY" -p "$SSHPORT" \
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new \
        "${fwd[@]}" "tunnel@$SERVER"
    echo "tunnel dropped — reconnecting in 5s"
    sleep 5
done
