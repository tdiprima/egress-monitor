# outbound\_audit_cron.sh

## The ultra-short version

This script is the **daily autopilot** for `outbound_audit.py`.

Translation:

- every day, it checks yesterday's outbound traffic
- compares it to the normal baseline
- saves a report
- emails you if something looks sketchy

So the vibe is:

**"Run the audit while I sleep, and yell if the server acts weird."**

---

## What this script depends on

Before this script works right, you need:

- `outbound_audit.py` installed somewhere
- a baseline JSON already created
- outbound logs already being collected
- some mail tool available if you want email alerts

So this script is not the setup.

It is the automation layer.

---

## Main character energy: what the script actually does

### 1. It defines where everything lives

It sets variables for:

- the Python audit script
- the baseline file
- the outbound log file
- the report directory
- the email address
- the Python binary

So first it is basically doing:

**"Where is my stuff?"**

One important detail:

```bash
ALERT_EMAIL="$EMAIL"
```

That means it expects an `EMAIL` environment variable to already exist.

So if that variable is empty or missing, email alerts are gonna be awkward.

---

### 2. It creates a report folder

It makes sure this directory exists:

```text
/var/log/outbound-audit-reports
```

That is where daily report files get saved.

So even if there is no email, you still get a local report file.

---

### 3. It figures out the time window for "yesterday"

It calculates:

- yesterday at `00:00`
- yesterday at `23:59`

Why?

Because the cron job is supposed to check the full previous day.

So if it runs at midnight today, it audits all of yesterday's traffic.

Clean and predictable.

---

### 4. It runs `outbound_audit.py`

This is the main event.

It runs the audit script with:

- the log file
- the baseline
- the start/end time for yesterday
- `--no-resolve`

That last one means:

**"don't waste time doing DNS lookups in cron"**

Smart, because reverse lookups can be slow and cron jobs should be boring.

Also:

```bash
2>&1
```

means it captures both normal output and errors into one variable:

```bash
AUDIT_OUTPUT
```

So the script keeps the full audit text and can inspect it later.

---

### 5. It checks whether the audit found anything bad

Now it looks through the audit output text using `grep`.

It checks for:

- `Found N anomalies`
- `OLLAMA MADE`

If either of those appears, it flips alert flags.

So this step is basically:

**"Did the audit yell? If yes, mark this as a problem."**

The script tracks:

- `HAS_ANOMALIES`
- `ANOMALY_COUNT`
- `OLLAMA_ALERT`

---

### 6. It always writes a report file

This happens no matter what.

The report file includes:

- date
- host
- time period checked
- status
- full audit output

If there were no issues, it writes a clean status.

If there were issues, it writes the warning status plus the full audit output.

That is good design.

Why?

Because even a clean run leaves receipts.

---

### 7. It sends an email only if anomalies were found

If the audit was clean:

- no email
- just a report file

If the audit found problems:

- it builds an email subject
- it builds an email body
- it sends the alert

If Ollama outbound activity happened, the subject becomes more dramatic:

```text
[CRITICAL] hostname: Ollama made outbound connections!
```

Which is fair.

That is very much the "wake somebody up" case.

---

### 8. It tries multiple mail tools

It sends email using the first available option:

- `mailx`
- `mail`
- `sendmail`

If none of those exist, it does not crash.

It writes a warning into:

```text
mail-failures.log
```

So the script is basically saying:

**"I tried to scream, but there was no megaphone."**

---

### 9. It deletes old report files

It removes audit reports older than 90 days.

So the report directory does not slowly become digital hoarder behavior.

---

### 10. It logs the run to syslog

At the end, it uses `logger` to write a one-line summary to syslog.

Something like:

- anomalies found
- Ollama yes/no
- where the report file is

So you get one final little breadcrumb in system logs.

---

## Why this script exists

Without this file, you would have to remember to manually run the audit every day.

That is annoying.

This script turns the whole audit process into:

- scheduled
- repeatable
- report-based
- alert-based

So this file is the automation glue.

---

## Remember just this

- It runs the audit once a day.
- It checks yesterday's traffic.
- It compares that traffic to the baseline.
- It always saves a report file.
- It only emails if something weird happened.
- It freaks out extra hard if Ollama made outbound connections.

That is the whole story.

---

## One-sentence summary

`outbound_audit_cron.sh` is the **"run the outbound audit every day, save a report, and send alerts if anything sus shows up"** script.

<br>
