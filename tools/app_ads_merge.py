#!/usr/bin/env python3
"""
app_ads_merge.py
Merges missing lines into an existing app-ads.txt content, preserving comments and basic formatting.
- Input: existing app-ads.txt (file path), file with "lines to add" (as produced by checker), output path.

Usage:
  python tools/app_ads_merge.py --in app-ads.txt --add out/studio-a_example_missing.txt --out updated_app-ads.txt
"""
import argparse, re

ENTRY_RE = re.compile(r'^\s*([^,#\s]+)\s*,\s*([^,#\s]+)\s*,\s*(DIRECT|RESELLER)\s*(?:,\s*([A-Za-z0-9]+))?\s*$')

def load_entries(path):
    entries = set()
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            lines.append(raw.rstrip("\n"))
            m = ENTRY_RE.match(raw)
            if m:
                system, pubid, rel, caid = m.group(1,2,3,4)
                entries.add((system.lower(), pubid, rel.upper(), (caid or '').lower()))
    return lines, entries

def fmt(e):
    system, pubid, rel, caid = e
    return f"{system}, {pubid}, {rel}" + (f", {caid}" if caid else "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--add", dest="addfile", required=True)
    ap.add_argument("--out", dest="outfile", required=True)
    args = ap.parse_args()

    orig_lines, orig_set = load_entries(args.infile)
    _, add_set = load_entries(args.addfile)

    to_add = sorted(list(add_set - orig_set), key=lambda x:(x[0],x[1],x[2],x[3]))

    with open(args.outfile, "w", encoding="utf-8") as out:
        out.write("\n".join(orig_lines).rstrip() + "\n")
        if to_add:
            out.write("\n# --- Added via tool ---\n")
            for e in to_add:
                out.write(fmt(e) + "\n")

    print(f"Wrote {args.outfile}. Added {len(to_add)} line(s).")

if __name__ == "__main__":
    main()
