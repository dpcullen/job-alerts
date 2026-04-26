#!/usr/bin/env python3
"""Daily job alert: scrapes public job boards and emails new relevant postings."""

import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

import requests
import yaml


SEEN_JOBS_FILE = Path("seen_jobs.json")
COMPANIES_FILE = Path("companies.yml")


# ── Exclusion filters ─────────────────────────────────────────────────────────
# Any job title containing one of these words is removed from the email.
# Edit this list to broaden or narrow what gets filtered.

EXCLUDE_TITLE_WORDS = {
    "engineer", "scientist", "developer", "programmer",
    "recruiter", "sourcer", "designer", "counsel",
    "attorney", "accountant", "paralegal", "sre",
}

EXCLUDE_TITLE_PHRASES = [
    "talent acquisition", "machine learning", "site reliability",
    "engineering manager", "head of engineering",
    "vp engineering", "vp of engineering", "director of engineering",
    "data science", "devops", "it support", "help desk",
]


# ── Fit scoring ───────────────────────────────────────────────────────────────
# Based on McKinsey + Microsoft background targeting Director/GM/COO-track,
# GTM, PMM, and Growth roles at AI/SaaS companies.

STRONG_FIT_KEYWORDS = [
    "director", "vice president", "head of", "general manager",
    "chief of staff", "coo", "svp", "evp", "managing director",
    "go-to-market", "gtm", "product marketing", "pmm",
    "growth", "revenue operations", "revops", "commercial",
    "business development", "partnerships", "corp dev",
    "strategy", "chief operating",
]

POSSIBLE_FIT_KEYWORDS = [
    "manager", "marketing", "brand", "communications",
    "product manager", "program manager", "enablement",
    "sales", "customer success", "field", "launch",
    "analytics", "operations", "content strategy",
]


# ── Scrapers ──────────────────────────────────────────────────────────────────

def _get(url: str) -> dict | list | None:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Request failed ({url}): {e}")
        return None


def fetch_greenhouse(board_id: str) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs")
    if not data:
        return []
    return [
        {
            "id": f"gh_{j['id']}",
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", "") or "",
            "url": j.get("absolute_url", ""),
            "department": ", ".join(d["name"] for d in j.get("departments", [])),
        }
        for j in data.get("jobs", [])
    ]


def fetch_lever(company_id: str) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{company_id}?mode=json")
    if not data:
        return []
    return [
        {
            "id": f"lv_{j['id']}",
            "title": j.get("text", ""),
            "location": (j.get("categories") or {}).get("location", "") or "",
            "url": j.get("hostedUrl", ""),
            "department": (
                (j.get("categories") or {}).get("team", "")
                or (j.get("categories") or {}).get("department", "")
                or ""
            ),
        }
        for j in data
    ]


def fetch_ashby(org_id: str) -> list[dict]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{org_id}")
    if not data:
        return []
    return [
        {
            "id": f"ab_{j['id']}",
            "title": j.get("title", ""),
            "location": j.get("locationName", "") or "",
            "url": j.get("jobPostingUrl", ""),
            "department": j.get("departmentName", "") or "",
        }
        for j in data.get("jobPostings", [])
    ]


def fetch_jobs(company: dict) -> list[dict]:
    board = company["board"].lower()
    bid = company["board_id"]
    if board == "greenhouse":
        return fetch_greenhouse(bid)
    elif board == "lever":
        return fetch_lever(bid)
    elif board == "ashby":
        return fetch_ashby(bid)
    else:
        print(f"  Unknown board type '{board}' for {company['name']}")
        return []


# ── Filter & score ────────────────────────────────────────────────────────────

def should_exclude(title: str) -> bool:
    t = title.lower()
    words = set(re.findall(r'\b\w+\b', t))
    if words & EXCLUDE_TITLE_WORDS:
        return True
    return any(phrase in t for phrase in EXCLUDE_TITLE_PHRASES)


def score_job(title: str, department: str) -> tuple[str, str]:
    combined = (title + " " + department).lower()

    for kw in STRONG_FIT_KEYWORDS:
        if kw in combined:
            label = kw.strip().title()
            return "🟢", f"Strong fit — matches your Director/GM-track and {label} background"

    if re.search(r'\bvp\b', combined):
        return "🟢", "Strong fit — VP-level role aligns with your leadership search"

    for kw in POSSIBLE_FIT_KEYWORDS:
        if kw in combined:
            label = kw.strip().title()
            return "🟡", f"Possible fit — relevant function ({label})"

    return "⚪", "Passed filters — worth a quick look"


# ── Email ─────────────────────────────────────────────────────────────────────

