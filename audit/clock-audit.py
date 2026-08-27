#!/usr/bin/env python3
"""clock-audit.py v4 (final) -- enumerate every camera profile x every
resolve_clock_freq consumer in thingino-firmware, resolve the build-system
output, and compute the on-chip actual AVPU clock.

Scope (full, no sampling): configs/cameras + configs/cameras-exp (225 profiles).

Mechanism (all source-verified):
 - Config.soc.in AVPU Clock Speed: choice, default 400MHz, options 400..700
   incl. 486. AVPU Clock Source: choice, default INTERNAL, options
   APLL/MPLL/SCLKA/VPLL/INTERNAL.
 - thingino.mk resolve_clock_freq map lacks 486 -> BR2_AVPU_CLK_486MHZ=y
   yields EMPTY avpu_clk param -> module compiled-in default 550MHz (silent).
   INTERNAL source -> empty clk_name -> module default clk_name "mpll".
 - avpu driver (SDK 3.10.14): avpu_clk=550000000 default, clk_name="mpll".
 - PLL rates from the 2026.07 U-Boot per-SKU leaf dts:
     * XBurst1 + t31: header comment "/* APLLn MPLLn CPCCR */" is authoritative
       (mnod OD-field encoding varies; OD bits 0 = /1 on t21/t30).
     * a1/t40/t41: mnod triple at cells[7..9] (after type/family, sizes,
       mpll_hz/ddr_hz), vpll mnod 0 = off; cross-check mpll vs mpll_hz.
     * VPLL policy: t31 hard-coded 1200 (T31_VPLL_MNOD), t32 1188, a1 1200,
       t41 per-SKU; t10..t30 + t33 left at reset (1080 measured on stock
       boot T31X -- t31 units on the stock bootloader also sit at 1080).
     * t40 vpll off (APLL+MPLL plan). t33 bins 950/1300 (L) 891/1100 (VL).
 - CDR divider: integer 1..64, rounds DOWN to largest <= requested.
 - t31al (no dts) aliases t31a; family fallbacks t10->t10n etc.

Usage: python3 clock-audit.py [repo] [--tsv out.tsv] [--quiet]
"""
import re, sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else
           "/home/gino/.gino/workspace/thingino-firmware")
TSV = Path(sys.argv[sys.argv.index("--tsv") + 1]) if "--tsv" in sys.argv else None
QUIET = "--quiet" in sys.argv
MHZ = 1_000_000

def rd(p):
    return p.read_text(errors="replace")

# ------------------------------------------------------------ build layer --
mk = rd(ROOT / "thingino.mk")
CONSUMERS = {"IPU_CLK": {}, "AVPU_CLK": {}, "ISP_CLK": {},
             "ISP_CLKA": {}, "ISP_CLKS": {}}
for prefix in CONSUMERS:
    m = re.search(re.escape(prefix) + r"(?:_CLK)?\s*:?=\s*"
                  r"\$\(call resolve_clock_freq," + re.escape(prefix)
                  + r",\w+,(.*?)\)\n", mk, re.S)
    if m:
        cmap = {}
        for pair in m.group(1).split():
            if ":" in pair:
                a, b = pair.split(":")
                cmap[int(a)] = int(b)
        CONSUMERS[prefix] = cmap

SRCMAP = {"APLL": "apll", "MPLL": "mpll", "SCLKA": "sclka", "VPLL": "vpll",
          "INTERNAL": None}     # None -> param absent -> module default mpll

soc_in = rd(ROOT / "Config.soc.in")
KCONF, KDEFLT = {}, {}
for label, prefix in (("AVPU Clock Speed", "AVPU_CLK"),
                      ("ISP Clock Speed", "ISP_CLK"),
                      ("ISP Scaler Clock Speed", "ISP_CLKS"),
                      ("ISP AXI Bus Clock Speed", "ISP_CLKA"),
                      ("IPU Clock Speed", "IPU_CLK")):
    m = re.search(r'choice\s*\n\tprompt "' + re.escape(label) + r'"(.*?)endchoice',
                  soc_in, re.S)
    if m:
        body = m.group(1)
        KCONF[prefix] = sorted(set(
            int(x) for x in re.findall(r"config BR2_" + prefix + r"_(\d+)MHZ", body)))
        d = re.search(r"default BR2_" + prefix + r"_(\d+)MHZ", body)
        if d:
            KDEFLT[prefix] = int(d.group(1))
