#!/usr/bin/env python3
"""Parse a vendor boot log into machine-readable clock facts.

Usage: extract.py <logfile> [--csv]
Emits key=value facts; with --csv appends a row matching extracted/clock-facts.csv.
"""
import re
import sys

PATTERNS = {
    "soc_probe": r"Probing SoC\.\.\. (\S+)",
    "board_info": r"Board info: (\S+)",
    "uboot_banner": r"(U-Boot SPL \S+ \(.*?\))",
    "apll": r"apll_freq = (\d+)",
    "mpll": r"mpll_freq = (\d+)",
    "vpll": r"vpll_freq = (\d+)",
    "cclk": r"cclk\s+(\d+)",
    "l2clk": r"l2clk (\d+)",
    "h0clk": r"h0clk (\d+)",
    "h2clk": r"h2clk (\d+)",
    "pclk_spl": r"pclk\s+(\d+)",
    "ddr_spl": r"[Dd][Dd][Rr] clk rate (\d+)",
    "kernel_cclocks": r"CCLK:(\d+)MHz L2CLK:(\d+)Mhz H0CLK:(\d+)MHz H2CLK:(\d+)Mhz PCLK:(\d+)Mhz",
    "isp_clk_param": r"isp_clk=(\d+)",
    "isp_clka_param": r"isp_clka=(\d+)",
    "isp_clks_param": r"isp_clks=(\d+)",
    "avpu_clk_param": r"avpu_clk=(\d+)",
    "clk_name_param": r"clk_name=(\S+)",
    "tnpu": r"tnna_clk=(\d+)MHz",
}


def parse(text):
    facts = {}
    for name, pat in PATTERNS.items():
        m = re.search(pat, text)
        if m:
            if name == "kernel_cclocks":
                cclk, l2, h0, h2, pclk = m.groups()
                facts.update(kernel_cclk=int(cclk), kernel_l2clk=int(l2),
                             kernel_h0clk=int(h0), kernel_h2clk=int(h2),
                             kernel_pclk=int(pclk))
            else:
                facts[name] = m.group(1)
    return facts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    text = open(sys.argv[1], errors="replace").read()
    for k, v in parse(text).items():
        print(f"{k}={v}")