def build_email(results: list[dict], is_first_run: bool) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    total = sum(len(r["jobs"]) for r in results)

    sections = []
    for company_result in results:
        jobs = company_result["jobs"]
        if not jobs:
            continue

        rows = []
        for job in jobs:
            emoji, reason = score_job(job["title"], job["department"])
            loc = job["location"] or "Remote / Not specified"
            dept_html = (
                f'<div style="color:#999;font-size:11px;margin-top:2px;">{job["department"]}</div>'
                if job["department"] else ""
            )
            rows.append(f"""
            <tr style="border-top:1px solid #f0f0f0;">
              <td style="padding:12px 14px;vertical-align:top;">
                <a href="{job['url']}" style="color:#1565C0;font-weight:600;text-decoration:none;font-size:14px;">{job['title']}</a>
                <div style="color:#777;font-size:12px;margin-top:3px;">📍 {loc}</div>
                {dept_html}
              </td>
              <td style="padding:12px 14px;vertical-align:middle;text-align:center;font-size:18px;">{emoji}</td>
              <td style="padding:12px 14px;vertical-align:middle;font-size:12px;color:#555;min-width:180px;">{reason}</td>
            </tr>""")

        count = len(jobs)
        sections.append(f"""
        <div style="margin-bottom:28px;">
          <h2 style="margin:0 0 10px;font-size:16px;color:#111;border-bottom:2px solid #e8e8e8;padding-bottom:7px;">
            {company_result['company']}
            <span style="font-weight:400;color:#888;font-size:13px;">&nbsp; {count} new role{"s" if count != 1 else ""}</span>
          </h2>
          <table style="width:100%;border-collapse:collapse;">
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>""")

    body = "\n".join(sections) if sections else (
        '<p style="color:#999;text-align:center;padding:32px 0;font-size:14px;">'
        'No new postings today. Check back tomorrow!</p>'
    )

    first_run_banner = ""
    if is_first_run:
        first_run_banner = """
        <div style="background:#FFF8E1;border:1px solid #FFD54F;border-radius:6px;
                    padding:11px 15px;margin-bottom:22px;font-size:13px;color:#5D4037;">
          <strong>First run!</strong> Showing all currently open relevant roles.
          From tomorrow you'll only see new postings.
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <div style="max-width:680px;margin:20px auto;background:#fff;border-radius:10px;
              overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

    <div style="background:#1a1a2e;padding:22px 28px;">
      <div style="font-size:19px;font-weight:700;color:#fff;">Daily Job Alert</div>
      <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:4px;">
        {today} &nbsp;·&nbsp; {total} new posting{"s" if total != 1 else ""}
      </div>
    </div>

    <div style="background:#f8f9fa;padding:9px 28px;border-bottom:1px solid #eee;
                font-size:11px;color:#777;">
      <strong>Fit key:</strong> &nbsp;
      🟢 Strong fit &nbsp;·&nbsp; 🟡 Possible fit &nbsp;·&nbsp; ⚪ Worth a look
      &nbsp;&nbsp;|&nbsp;&nbsp; Engineering, recruiting &amp; legal roles are filtered out
    </div>

    <div style="padding:22px 28px;">
      {first_run_banner}
      {body}
    </div>

    <div style="background:#f8f9fa;padding:13px 28px;border-top:1px solid #eee;
                font-size:11px;color:#bbb;">
      Add or remove companies by editing <code>companies.yml</code> on GitHub
      · Sent automatically every morning at 8 AM
    </div>
  </div>
</body>
</html>"""


def send_email(html: str, subject: str):
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = os.environ.get("TO_EMAIL", gmail_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Job Alert <{gmail_user}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, to_addr, msg.as_string())
    print(f"  ✓ Email sent to {to_addr}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    companies = yaml.safe_load(COMPANIES_FILE.read_text())["companies"]
    seen_data = json.loads(SEEN_JOBS_FILE.read_text()) if SEEN_JOBS_FILE.exists() else []
    seen = set(seen_data)
    is_first_run = len(seen) == 0

    all_relevant_ids: set[str] = set()
    results = []

    for company in companies:
        print(f"Fetching {company['name']}...")
        all_jobs = fetch_jobs(company)
        relevant = [j for j in all_jobs if not should_exclude(j["title"])]
        all_relevant_ids.update(j["id"] for j in relevant)

        new_jobs = relevant if is_first_run else [j for j in relevant if j["id"] not in seen]
        results.append({"company": company["name"], "jobs": new_jobs})

        label = "all" if is_first_run else "new"
        print(f"  {len(all_jobs)} total → {len(relevant)} relevant → {len(new_jobs)} {label}")

    total_new = sum(len(r["jobs"]) for r in results)

    if total_new == 0 and not is_first_run:
        print("No new jobs today — skipping email.")
    else:
        tag = "First Run — All Current Listings" if is_first_run else f"{total_new} New Posting{'s' if total_new != 1 else ''}"
        send_email(build_email(results, is_first_run), f"Job Alert — {tag}")

    updated_seen = seen | all_relevant_ids
    SEEN_JOBS_FILE.write_text(json.dumps(sorted(updated_seen), indent=2))
    print(f"Saved {len(updated_seen)} seen job IDs.")


if __name__ == "__main__":
    main()
