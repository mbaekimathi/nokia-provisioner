#!/bin/sh
set -e

# Host keys persist on the bind-mounted volume so container rebuilds
# don't change the relay's identity (stations would see MITM warnings).
mkdir -p /etc/relay/host_keys
[ -f /etc/relay/host_keys/ssh_host_ed25519_key ] || \
    ssh-keygen -q -t ed25519 -f /etc/relay/host_keys/ssh_host_ed25519_key -N ""
[ -f /etc/relay/host_keys/ssh_host_rsa_key ] || \
    ssh-keygen -q -t rsa -b 3072 -f /etc/relay/host_keys/ssh_host_rsa_key -N ""

exec /usr/sbin/sshd -D -e
