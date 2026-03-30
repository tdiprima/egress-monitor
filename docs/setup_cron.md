# setup_cron.sh

## The ultra-short version

This script is basically a tiny **manual checklist in shell-script form**.

It:

- copies the audit scripts into the right place
- reruns the outbound logging setup
- creates a baseline
- opens cron setup so you can schedule the daily audit

So the vibe is:

**"Install the pieces, prime the system, then wire up the daily job."**

---

## This script is very simple

Unlike the other two, this one is not doing big logic.

It is mostly just running a few commands in order.

So think of it less like a program and more like:

**"the setup to-do list, but executable."**

---

## What it actually does

### 1. Copies files into `/usr/local/bin`

It copies:

- `outbound_audit.py`
- `outbound_audit_cron.sh`

into:

```text
/usr/local/bin/
```

That makes them available from a standard system location.

Then it marks `outbound_audit_cron.sh` as executable.

Meaning:

**"this file is allowed to run like a command"**

---

### 2. Re-runs the outbound logging setup

It runs:

```bash
sudo bash setup_outbound_logging.sh
```

That means:

- set up firewall logging
- set up rsyslog routing
- set up log rotation

So this step is basically:

**"make sure the server is actually collecting the logs we want."**

---

### 3. Creates the baseline

It runs:

```bash
sudo /usr/bin/python3 /usr/local/bin/outbound_audit.py --save-baseline /etc/outbound-baseline.json
```

That tells the audit script:

**"Take whatever traffic exists right now and save it as our normal reference point."**

This baseline is what the daily cron audit compares against later.

Important real-world note:

The comment says to let logs accumulate for a day or two first.

That matters.

Because if you save the baseline too early, your "normal" snapshot might be incomplete.

So the script is technically doing the baseline creation command, but the comment is warning you not to rush that step.

---

### 4. Opens root cron editing

It runs:

```bash
sudo crontab -e
```

Then it tells you to add:

```text
0 0 * * * /usr/local/bin/outbound_audit_cron.sh
```

That means:

- run every day
- at midnight

So this is the final wiring step that puts the daily audit on autopilot.

---

## Why this script exists

Because all the pieces need to be connected in the right order:

1. install the scripts
2. enable logging
3. create baseline
4. schedule automation

This file is just trying to make that process harder to forget.

---

## One important thing to notice

This script still opens `crontab -e`, which is interactive.

So it is not a fully hands-off installer.

It gets you to the finish line, but you still have to type in the cron entry yourself.

So the script is part automation, part reminder.

---

## Remember just this

- It installs the audit scripts.
- It turns on outbound logging.
- It creates the baseline file.
- It helps you set the daily cron job.

That is literally it.

---

## One-sentence summary

`setup_cron.sh` is the **"install everything and help schedule the daily audit job"** script.

<br>
