#!/usr/bin/env python3
"""
sellers_generate.py
Generate a sellers.json for your ad system (e.g., Monetizr) by joining:
- data/master_app_ads.txt (source of truth)
- optional partner files in data/partners/*.txt
- publisher metadata in data/publishers.csv (name/domain)
- optional overrides in data/publishers_sellers.csv (seller_id/type)

We infer seller_ids from master_app_ads.txt entries where <ad system> == --system_domain.
If master lacks that system, we fall back to data/partners/*.txt.

Usage:
  python tools/sellers_generate.py \
    --system_domain monetizr.com \
    --master data/master_app_ads.txt \
    --publishers data/publishers.csv \
    --partners_dir data/partners \
    --config data/sellers_config.json \
    --out sellers.json
"""
import argparse, csv, json, os, re, glob, datetime
ENTRY_RE = re.compile(r'^\s*([^,#\s]+)\s*,\s*([^,#\s]+)\s*,\s*(DIRECT|RESELLER)\s*(?:,\s*([A-Za-z0-9]+))?\s*$')
LINE_RE  = re.compile(r'^\s*([#].*)?$')

def parse_master(path):
    ids_by_system = {}
    if not os.path.exists(path):
        return ids_by_system
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            if LINE_RE.match(raw): continue
            m = ENTRY_RE.match(raw)
            if not m: continue
            system, pubid, rel, caid = m.group(1,2,3,4)
            system = system.lower()
            ids_by_system.setdefault(system, set()).add(pubid)
    return ids_by_system

def parse_partners(dirpath):
    ids_by_system = {}
    if not dirpath or not os.path.isdir(dirpath): return ids_by_system
    for fp in glob.glob(os.path.join(dirpath, "*.txt")):
        with open(fp, 'r', encoding='utf-8') as f:
            for raw in f:
                if LINE_RE.match(raw): continue
                m = ENTRY_RE.match(raw)
                if not m: continue
                system, pubid, rel, caid = m.group(1,2,3,4)
                system = system.lower()
                ids_by_system.setdefault(system, set()).add(pubid)
    return ids_by_system

def read_publishers(path):
    pubs, by_domain, by_seller = [], {}, {}
    if not path or not os.path.exists(path): return pubs, by_domain, by_seller
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            d = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            pubs.append(d)
            dom = d.get("domain","").lower()
            if dom: by_domain[dom] = d
            sid = d.get("seller_id","")
            if sid: by_seller[sid] = d
    return pubs, by_domain, by_seller

def read_publishers_overrides(path):
    # optional separate mapping file: domain,seller_id,seller_type,name_override
    by_domain = {}
    if not path or not os.path.exists(path): return by_domain
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            d = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            dom = d.get("domain","").lower()
            if dom: by_domain[dom] = d
    return by_domain

def load_config(path):
    cfg = {
        "contact_email": "",
        "organization_name": "",
        "organization_domain": "",
        "seller_type_default": "PUBLISHER",
        "is_confidential_default": 0
    }
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f); cfg.update({k:v for k,v in user.items() if k in cfg})
    return cfg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system_domain", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--publishers", default="data/publishers.csv")
    ap.add_argument("--publishers_overrides", default="data/publishers_sellers.csv")
    ap.add_argument("--partners_dir", default="data/partners")
    ap.add_argument("--config", default="data/sellers_config.json")
    ap.add_argument("--out", default="sellers.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    ids_by_system = parse_master(args.master)

    if args.system_domain.lower() not in ids_by_system:
        partner_ids = parse_partners(args.partners_dir)
        for k,v in partner_ids.items():
            ids_by_system.setdefault(k, set()).update(v)

    seller_ids = sorted(ids_by_system.get(args.system_domain.lower(), set()))
    pubs, pubs_by_domain, pubs_by_seller = read_publishers(args.publishers)
    overrides = read_publishers_overrides(args.publishers_overrides)

    sellers = []
    for sid in seller_ids:
        meta = pubs_by_seller.get(sid, {})
        name = meta.get("publisher_name") or meta.get("name") or f"Publisher {sid}"
        domain = (meta.get("domain") or "").lower()

        if domain and domain in overrides:
            od = overrides[domain]
            name = od.get("name_override") or name
            sid_override = od.get("seller_id","").strip()
            if sid_override: sid = sid_override
            seller_type = (od.get("seller_type") or "").upper() or cfg["seller_type_default"]
        else:
            seller_type = (meta.get("seller_type") or "").upper() or cfg["seller_type_default"]

        sellers.append({
            "seller_id": sid,
            "name": name,
            "domain": domain,
            "seller_type": seller_type,
            "is_confidential": int(cfg["is_confidential_default"])
        })

    out = {
        "version": "1.0",
        "contact_email": cfg["contact_email"],
        "organization_name": cfg["organization_name"],
        "organization_domain": cfg["organization_domain"],
        "generated_at": datetime.datetime.utcnow().isoformat()+"Z",
        "sellers": sellers
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {args.out} with {len(sellers)} sellers.")

if __name__ == "__main__":
    main()
