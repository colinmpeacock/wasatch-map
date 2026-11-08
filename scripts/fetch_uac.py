#!/usr/bin/env python3
"""Fetch Utah Avalanche Center forecasts and save them for the Wasatch Backcountry Planner.

Uses UAC's documented JSON endpoint, https://utahavalanchecenter.org/forecast/<region>/json
(docs: https://utahavalanchecenter.org/docs/api/forecast). UAC asks every client to send a
custom User-Agent with contact details, and to poll gently (forecasts come out 5-8 AM).

Writes:
  <out>/latest.json      one normalized file with every region (what the map reads)
  <out>/raw/<region>.json  the untouched UAC response, for debugging

Standard library only, so it runs in a GitHub Action or on your own computer:
  python fetch_uac.py --contact "you@example.com" --site "https://github.com/you/wasatch-map"
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REGIONS = ["salt-lake", "provo", "ogden", "uintas", "logan", "skyline", "moab", "abajos", "southwest"]
BASE_URL = "https://utahavalanchecenter.org/forecast/{region}/json"
PAGE_URL = "https://utahavalanchecenter.org/forecast/{region}"
DANGER_WORDS = {0: "No rating", 1: "Pockets of low", 2: "Low", 3: "Pockets of moderate", 4: "Moderate",
                5: "Pockets of considerable", 6: "Considerable", 7: "Pockets of high", 8: "High",
                9: "Pockets of extreme", 10: "Extreme"}


def clean_text(value):
    """UAC text fields are plain text with \\r line breaks, stray &nbsp; and the odd HTML tag."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_rose(value):
    """A rose is a CSV string of 24 integers: upper band N..NW, then mid, then low."""
    if isinstance(value, list):
        parts = value
    elif isinstance(value, str) and value.strip():
        parts = value.split(",")
    else:
        return None
    try:
        nums = [int(float(p)) for p in parts]
    except (TypeError, ValueError):
        return None
    return nums if len(nums) == 24 else None


def problem_mask(rose):
    """Problem locator roses only mark where a problem sits; the numbers themselves carry no meaning.
    UAC uses two values per rose (e.g. 16 = problem here, 14 = not here), so the higher value marks it."""
    if not rose:
        return None
    values = sorted(set(rose))
    if len(values) == 1:
        # A uniform rose: every cell is marked only if it carries the "marked" value seen in current data.
        return [values[0] >= 16] * 24
    hi = values[-1]
    return [v == hi for v in rose]


def normalize(region, payload):
    advisories = (payload or {}).get("advisories") or []
    if not advisories:
        return {"region_slug": region, "available": False, "reason": "No forecast in the response (off season?)"}
    adv = advisories[0].get("advisory") or {}
    rose = parse_rose(adv.get("overall_danger_rose"))
    ts = adv.get("date_issued_timestamp")
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        ts = None
    problems = []
    for n in (1, 2, 3):
        name = clean_text(adv.get(f"avalanche_problem_{n}"))
        if not name:
            continue
        locator = parse_rose(adv.get(f"danger_rose_{n}"))
        problems.append({
            "name": name,
            "description": clean_text(adv.get(f"avalanche_problem_{n}_description")),
            "where": problem_mask(locator),
        })
    return {
        "region_slug": region,
        "available": rose is not None,
        "region": clean_text(adv.get("region")) or region.replace("-", " ").title(),
        "issued": clean_text(adv.get("date_issued")),
        "issued_ts": ts,
        "rating": clean_text(adv.get("overall_danger_rating")),
        "rose": rose,
        "rose_labels": [DANGER_WORDS.get(v, str(v)) for v in rose] if rose else None,
        "problems": problems,
        "bottom_line": clean_text(adv.get("bottom_line")),
        "current_conditions": clean_text(adv.get("current_conditions")),
        "recent_activity": clean_text(adv.get("recent_activity")),
        "url": PAGE_URL.format(region=region),
        "node_id": clean_text(adv.get("Nid")),
    }


def fetch_json(url, user_agent, timeout=20, tries=2):
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            return json.loads(body.decode("utf-8-sig"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/uac", help="output folder (default data/uac)")
    ap.add_argument("--regions", default=",".join(REGIONS), help="comma-separated region slugs")
    ap.add_argument("--contact", default=os.environ.get("UAC_CONTACT", ""),
                    help="contact email for the User-Agent UAC asks for (or set UAC_CONTACT)")
    ap.add_argument("--site", default=os.environ.get("UAC_SITE", ""),
                    help="URL of your project, added to the User-Agent (or set UAC_SITE)")
    ap.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)  # for testing
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between regions")
    args = ap.parse_args(argv)

    if not args.contact and not args.site:
        ap.error("UAC asks for contact details in the User-Agent: pass --contact and/or --site "
                 "(or set UAC_CONTACT / UAC_SITE).")
    ua_bits = ["WasatchBackcountryPlanner/1.0"]
    detail = "; ".join(b for b in [f"+{args.site}" if args.site else "", args.contact] if b)
    user_agent = f"{ua_bits[0]} ({detail})"

    os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
    latest_path = os.path.join(args.out, "latest.json")
    try:
        with open(latest_path, encoding="utf-8") as f:
            previous = json.load(f)
    except (OSError, json.JSONDecodeError):
        previous = {}
    prev_regions = previous.get("regions", {})

    regions, errors, changed = {}, {}, False
    slugs = [s.strip() for s in args.regions.split(",") if s.strip()]
    for i, slug in enumerate(slugs):
        if i:
            time.sleep(args.delay)
        try:
            payload = fetch_json(args.base_url.format(region=slug), user_agent)
        except Exception as e:  # keep the last good copy for this region
            errors[slug] = str(e)[:300]
            if slug in prev_regions:
                regions[slug] = prev_regions[slug]
            print(f"! {slug}: {e}", file=sys.stderr)
            continue
        with open(os.path.join(args.out, "raw", f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        entry = normalize(slug, payload)
        old = prev_regions.get(slug)
        if old and {k: v for k, v in old.items() if k != "fetched"} == entry:
            entry["fetched"] = old.get("fetched")
        else:
            entry["fetched"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            changed = True
        regions[slug] = entry
        print(f"  {slug}: {entry.get('rating') or 'no rating'} · {entry.get('issued') or 'not issued'}")

    out = {
        "source": "Utah Avalanche Center (utahavalanchecenter.org)",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds") if changed or not previous
                     else previous.get("generated"),
        "regions": regions,
        "errors": errors,
    }
    if out != previous:
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"wrote {latest_path}")
    else:
        print("no change")
    # Fail the run only when every region failed, so one bad region doesn't turn the Action red.
    return 1 if slugs and len(errors) == len(slugs) else 0


if __name__ == "__main__":
    sys.exit(main())