AVPU_SRC_DFLT = "INTERNAL"
m = re.search(r'choice\s*\n\tprompt "AVPU Clock Source"(.*?)endchoice', soc_in, re.S)
if m:
    d = re.search(r"default (BR2_AVPU_\w+)", m.group(1))
    if d:
        AVPU_SRC_DFLT = d.group(1).replace("BR2_AVPU_", "")

soc_db = {}
for f in (ROOT / "soc" / "ingenic").glob("*.mk"):
    for tok in re.findall(r"\$\(filter \$\(SOC_MODEL\),([^)]+)\)", rd(f)):
        for mm in tok.split():
            soc_db[mm.lower()] = f.stem

# -------------------------------------------------------------- PLL layer --
def decode_mnod(v, zero_od_is_one=True):
    M = (v >> 20) & 0x3FF
    N = (v >> 14) & 0x3F
    od1 = (v >> 11) & 0x7
    od0 = (v >> 8) & 0x7
    if zero_od_is_one:
        od1 = od1 or 1
        od0 = od0 or 1
    if not N or not M:
        return None
    return 24 * M / (N * od0 * od1)

MODERN = {}
patch = rd(ROOT / "package" / "all-patches" / "uboot" / "2026.07" /
           "0001-uboot-master.patch")
for m in re.finditer(
        r"diff --git a/arch/mips/dts/([\w-]+)-isvp(?:-[\w-]+)?\.dts b/[^\n]*\n"
        r"(?:new file[^\n]*\n)?index [^\n]*\n--- [^\n]*\n\+\+\+ [^\n]*\n"
        r"@@[^\n]*\n((?:\+.*\n)+)", patch):
    sku = m.group(1).lower()
    body = m.group(2)
    mm = re.search(r"sdram-params = <\n((?:\+.*\n)+?)\+\s*>", body)
    if not mm:
        continue
    cells = []
    for ln in mm.group(1).splitlines():
        for tok in ln.lstrip("+").strip().split():
            if tok.startswith("0x"):
                cells.append(int(tok, 16))
    if len(cells) < 3:
        continue
    plls = {}
    cm = re.search(r"/\* APLL(\d+) MPLL(\d+) CPCCR \*/", body)
    if cm:                                   # XBurst1 + t31: comment authority
        plls["apll"] = float(cm.group(1))
        plls["mpll"] = float(cm.group(2))
    elif re.search(r"/\* apll mpll vpll _mnod \*/", body) and len(cells) > 9:
        plls["apll"] = decode_mnod(cells[7])
        plls["mpll"] = decode_mnod(cells[8])
        plls["vpll"] = decode_mnod(cells[9]) if cells[9] else None
        # cross-check mpll against the mpll_hz word when present
        hz = cells[5] if len(cells) > 5 else 0
        if hz and plls["mpll"] and abs(plls["mpll"] - hz / MHZ) > 8:
            plls["mpll"] = hz / MHZ          # trust explicit Hz field
    if plls:
        MODERN.setdefault(sku, {}).update(plls)

FAMILY_VPLL = {"t31": 1200.0, "t32": 1188.0, "a1": 1200.0}
CHIP_DEFAULT_VPLL = 1080.0                   # t10..t30, t33 (reset value)
T33_BINS = {"apll": 950.0, "mpll": 1300.0}
T40_FALLBACK = {"apll": 1404.0, "mpll": 1000.0}
ALIAS = {"t31al": "t31a", "t31zn": "t31n", "t23zn": "t23n"}
FAM_DTS = {"t10": "t10n", "t20": "t20n", "t21": "t21n", "t23": "t23n",
           "t30": "t30n", "t31": "t31n", "t40": "t40n", "t41": "t41nq"}

