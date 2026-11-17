#!/bin/bash
# Pasang ulang service ASMR dari salinan induk persisten (unit /etc hilang tiap VM diganti)
set -e
for u in asmr-tools-vm vm-reverse-asmr; do
  cp "/home/hatch/workspace/asmr-service/systemd/$u.service" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable --now asmr-tools-vm.service vm-reverse-asmr.service
