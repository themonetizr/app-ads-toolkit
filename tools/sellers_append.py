#!/usr/bin/env python3
"""
sellers_append.py

Goal:
- Take existing sellers.json (base)
- Take generated sellers.new.json (candidate)
- Append ONLY new sellers (by seller_id) from candidate into base
- Do NOT remove or modify existing sellers
- If anything was appended, bump the MINOR version number (X.Y -> X.(Y+1))
- Write updated sellers.json
- Emit a summary of what was added

Usage:
  python tools/sellers_append.py \
    --base data/sellers.json \
    --candidate data/sellers.new.json \
    --out data/sellers.json \
    --summary_dir out
"""

import argparse, json, os

def load_json(path, required=True):
    if not os.path.exists(path):
        if required:
            raise FileNotFoundError(path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def bump_minor(version_str: str) -> str:
    try:
        parts = version_str.split(".")
        if len(parts) < 2:
            # if weird format, just return as-is
            return version_str
        major = int(parts[0])
        minor = int(parts[1])
        minor += 1
        return f"{major}.{minor}"
    except Exception:
        # if parse fails, don't mutate version
        return version_str

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="Existing sellers.json")
    ap.add_argument("--candidate", required=True, help="Generated sellers.new.json")
    ap.add_argument("--out", required=True, help="Where to write the updated sellers.json")
    ap.add_argument("--summary_dir", default="out", help="Directory to write summary files")
    args = ap.parse_args()

    os.makedirs(args.summary_dir, exist_ok=True)

    base = load_json(args.base)
    cand = load_json(args.candidate)

    if "sellers" not in base or not isinstance(base["sellers"], list):
        raise ValueError("Base sellers.json missing 'sellers' list")
    if "sellers" not in cand or not isinstance(cand["sellers"], list):
        raise ValueError("Candidate sellers.new.json missing 'sellers' list")

    base_by_id = {str(s["seller_id"]).strip(): s for s in base["sellers"] if "seller_id" in s}
    cand_by_id = {str(s["seller_id"]).strip(): s for s in cand["sellers"] if "seller_id" in s}

    new_ids = [sid for sid in cand_by_id.keys() if sid and sid not in base_by_id]
    new_sellers = [cand_by_id[sid] for sid in new_ids]

    # Append new sellers
    if new_sellers:
        base["sellers"].extend(new_sellers)
        # bump minor version
        old_version = str(base.get("version", "1.0"))
        new_version = bump_minor(old_version)
        base["version"] = new_version
    else:
        old_version = str(base.get("version", "1.0"))
        new_version = old_version

    # Write updated base -> out
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=2, ensure_ascii=False)

    # Summary file(s)
    summary = {
        "appended_count": len(new_sellers),
        "appended_ids": new_ids,
        "version_before": old_version,
        "version_after": new_version,
    }

    with open(os.path.join(args.summary_dir, "sellers_appended.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Human-readable summary
    lines = []
    lines.append("# sellers.json append summary")
    lines.append(f"- Version before: **{old_version}**")
    lines.append(f"- Version after: **{new_version}**")
    lines.append(f"- New sellers appended: **{len(new_sellers)}**")
    if new_ids:
        lines.append("")
        lines.append("## Appended seller_ids")
        for sid in new_ids:
            lines.append(f"- `{sid}`")
    with open(os.path.join(args.summary_dir, "sellers_appended.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Also print a short summary into the logs
    print(f"Base version: {old_version} -> {new_version}")
    print(f"Appended {len(new_sellers)} new seller(s).")
    if new_ids:
        print("New seller_ids:")
        for sid in new_ids:
            print(" -", sid)

if __name__ == "__main__":
    main()
