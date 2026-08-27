#!/bin/sh
# Collect vendor clock/log evidence from a stock (or stock-bootloader) camera shell.
# Usage: sh collect.sh   -> writes stock-<date>.log in cwd
OUT="stock-$(date +%Y%m%d-%H%M%S).log"
{
  echo "=== collected $(date -u) ==="
  echo "=== uname ==="
  uname -a
  cat /proc/version 2>/dev/null
  echo "=== bootloader state note ==="
  echo "(submitter: state whether stock U-Boot or Thingino U-Boot booted this kernel)"
  echo "=== kernel clock lines ==="
  dmesg | grep -iE 'CCLK|L2CLK|H0CLK|H2CLK|PCLK'
  echo "=== CPM registers (T-series: APCR/MPCR/VPCR/CPCCR/CCR) ==="
  for a in 0x10000010 0x10000014 0x10000018 0x10000000 0x10000024 0x10000060; do
    printf '%s: ' "$a"
    devmem "$a" 2>/dev/null || echo "n/a"
  done
  echo "=== clock summary (if debugfs) ==="
  cat /sys/kernel/debug/clk/clk_summary 2>/dev/null | head -80
  echo "=== ISP/AVPU/IPU module params ==="
  for m in /sys/module/*isp*/parameters /sys/module/*avpu*/parameters /sys/module/*ipu*/parameters /sys/module/*vpu*/parameters; do
    [ -d "$m" ] || continue
    echo "--- $m"
    for p in "$m"/*; do printf '%s=' "${p##*/}"; cat "$p" 2>/dev/null; echo; done
  done
  echo "=== insmod lines from stock init scripts (if readable) ==="
  grep -rshiE 'insmod.*(isp|avpu|vpu|ipu|sensor)' /etc /system 2>/dev/null | head -40
  echo "=== sensor ==="
  dmesg | grep -iE 'chip found|sensor driver|stream on' | head
} > "$OUT" 2>&1
echo "wrote $OUT"