def plls_for(model, fam):
    key = ALIAS.get(model, model)
    got = dict(MODERN.get(key) or {})
    if not got:
        got = dict(MODERN.get(FAM_DTS.get(fam, fam)) or {})
    if not got and fam == "t40":
        got = dict(T40_FALLBACK)
    if fam == "t33":
        got.update(T33_BINS)
    if fam in FAMILY_VPLL:
        got.setdefault("vpll", FAMILY_VPLL[fam])
    elif fam in ("t10", "t20", "t21", "t23", "t30"):
        got.setdefault("vpll", CHIP_DEFAULT_VPLL)
    return got

# ------------------------------------------------------------- machinery ---
def divider_round(parent, req):
    if parent is None or req is None:
        return None
    best = None
    for n in range(1, 65):
        v = parent / n
        if v <= req + 1e-9 and (best is None or v > best):
            best = v
    return best

rows, issues = [], []
for base in ("configs/cameras", "configs/cameras-exp"):
    bdir = ROOT / base
    if not bdir.exists():
        continue
    for d in sorted(bdir.iterdir()):
        if not d.is_dir():
            continue
        prof = d.name
        defs = sorted(d.rglob(f"{prof}_defconfig")) or sorted(d.rglob("*_defconfig"))
        if not defs:
            continue
        txt = rd(defs[0])
        model = (re.search(r'BR2_INGENIC_SOC_MODEL="?([\w.]+)"?', txt) or
                 re.search(r'SOC_MODEL="?([\w.]+)"?', txt))
        if not model:
            continue
        model = model.group(1).lower()
        fam = soc_db.get(model, "?")
        plls = plls_for(model, fam)

        av = {}
        if fam in ("t31", "t40", "t41"):
            src_sym = next((s for s in ("APLL", "MPLL", "SCLKA", "VPLL", "INTERNAL")
                            if re.search(r"BR2_AVPU_" + s + r"=y", txt)),
                           AVPU_SRC_DFLT)
            freq = next((int(x) for x in re.findall(r"BR2_AVPU_CLK_(\d+)MHZ=y", txt)),
                        KDEFLT.get("AVPU_CLK"))
            src = SRCMAP.get(src_sym)
            hz = CONSUMERS["AVPU_CLK"].get(freq)
            # effective request: mapped value, else module default 550
            req = (hz / MHZ) if hz else 550.0
            # effective parent: chosen src; INTERNAL/absent -> module default mpll
            parent_key = src if src else "mpll"
            parent = plls.get(parent_key)
            actual = divider_round(parent, req)
            old = (divider_round(CHIP_DEFAULT_VPLL, req)
                   if fam == "t31" and parent_key == "vpll" else None)
            av = {"src_sym": src_sym, "src": src, "req_mhz": freq, "hz": hz,
                  "parent": parent_key, "parent_mhz": parent,
                  "req_eff": req, "actual": actual, "old_actual": old}
            tag = "DEFAULT" if (freq == KDEFLT.get("AVPU_CLK")
                                and src_sym == AVPU_SRC_DFLT) else "PINNED"
            if freq is not None and hz is None:
                issues.append(("LAYER1-EMPTY-MAP", prof, fam,
                               f"[{tag}] 486MHz selected, map lacks 486 -> avpu_clk param ABSENT"
                               f" -> module default 550MHz requested"
                               + (f" -> actual {actual:.0f}MHz on {parent_key}"
                                  f"({parent:.0f})" if actual else "")))
            elif hz and parent and actual is not None and abs(actual - req) > 0.01:
                extra = (f"; stock-boot vpll1080 -> {old:.0f}"
                         if old is not None and abs(old - req) > 0.01 else "")
                issues.append(("LAYER2-UNREACHABLE", prof, fam,
                               f"[{tag}] {req:.0f}MHz on {parent_key}({parent:.0f})"
                               f" -> actual {actual:.0f}MHz{extra}"))
            elif hz and parent is None:
                issues.append(("LAYER2-PARENT-OFF", prof, fam,
                               f"[{tag}] {req:.0f}MHz on {parent_key}: PLL not programmed"
                               " by this U-Boot (off)"))
        rows.append({"prof": prof, "base": base, "model": model, "fam": fam,
                     "avpu": av, "plls": plls})

