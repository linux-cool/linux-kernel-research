#!/usr/bin/env bash
# Minimal QEMU launcher (safe sandbox). Usage:
#   bash qemu_run.sh -k /path/to/bzImage -i /path/to/initramfs.img \
#       [-m 2G] [-a "console=ttyS0"] [-p 10022:22] [-n]
# Options:
#   -k  kernel bzImage path (required)
#   -i  initrd/initramfs path (required)
#   -m  memory size (default: 2G)
#   -a  kernel cmdline append (default: "console=ttyS0 earlyprintk=serial")
#   -p  hostfwd spec host_port:guest_port (enable usernet with SSH forward)
#   -n  use -enable-kvm if available
set -euo pipefail
mem=2G
append="console=ttyS0 earlyprintk=serial"
kernel=""
initrd=""
hostfwd=""
kvm=""
while getopts ":k:i:m:a:p:n" opt; do
  case $opt in
    k) kernel="$OPTARG";;
    i) initrd="$OPTARG";;
    m) mem="$OPTARG";;
    a) append="$OPTARG";;
    p) hostfwd="$OPTARG";;
    n) kvm="-enable-kvm";;
    *) echo "Usage: $0 -k bzImage -i initrd [-m 2G] [-a cmdline] [-p host:guest] [-n]"; exit 1;;
  esac
done
if [[ -z ${kernel} || -z ${initrd} ]]; then
  echo "Missing -k or -i"; exit 1
fi
net_args=""
if [[ -n ${hostfwd} ]]; then
  net_args="-netdev user,id=n0,hostfwd=tcp::${hostfwd} -device e1000,netdev=n0"
fi
set -x
qemu-system-x86_64 ${kvm} -m "${mem}" -nographic \
  -kernel "${kernel}" -initrd "${initrd}" \
  -append "${append}" ${net_args}

