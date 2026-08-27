# ipc-firmware-logs

Companion to [themactep/ipc-firmware](https://github.com/themactep/ipc-firmware)
(which archives original **vendor firmware images**) — this repo archives
original **vendor firmware logs**: serial boot captures (SPL + U-Boot + kernel)
and stock-shell dumps from IP cameras.

Primary use cases:

- **Clock research** — vendor SPL prints the true PLL plan
  (`apll_freq / mpll_freq / vpll_freq`, `cclk/l2clk/h0clk/h2clk/pclk`,
  `DDR clk rate`); vendor `insmod` lines reveal the ISP/AVPU/IPU clock
  parameters vendors actually ship (vs SDK compiled-in defaults).
- Any other research needing ground truth about vendor behavior
  (module load order, sensor init, WiFi bring-up, partition layout...).

## Layout

```
logs/               raw logs, one file per device/capture
  *.boot.log        full serial capture from power-on (SPL onward)
  *.stock-dump.log  stock-shell captures (dmesg/devmem/module params)
evidence/           clock facts quoted from chats/pastes (no raw log available)
extracted/          machine-readable clock facts derived from logs
tools/collect.sh    on-camera collector (run on stock firmware shell)
tools/extract.py    parse a log -> clock-facts row
```

## Naming convention

Mirror the firmware image basename from `ipc-firmware` and append the
capture type:

```
<vendor>_<model>-<soc>-<sensor>-<wifi>-virgin.boot.log      (serial capture)
<vendor>_<model>-<soc>-<sensor>-<wifi>-virgin.stock-dump.log (shell dump)
```

If the device has no image in `ipc-firmware` yet, still follow the pattern;
unknowns may be `unknown-oem-...`.

## What to capture

Best (serial console attached, capture from power-on, ~60 s after boot):
vendor SPL PLL block, U-Boot banner, kernel `CCLK:` line, module insmod lines.

No serial access? Run `tools/collect.sh` on the stock shell and submit the
generated file. Works best on units still booted by the stock bootloader,
but register dumps are valuable in any state — just note the state in the PR.

Minimum viable: on stock firmware,
`dmesg | grep -E 'CCLK|L2CLK'` plus `devmem 0x10000010; devmem 0x10000014;
devmem 0x10000018; devmem 0x10000000` (APLL/MPLL/VPLL/CPCCR on T-series).

## Current coverage

See `extracted/clock-facts.csv`. Wishlist (no vendor serial capture yet):
T20, T21, T30, T31 (any bin), T33, T40, T41, A1.

## Provenance & license

Logs are captures of proprietary vendor firmware output, collected for
interoperability and hardware documentation research. Files mirrored from
`ipc-firmware` are credited to that repo's contributors. Do not embed
credentials, WiFi passwords, or serial numbers/MAC addresses in submissions
(redact before submitting).