# ------------------------------------------------------------ validation ---
errs = []
if len(rows) < 225:
    errs.append(f"profile count {len(rows)} < 225")
chk = {"t21n": (864.0, 900.0), "t31x": (1392.0, 1200.0), "t31a": (1512.0, 1500.0),
       "t40xp": (1008.0, 1200.0), "a1n": (1104.0, 1608.0), "t41nq": (None, 1400.0)}
for sku, (ea, em) in chk.items():
    v = MODERN.get(sku, {})
    ok = (ea is None or (v.get("apll") and abs(v["apll"] - ea) < 1)) and \
         (em is None or (v.get("mpll") and abs(v["mpll"] - em) < 1))
    if not ok:
        errs.append(f"{sku} PLL anchor failed: {v}")
if divider_round(1080, 550) != 540 or divider_round(1080, 500) != 360:
    errs.append("vpll1080 divider anchors failed")
if divider_round(1200, 550) != 400 or divider_round(1200, 600) != 600:
    errs.append("vpll1200 divider anchors failed")
z55 = next((r for r in rows if r["prof"] == "vanhua_z55_t31x_gc4653_eth"), None)
if not z55:
    errs.append("z55 missing")
else:
    a = z55["avpu"]
    if not (a["req_mhz"] == 486 and a["src_sym"] == "VPLL" and a["hz"] is None
            and a["req_eff"] == 550.0 and a["actual"] == 400.0
            and a["old_actual"] == 540.0):
        errs.append(f"z55 anchor failed: {a}")
n1 = sum(1 for i in issues if i[0] == "LAYER1-EMPTY-MAP")
if n1 != 11:
    errs.append(f"LAYER1 count {n1} != 11")
for prefix in CONSUMERS:
    for gap in sorted(set(KCONF.get(prefix, [])) - set(CONSUMERS[prefix])):
        issues.append(("KCONFIG-MAP-GAP", "<global>", "-",
                       f"BR2_{prefix}_{gap}MHZ selectable but mk map lacks {gap}"))
    for extra in sorted(set(CONSUMERS[prefix]) - set(KCONF.get(prefix, []))):
        issues.append(("MAP-EXTRA", "<global>", "-",
                       f"{prefix} map has {extra}MHz not offered in Kconfig"))

# ---------------------------------------------------------------- output ---
if TSV:
    with TSV.open("w") as f:
        f.write("profile\tfamily\tmodel\tsrc_sym\tsrc_param\treq_mhz\tmap_hz\tparent"
                "\tparent_mhz\treq_eff\tactual_mhz\told_boot_actual\n")
        for r in rows:
            a = r["avpu"] or {}
            f.write("\t".join(str(x) for x in (
                r["prof"], r["fam"], r["model"], a.get("src_sym"), a.get("src"),
                a.get("req_mhz"), a.get("hz"), a.get("parent"),
                a.get("parent_mhz"), a.get("req_eff"), a.get("actual"),
                a.get("old_actual"))) + "\n")

if not QUIET:
    print(f"# profiles: {len(rows)}   U-Boot 2026.07 (default; none pin 2013.07)")
    print(f"# Kconfig defaults: src={AVPU_SRC_DFLT} freq={KDEFLT.get('AVPU_CLK')}MHz;"
          " module defaults: clk_name=mpll avpu_clk=550M")
    print("# per-SKU PLLs (MHz):")
    for k in sorted(MODERN):
        v = MODERN[k]
        print(f"#   {k:10s} apll={v.get('apll')} mpll={v.get('mpll')} vpll={v.get('vpll')}")
    print()
    by = {}
    for it in issues:
        by.setdefault(it[0], []).append(it)
    for cls in sorted(by):
        print(f"== {cls}: {len(by[cls])} ==")
        for _, prof, fam, msg in by[cls]:
            print(f"  {prof} [{fam}] {msg}")
        print()
    if errs:
        print("VALIDATION ERRORS:")
        for e in errs:
            print(" !", e)
        sys.exit(1)
    print("VALIDATION: all anchors passed")
