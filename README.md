# Monetizr app-ads.txt Toolkit

This mini-toolkit helps you (1) keep every publisher's `app-ads.txt` in sync with a central **source of truth**, and (2) safely add missing lines.

## Files
- `data/master_app_ads.txt` — your master list (source of truth). Keep it deduped and alphabetized.
- `data/publishers.csv` — list of publisher domains to check (one row per `app-ads.txt` host).
- `tools/app_ads_checker.py` — fetches and compares, outputs Markdown/JSON reports + per-publisher patch files.
- `tools/app_ads_merge.py` — merges a missing-lines patch into a local `app-ads.txt` file.
- `.github/workflows/appads-check.yml` — optional GitHub Action to run nightly and attach the report.

## Quick start (web)
1. Adding lines to app-ads.txt
   - Add partner file to `data/partners/` named afer the partner in app-ads.txt format.
   - Go to Actions tab and run `appads-check.yml` on the main branch.
   - Set of reports will be produced
      -  `update_report.json` explains manipulations done on the `data/master_app_ads.txt`
      -  `report.json` reviews partner app-ads.txt files and compares with our document
      -  `[partner]_cc_missing.txt` is specific file to send to publishers for app-ads.txt line update needed. 

## Quick start (local)
```bash
cd app-ads-toolkit
python3 tools/app_ads_checker.py --publishers data/publishers.csv --master data/master_app_ads.txt --out out
# See out/report.md and per-domain *_missing.txt patch files
```

To **apply** missing lines to a local text file you control:
```bash
python3 tools/app_ads_merge.py --in path/to/app-ads.txt --add out/<domain>_missing.txt --out path/to/app-ads.updated.txt
```

## Suggested process
1. Maintain `data/master_app_ads.txt` in a repo. Require *all* new partner line requests to include:
   - ad system domain,
   - publisher account ID,
   - relationship (`DIRECT` or `RESELLER`),
   - certification authority ID (if provided by the exchange).
2. Validate new requests (syntax + whois/domain sanity check) before merging into master.
3. Run the checker (manually or via GitHub Actions). Send each publisher the small patch file for their domain.
4. Re-run until all show **OK** in the report.

## Tips
- The script accepts both HTTPS and HTTP and follows standard hosting at `/<app-ads.txt>`.
- Lines with comments/blank spaces are ignored; duplicates are deduped.
- Keep "DIRECT" vs "RESELLER" accurate — that's a frequent audit failure.
- Sorting/consistency in master makes reviews fast.
