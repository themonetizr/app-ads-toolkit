#!/usr/bin/env python3
"""
app_ads_update.py
Merges partner-supplied app-ads lines from /data/partners/*.txt into master_app_ads.txt.
- Validates syntax
- Dedupes
- Sorts consistently
- Detects CAID conflicts (same system/pubid/rel but different non-empty CAIDs)
- Writes JSON/Markdown report to --report

Usage:
  python tools/app_ads_update.py --partners_dir data/partners --master data/master_app_ads.txt --out data/master_app_ads.txt --report out
  python tools/app_ads_update.py --partners_dir data/partners --master data/master_app_ads.txt --dry-run --report out
"""
import argparse, os, re, json, datetime, glob

LINE_RE  = re.compile(r'^\s*([#].*)?$')
ENTRY_RE = re.compile(r'^\s*([^,#\s]+)\s*,\s*([^,#\s]+)\s*,\s*(DIRECT|RESELLER)\s*(?:,\s*([A-Za-z0-9]+))?\s*$')

def parse_entries_from_text(text):
    entries, invalid = [], []
    for raw in text.splitlines():
        if LINE_RE.match(raw):
            continue
        m = ENTRY_RE.match(raw)
        if m:
            system, pubid, rel, caid = m.group(1,2,3,4)
            entries.append((system.lower(), pubid, rel.upper(), (caid or '').lower()))
        else:
            invalid.append(raw.strip())
    return entries, invalid

def load_entries_from_file(path):
    if not os.path.exists(path):
        return [], []
    with open(path, 'r', encoding='utf-8') as f:
        return parse_entries_from_text(f.read())

def load_master(path):
    return load_entries_from_file(path)

def fmt(e):
    system, pubid, rel, caid = e
    return f"{system}, {pubid}, {rel}" + (f", {caid}" if caid else "")

def write_master(path, entries):
    header = (
        "# Monetizr — app-ads.txt master list (SOURCE OF TRUTH)\n"
        "# Format: <ad system domain>, <publisher account id>, <relationship>, <cert auth id - optional>\n"
        "# Lines below are auto-normalized. Keep alphabetized and deduplicated.\n"
        "# ----- BEGIN AUTHORIZED LINES -----\n"
    )
    body = "\n".join(fmt(e) for e in entries)
    footer = "\n# ----- END AUTHORIZED LINES -----\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + body + footer)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partners_dir", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", help="Write updated master here (default: overwrite --master)")
    ap.add_argument("--report", default="out", help="Dir for update_report.json/.md")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.report, exist_ok=True)

    # Load master
    master_entries, invalid_master = load_master(args.master)
    master_set = set(master_entries)

    # Track CAID conflicts by key (system,pubid,rel)
    by_key = {}
    for (sysd, pid, rel, caid) in master_entries:
        by_key.setdefault((sysd, pid, rel), set()).add(caid)

    partner_files = sorted(glob.glob(os.path.join(args.partners_dir, "*.txt")))
    duplicates, conflicts, invalid_lines = [], [], []

    # Scan partner files and detect conflicts/dupes
    for pf in partner_files:
        ents, bads = load_entries_from_file(pf)
        invalid_lines += [(os.path.basename(pf), line) for line in bads]
        for e in ents:
            if e in master_set:
                duplicates.append((os.path.basename(pf), fmt(e)))
            k = (e[0], e[1], e[2])
            caids = by_key.setdefault(k, set())
            if e[3]:
                if caids and (e[3] not in caids) and any(x for x in caids if x):
                    conflicts.append((os.path.basename(pf), fmt(e), sorted(list(caids))))
                caids.add(e[3])

    # Merge
    merged = set(master_set)
    for pf in partner_files:
        ents, _ = load_entries_from_file(pf)
        merged.update(ents)

    merged = sorted(merged, key=lambda x:(x[0], x[1], x[2], x[3]))
    added  = [e for e in merged if e not in master_set]
    out_path = args.out or args.master

    if not args.dry_run:
        write_master(out_path, merged)

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat()+"Z",
        "partners_dir": args.partners_dir,
        "master_in": args.master,
        "master_out": out_path,
        "dry_run": args.dry_run,
        "stats": {
            "master_count_before": len(master_entries),
            "master_count_after": len(merged),
            "newly_added": len(added),
            "duplicates": len(duplicates),
            "invalid_lines": len(invalid_lines),
            "conflicts": len(conflicts)
        },
        "added": [fmt(e) for e in added],
        "duplicates": [{"file":f, "line":line} for (f,line) in duplicates],
        "invalid_lines": [{"file":f, "raw":raw} for (f,raw) in invalid_lines],
        "conflicts": [{"file":f, "line":line, "existing_caids":existing} for (f,line,existing) in conflicts]
    }

    with open(os.path.join(args.report, "update_report.json"), "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2)

    md = []
    md.append("# app-ads Master Update Report")
    md.append(f"_Generated: {report['generated_at']}_\n")
    md.append(f"- Master before: **{report['stats']['master_count_before']}** lines")
    md.append(f"- Master after: **{report['stats']['master_count_after']}** lines")
    md.append(f"- Newly added: **{report['stats']['newly_added']}**")
    md.append(f"- Duplicates (already in master): **{report['stats']['duplicates']}**")
    md.append(f"- Invalid lines: **{report['stats']['invalid_lines']}**")
    md.append(f"- CAID conflicts: **{report['stats']['conflicts']}**\n")

    if report["added"]:
        md.append("## Added lines")
        for line in report["added"][:200]:
            md.append(f"- `{line}`")
        if len(report["added"]) > 200:
            md.append(f"... and {len(report['added'])-200} more")
    else:
        md.append("## Added lines\n- None")

    if report["duplicates"]:
        md.append("\n## Duplicates (already present)")
        for d in report["duplicates"][:200]:
            md.append(f"- `{d['line']}`  _(from {d['file']})_")
        if len(report["duplicates"]) > 200:
            md.append(f"... and {len(report['duplicates'])-200} more")

    if report["invalid_lines"]:
        md.append("\n## Invalid lines (syntax issues)")
        for d in report["invalid_lines"][:100]:
            md.append(f"- `{d['raw']}`  _(in {d['file']})_")
        if len(report["invalid_lines"]) > 100:
            md.append(f"... and {len(report['invalid_lines'])-100} more")

    if report["conflicts"]:
        md.append("\n## CAID conflicts (same system/pubid/rel, different CAID)")
        for c in report["conflicts"][:100]:
            md.append(f"- `{c['line']}`  vs existing CAIDs: {', '.join(c['existing_caids'])} _(from {c['file']})_")
        if len(report["conflicts"]) > 100:
            md.append(f"... and {len(report['conflicts'])-100} more")

    with open(os.path.join(args.report, "update_report.md"), "w", encoding="utf-8") as mf:
        mf.write("\n".join(md))

    print("Update complete. Report written to:", args.report)

if __name__ == "__main__":
    main()
