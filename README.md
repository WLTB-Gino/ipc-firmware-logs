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
T20, T33 (all other families now covered at least once).

## 2026-08-28 — gtxaspec gist harvest

30 captures imported from [gtxaspec's public gists](https://gist.github.com/gtxaspec)
(53 gists screened; vendor camera logs extracted, MACs/credentials redacted).
This nearly completes the SoC wishlist — first-ever captures for A1 (A1N NVR),
T40, T40XP, T41, T41NQ, T30, T30X, T21, T21N, T10, T31A/LC/N/X, T32NQ.

Headline findings:

- **Wyze Cam4 (T41NQ)**: apll 1104 / mpll 1440 — mpll 1440, not 1200!
- **Wyze V3 Pro (T40)**: mpll 1308 / DDR 654 — non-integer vendor tuning.
- **A1N NVR**: apll 1104 / mpll 1500 / vpll 1200 / DDR 750.
- **Wyze Cam Pan v4 (T32NQ)**: apll 1200 / mpll 840 — mpll below apll, unusual.
- **Wansview Q5 T23N rev**: thingino profiles say T21N — newer hw runs T23N,
  apll 1400 (upper T23 bin) with mpll 1200.
- **Jooan JA-Q3H (T30)**: CCLK 720 — vendor ships T30 underclocked 20% below
  the usual 900.
- **noname green T10**: fractional apll 909.312 MHz (same class as T20X
  860.160 fractional PLLs — kernel prints "909").

Remaining wishlist: T20 (true serial capture; T20X clock facts exist from
Wyze Cam2 evidence), T33.

## Provenance & license

Logs are captures of proprietary vendor firmware output, collected for
interoperability and hardware documentation research. Files mirrored from
`ipc-firmware` are credited to that repo's contributors. Do not embed
credentials, WiFi passwords, or serial numbers/MAC addresses in submissions
(redact before submitting).

## 2026-08-27 — wiki-sourced captures

5 more vendor captures, extracted from serial-log excerpts embedded in
thingino-firmware.wiki camera pages (files suffixed `-from-wiki`):

| file | SoC | source page |
|---|---|---|
| logs/xiaomi_mjsxj03hl-t23x-t31x-serial-from-wiki.boot.log | T31L/N | Camera:-Xiaomi-MJSXJ03HL |
| logs/jooan_a6m-t23x-t31x-serial-from-wiki.boot.log | T23N | Camera:-Jooan-A6M |
| logs/lsc_3215672-t23x-t31x-serial-from-wiki.boot.log | T23N | Camera:-LSC-3215672 |
| logs/galayou_g2-t23x-t31x-serial-from-wiki.boot.log | T23N (of 3 hw revs) | Camera:-Galayou-G2 |
| logs/sannce_i21ag-t23x-t31x-serial-from-wiki.boot.log | T10 | Camera:-Sannce-I21AG |

Notable: vendor T31L/N mpll = 1200 MHz (our 2026.07 SPL plan: 1000) and
vpll = 1200; vendor T23 boards show apll 1188 (LSC/Galayou) vs 1400 (Jooan A6M)
with mpll 1200 throughout — per-model vendor clock tuning is real.
