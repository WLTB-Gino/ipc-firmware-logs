# Evidence: kernel CCLK lines quoted in Discord (no raw capture on file)
# Each line is a distinct device report. Bootloader state noted where known.

# Vanhua Z55 (T31X, GC4653) — reported by Nic 2026-08-21, session 1540410378230435981
# Bootloader: STOCK vendor U-Boot (later AVPU probing measured vpll=1080 on this unit)
CCLK:1392MHz L2CLK:696Mhz H0CLK:200MHz H2CLK:200Mhz PCLK:100Mhz
# Same session, CPM register reads (devmem): APCR/MPCR both 0x0640510D.
# NOTE: vendor h0/h2=200 pclk=100 differs from Thingino 2013.07 SPL plan
# (h0/h2=240 pclk=120) — flashing Thingino U-Boot shifts the whole bus plan.

# Wyze Cam2 (T20X, JXF22) — reported 2026-08-10, session 1536450347848044675
# Bootloader state unknown
CCLK:860MHz L2CLK:430Mhz H0CLK:200MHz H2CLK:200Mhz PCLK:100Mhz
# ANOMALY: 860 is not an integer 24MHz PLL product (24*36=864). Suspect
# non-24MHz crystal or divider rounding. ACR devmem read would resolve.
