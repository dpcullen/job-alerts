# Daily Job Alert

Emails you every morning with new job postings from companies you care about.
Engineering, recruiting, legal, and design roles are automatically filtered out.
Remaining roles get a fit indicator (🟢 Strong / 🟡 Possible / ⚪ Worth a look)
based on your GTM/PMM/leadership background — no AI API costs required.

---

## One-time setup (takes ~10 minutes)

### Step 1 — Create a Gmail App Password

You need a special password so the script can send email on your behalf.
Your regular Gmail password won't work here.

1. Go to your Google Account → **Security** → **2-Step Verification** (enable it if not already on)
2. Still in Security, scroll down and click **App passwords**
3. Under "Select app" choose **Mail**, under "Select device" choose **Other**, type `Job Alert`
4. Click **Generate** — copy the 16-character password shown (you won't see it again)

---

### Step 2 — Add secrets to GitHub

1. Go to this repo on GitHub: `https://github.com/dpcullen/job-alerts`
2. Click **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
3. Add these three secrets one at a time:

| Secret name | Value |
|---|---|
| `GMAIL_USER` | `dallaspcullen@gmail.com` |
| `GMAIL_APP_PASSWORD` | The 16-character password from Step 1 |
| `TO_EMAIL` | `dallaspcullen@gmail.com` |

---

### Step 3 — Enable GitHub Actions

1. In this repo, click the **Actions** tab
2. If you see a banner asking to enable workflows, click **I understand my workflows, go ahead and enable them**

That's it! The email will run automatically every morning at 8 AM EST.

---

## Send a test email right now

1. Go to the **Actions** tab in this repo
2. Click **Daily Job Alert** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Check your inbox in ~60 seconds

---

## Add or remove companies

Open [`companies.yml`](companies.yml) on GitHub, click the pencil ✏️ icon to edit,
add or remove entries, then click **Commit changes**.

The file has examples and instructions at the bottom.

---

## Adjust the send time

Open [`.github/workflows/daily-job-alert.yml`](.github/workflows/daily-job-alert.yml),
find the line `- cron: '0 13 * * *'`, and change `13` to a different UTC hour:

| Local time | UTC hour to use |
|---|---|
| 7 AM EST | `12` |
| 8 AM EST | `13` |
| 9 AM EST | `14` |
| 8 AM PST | `16` |

---

## Adjust what gets filtered out

Open [`job_alert.py`](job_alert.py) and find the `EXCLUDE_TITLE_WORDS` and
`EXCLUDE_TITLE_PHRASES` sections near the top. Add or remove words there.

---

## Troubleshooting

**No email arrived** — Check the Actions tab for a red ✗ on the latest run.
Click it to see the error log.

**0 jobs showing for a company** — The company's board ID may have changed.
Find their careers page URL and update `board_id` in `companies.yml`.

**Email going to spam** — Mark it as "Not spam" once and Gmail will remember.
