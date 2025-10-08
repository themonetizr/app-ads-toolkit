#!/usr/bin/env python3
"""
app_ads_checker.py
Fetches app-ads.txt from each publisher domain and compares it against the master source-of-truth.
Outputs a JSON and Markdown report including per-publisher diffs.

Usage:
  python tools/app_ads_checker.py --publishers data/publishers.csv --master data/master_app_ads.txt --out out

No external deps required.
"""
import argparse, csv, datetime, hashlib, json, os, re, sys, urllib.request

LINE_RE = re.compile(r'^\s*([#].*)?$')  # comment or blank
ENTRY_RE = re.compile(r'^\s*([^,#\s]+)\s*,\s*([^,#\s]+)\s*,\s*(DIRECT|RESELLER)\s*(?:,\s*([A-Za-z0-9]+))?\s*$')

def load_master(path):
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            if LINE_RE.match(raw):
                continue
            m = ENTRY_RE.match(raw)
            if m:
                system, pubid, rel, caid = m.group(1,2,3,4)
                lines.append((system.lower(), pubid, rel.upper(), (caid or '').lower()))
    # dedupe + sort
    lines = sorted(set(lines), key=lambda x:(x[0], x[1], x[2], x[3]))
    return lines

def fetch_app_ads_txt(host, path):
    url_http = f"http://{host}{path}"
    url_https = f"https://{host}{path}"
    last_err = None
    for url in (url_https, url_http):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                content = resp.read().decode('utf-8', errors='replace')
                return url, content
        except Exception as e:
            last_err = str(e)
    return None, None

def parse_entries(text):
    entries = []
    if text is None:
        return entries
    for line in text.splitlines():
        if LINE_RE.match(line):
            continue
        m = ENTRY_RE.match(line)
        if m:
            system, pubid, rel, caid = m.group(1,2,3,4)
            entries.append((system.lower(), pubid, rel.upper(), (caid or '').lower()))
    # dedupe
    entries = sorted(set(entries), key=lambda x:(x[0], x[1], x[2], x[3]))
    return entries

def format_entry(e):
    system, pubid, rel, caid = e
    return f"{system}, {pubid}, {rel}" + (f", {caid}" if caid else "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publishers", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    master = load_master(args.master)
    master_set = set(master)

    rows = []
    with open(args.publishers, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    summary = {
        "generated_at": datetime.datetime.utcnow().isoformat()+"Z",
        "total_publishers": len(rows),
        "ok": 0, "missing": 0, "errors": 0,
        "publishers": []
    }

    for r in rows:
        domain = r["domain"].strip()
        path = (r.get("app_ads_path") or "/app-ads.txt").strip() or "/app-ads.txt"
        name = r.get("publisher_name","").strip() or domain
        notes = r.get("notes","").strip()

        url, content = fetch_app_ads_txt(domain, path)
        if not content:
            summary["errors"] += 1
            summary["publishers"].append({
                "name": name, "domain": domain, "url": url, "status": "ERROR_FETCHING",
                "notes": notes, "missing_lines": [], "extra_lines": [], "current_count": 0
            })
            continue

        current = parse_entries(content)
        current_set = set(current)

        missing = sorted(list(master_set - current_set), key=lambda x:(x[0],x[1],x[2],x[3]))
        extra = sorted(list(current_set - master_set), key=lambda x:(x[0],x[1],x[2],x[3]))

        status = "OK" if not missing else "MISSING"
        summary["ok" if status=="OK" else "missing"] += 1

        pub_report = {
            "name": name, "domain": domain, "url": url, "status": status, "notes": notes,
            "current_count": len(current), 
            "missing_lines": [format_entry(e) for e in missing],
            "extra_lines": [format_entry(e) for e in extra]
        }
        summary["publishers"].append(pub_report)

        # write per-publisher suggested patch
        patch_path = os.path.join(args.out, f"{domain.replace('.', '_')}_missing.txt")
        with open(patch_path, "w", encoding="utf-8") as pf:
            if missing:
                pf.write("# Lines to ADD to this publisher's app-ads.txt to match master\n")
                for e in missing:
                    pf.write(format_entry(e) + "\n")
            else:
                pf.write("# No missing lines — already in sync.\n")

    # Write JSON + Markdown reports
    with open(os.path.join(args.out,"report.json"), "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=2)

    md = ["# app-ads.txt Compliance Report",
          f"_Generated: {summary['generated_at']}_",
          "",
          f"- Publishers checked: **{summary['total_publishers']}**",
          f"- In sync: **{summary['ok']}**",
          f"- Out of sync: **{summary['missing']}**",
          f"- Errors: **{summary['errors']}**",
          "",
          "| Publisher | Domain | Status | Current lines | URL | Notes |",
          "|---|---|---|---:|---|---|"]
    for p in summary["publishers"]:
        md.append(f"| {p['name']} | {p['domain']} | {p['status']} | {p['current_count']} | {p.get('url','–')} | {p.get('notes','')} |")
    md.append("\n## Details\n")
    for p in summary["publishers"]:
        md.append(f"### {p['name']} ({p['domain']}) — {p['status']}")
        md.append(f"- URL: {p.get('url','–')}")
        if p["missing_lines"]:
            md.append("**Missing lines to add:**")
            md.extend([f"- `{line}`" for line in p["missing_lines"]])
        else:
            md.append("**Missing lines to add:** None.")
        if p["extra_lines"]:
            md.append("**Extra lines present (not in master):**")
            md.extend([f"- `{line}`" for line in p["extra_lines"]])
        else:
            md.append("**Extra lines present:** None.")
        md.append("")
    with open(os.path.join(args.out,"report.md"), "w", encoding="utf-8") as mf:
        mf.write("\n".join(md))

    print("Done. Reports written to:", args.out)

if __name__ == "__main__":
    main()
