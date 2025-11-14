#!/usr/bin/env python3
"""
sellers_check.py
Validate a sellers.json file and cross-check against your master_app_ads.txt.

Checks:
- JSON schema basics
- Required seller fields present
- seller_type in {PUBLISHER, INTERMEDIARY, BOTH}
- Unique seller_id
- Optional: verify each seller_id appears in master_app_ads.txt for --system_domain

Usage:
  python tools/sellers_check.py --sellers sellers.json --master data/master_app_ads.txt --system_domain monetizr.com
"""
import argparse, json, os, re, sys

ENTRY_RE = re.compile(r'^\s*([^,#\s]+)\s*,\s*([^,#\s]+)\s*,\s*(DIRECT|RESELLER)\s*(?:,\s*([A-Za-z0-9]+))?\s*$')
LINE_RE  = re.compile(r'^\s*([#].*)?$')

def parse_master_ids(master_path, system_domain):
    ids = set()
    if not master_path or not os.path.exists(master_path):
        return ids
    with open(master_path, 'r', encoding='utf-8') as f:
        for raw in f:
            if LINE_RE.match(raw): continue
            m = ENTRY_RE.match(raw)
            if not m: continue
            system, pubid, rel, caid = m.group(1,2,3,4)
            if system.lower() == system_domain.lower():
                ids.add(pubid)
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sellers", required=True)
    ap.add_argument("--master", required=False)
    ap.add_argument("--system_domain", required=False, default="")
    args = ap.parse_args()

    errors, warnings = [], []

    if not os.path.exists(args.sellers):
        print("ERROR: sellers.json not found"); sys.exit(2)

    try:
        data = json.load(open(args.sellers, "r", encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: sellers.json invalid JSON: {e}"); sys.exit(2)

    for k in ["version", "contact_email", "organization_name", "organization_domain", "sellers"]:
        if k not in data:
            errors.append(f"Missing top-level key: {k}")

    sellers = data.get("sellers", [])
    if not isinstance(sellers, list):
        errors.append("Top-level 'sellers' must be a list")

    seen_ids = set()
    valid_types = {"PUBLISHER","INTERMEDIARY","BOTH"}
    for i, s in enumerate(sellers):
        path = f"sellers[{i}]"
        for req in ["seller_id","name","seller_type"]:
            if req not in s or not str(s[req]).strip():
                errors.append(f"{path}: missing field '{req}'")
        if s.get("seller_type","").upper() not in valid_types:
            errors.append(f"{path}: invalid seller_type '{s.get('seller_type')}', must be one of {sorted(valid_types)}")
        sid = s.get("seller_id","").strip()
        if sid in seen_ids:
            errors.append(f"{path}: duplicate seller_id '{sid}'")
        seen_ids.add(sid)

    if args.master and args.system_domain:
        master_ids = parse_master_ids(args.master, args.system_domain)
        missing_in_master = [s["seller_id"] for s in sellers if s["seller_id"] not in master_ids]
        if missing_in_master:
            warnings.append(f"{len(missing_in_master)} seller_id(s) not present in master for system '{args.system_domain}': {', '.join(sorted(missing_in_master)[:50])}")

    if errors:
        print("FAILED")
        for e in errors: print(" -", e)
        sys.exit(1)

    print("OK")
    for w in warnings: print("WARN:", w)

if __name__ == "__main__":
    main()
