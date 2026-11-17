# Tunnel relay: sshd that only accepts remote forwards (-R) from station PCs.
# Stations hold no shell access -- they can only bind their assigned ports,
# which the backend reaches as https://relay:<port> inside the compose network.
FROM alpine:3.20

RUN apk add --no-cache openssh-server \
    && adduser -D -s /sbin/nologin tunnel \
    && mkdir -p /run/sshd \
    && ssh-keygen -A

COPY deploy/relay/sshd_config /etc/ssh/sshd_config

# authorized_keys is bind-mounted from the host (deploy/relay/authorized_keys)
# so new-station.sh can append station keys without rebuilding.
EXPOSE 2222

CMD ["/usr/sbin/sshd", "-D", "-e"]
