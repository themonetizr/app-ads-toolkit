#!/usr/bin/env python3
"""
sellers_validate.py

Validate a sellers.json file against the IAB Tech Lab Sellers.json spec:
https://iabtechlab.com/wp-content/uploads/2019/07/Sellers.json_Final.pdf

Checks:

Top-level (Parent object):
- JSON is an object
- "sellers" exists and is a list (REQUIRED)
- "version" exists and is a string (REQUIRED; spec says only '1.0' is valid)
- Optional: contact_email, contact_address, identifiers[], ext

Seller objects:
- seller_id: required, non-empty string
- seller_type: required, must be PUBLISHER / INTERMEDIARY / BOTH (case-insensitive)
- is_confidential: optional, must be 0 or 1 if present
- is_passthrough: optional, must be 0 or 1 if present
- name: required when is_confidential != 1
- domain: required if is_confidential != 1 AND provided (we can't know "no web presence",
          but we validate format when present: no scheme, no path)
- seller_id must be unique across all sellers

Exit codes:
- 0 = OK (no errors, possibly warnings)
- 1 = INVALID (spec violations)
"""

import argparse
import json
import os
import sys
import re

VALID_TYPES = {"PUBLISHER", "INTERMEDIARY", "BOTH"}

DOMAIN_BAD_CHARS = re.compile(r"\s|/|:")

def load_json(path: str):
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to parse JSON from {path}: {e}")
        sys.exit(1)

def validate_parent(obj, errors, warnings):
    if not isinstance(obj, dict):
        errors.append("Top-level JSON must be an object.")
        return

    # sellers (required)
    if "sellers" not in obj:
        errors.append('Missing required top-level key: "sellers"')
    elif not isinstance(obj["sellers"], list):
        errors.append('Top-level "sellers" must be a JSON array.')

    # version (required)
    if "version" not in obj:
        errors.append('Missing required top-level key: "version"')
    elif not isinstance(obj["version"], str):
        errors.append('Top-level "version" must be a string.')
    else:
        # Strict spec: only "1.0" is valid
        if obj["version"] != "1.0":
            warnings.append(
                f'Top-level "version" is "{obj["version"]}", but spec 1.0 says the only valid value is "1.0".'
            )

    # identifiers (optional)
    if "identifiers" in obj:
        if not isinstance(obj["identifiers"], list):
            errors.append('"identifiers" must be an array if present.')
        else:
            for i, ident in enumerate(obj["identifiers"]):
                if not isinstance(ident, dict):
                    errors.append(f'identifiers[{i}] must be an object.')
                    continue
                if "name" not in ident or not str(ident["name"]).strip():
                    errors.append(f'identifiers[{i}]: missing required "name".')
                if "value" not in ident or not str(ident["value"]).strip():
                    errors.append(f'identifiers[{i}]: missing required "value".')

def validate_sellers(obj, errors, warnings):
    sellers = obj.get("sellers", [])
    if not isinstance(sellers, list):
        return

    seen_ids = set()

    for idx, s in enumerate(sellers):
        path = f"sellers[{idx}]"

        if not isinstance(s, dict):
            errors.append(f"{path} must be an object.")
            continue

        # seller_id
        seller_id = str(s.get("seller_id", "")).strip()
        if not seller_id:
            errors.append(f'{path}: missing or empty required field "seller_id".')
        else:
            if seller_id in seen_ids:
                errors.append(f"{path}: duplicate seller_id '{seller_id}'.")
            seen_ids.add(seller_id)

        # seller_type
        st = str(s.get("seller_type", "")).upper()
        if not st:
            errors.append(f'{path}: missing required field "seller_type".')
        elif st not in VALID_TYPES:
            errors.append(
                f'{path}: invalid seller_type "{s.get("seller_type")}", must be one of {sorted(VALID_TYPES)}.'
            )

        # is_confidential
        is_conf = s.get("is_confidential", 0)
        if is_conf not in (0, 1, "0", "1"):
            errors.append(
                f'{path}: "is_confidential" must be 0 or 1 if present (got {is_conf}).'
            )
        is_conf_val = int(is_conf) if str(is_conf).isdigit() else 0

        # is_passthrough
        if "is_passthrough" in s:
            ip = s["is_passthrough"]
            if ip not in (0, 1, "0", "1"):
                errors.append(
                    f'{path}: "is_passthrough" must be 0 or 1 if present (got {ip}).'
                )

        # name (required when non-confidential)
        name = s.get("name")
        if is_conf_val == 0:
            if not name or not str(name).strip():
                errors.append(
                    f'{path}: "name" is required when is_confidential != 1.'
                )

        # domain
        domain = s.get("domain")
        if domain is not None:
            d = str(domain).strip()
            if not d:
                errors.append(f'{path}: "domain" is empty string.')
            else:
                # spec: root domain only (no scheme, no path); we do basic heuristic
                if DOMAIN_BAD_CHARS.search(d):
                    warnings.append(
                        f'{path}: "domain" looks suspicious ("{d}"). It should be a root domain (no scheme, no path).'
                    )
                if d.startswith("http://") or d.startswith("https://"):
                    warnings.append(
                        f'{path}: "domain" should not contain scheme, only root domain (e.g. example.com).'
                    )
        else:
            # spec: domain required if has web presence and non-confidential. We cannot
            # know "web presence", but we can warn when missing.
            if is_conf_val == 0:
                warnings.append(
                    f'{path}: no "domain" set while is_confidential=0. If this seller has a web presence, domain is required by spec.'
                )

def validate_sellers_json(path: str):
    errors = []
    warnings = []

    data = load_json(path)
    validate_parent(data, errors, warnings)
    validate_sellers(data, errors, warnings)

    if errors:
        print("RESULT: INVALID ❌")
        print("Errors:")
        for e in errors:
            print(" -", e)
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(" -", w)
        sys.exit(1)
    else:
        print("RESULT: VALID ✅")
        if warnings:
            print("With warnings:")
            for w in warnings:
                print(" -", w)
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Validate sellers.json against IAB spec.")
    parser.add_argument(
        "--file",
        default="data/sellers.json",
        help="Path to sellers.json (default: data/sellers.json)",
    )
    args = parser.parse_args()
    validate_sellers_json(args.file)

if __name__ == "__main__":
    main()
