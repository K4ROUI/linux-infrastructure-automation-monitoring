FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    openssh-server nginx prometheus-node-exporter supervisor \
    sudo python3 python3-apt curl rsync tar iproute2 procps ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -s /bin/bash labadmin \
 && password="$(head -c 48 /dev/urandom | base64 -w 0)" \
 && printf 'labadmin:%s\n' "$password" | chpasswd \
 && echo 'labadmin ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/90-labadmin \
 && chmod 0440 /etc/sudoers.d/90-labadmin \
 && mkdir -p /run/sshd /run/lab /srv/labsite /srv/lab-backups \
 && rm -f /etc/ssh/ssh_host_* \
 && chmod 0755 /run/sshd

COPY ssh-hardening.conf /etc/ssh/sshd_config.d/99-lab.conf
COPY supervisor-lab.conf /etc/supervisor/conf.d/lab.conf
COPY entrypoint.sh /usr/local/bin/lab-entrypoint
RUN chmod 0755 /usr/local/bin/lab-entrypoint
EXPOSE 22 80 9100
ENTRYPOINT ["/usr/local/bin/lab-entrypoint"]
