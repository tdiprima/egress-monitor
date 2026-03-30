# setup\_outbound_logging.sh

## The ultra-short version

This script sets up your server so it can **snitch on outbound internet traffic**.

Translation:

- it tells the firewall to log outbound connections
- it gives those logs their own file
- it makes sure the log file does not grow forever
- optionally, it adds extra connection tracking stuff

So the vibe is:

**"Server, every time you try to talk to the internet, write that down."**

---

## What this script is for

`outbound_audit.py` needs logs to read.

This script is the thing that creates those logs in the first place.

So:

- `setup_outbound_logging.sh` = setup the surveillance
- `outbound_audit.py` = read the surveillance

They are a duo.

---

## What it sets up

Main log file:

```text
/var/log/outbound-connections.log
```

Optional extra log file if conntrack is enabled:

```text
/var/log/conntrack-outbound.log
```

So after this runs, outbound network activity should get logged where the audit script can read it.

---

## Main character energy: what the script actually does

### 1. It checks if you are root

If you are not running with `sudo`, it bails.

Because this script edits:

- firewall config
- rsyslog config
- logrotate config
- system services

Normal user powers are not enough.

---

### 2. It checks that `firewalld` is running

If `firewalld` is not active, the script stops and tells you to start it.

Makes sense.

No firewall = nothing to configure.

---

### 3. It finds the active firewall zone

It asks `firewall-cmd` for the default zone.

That is basically:

**"which firewall bucket are we editing?"**

---

### 4. It deletes old direct logging rules first

This is the re-run safety move.

The script removes previous `OUTPUT` chain direct rules before adding fresh ones.

So instead of stacking duplicate rules forever, it tries to clean the old stuff first.

That means the script is meant to be re-runnable.

Nice.

---

### 5. It adds firewall rules to log outbound traffic

This is the core of the script.

It creates multiple layers of rules.

#### Priority 0: ignore localhost / loopback traffic

This skips traffic that stays inside the machine, like:

- app talking to itself
- local dev servers
- local Ollama inference calls

Why skip that?

Because it is noisy and not the point.

The script only cares about traffic that is actually trying to leave the machine.

So this is basically:

**"ignore internal self-chat"**

---

#### Priority 1: log Ollama's outbound traffic separately

This is the spicy part.

The script tries to find the `ollama` user.

If it exists, it adds special logging rules for traffic created by that user.

That means if Ollama reaches out to the internet, it gets a special log prefix like:

- `OLLAMA_OUTBOUND_TCP`
- `OLLAMA_OUTBOUND_UDP`
- `OLLAMA_OUTBOUND_TCP6`

So the script is very intentionally saying:

**"If Ollama phones home, I want receipts."**

If the `ollama` user does not exist, it warns you and skips the Ollama-specific rules.

---

#### Priority 2: log all other outbound traffic

It adds rules for:

- IPv4 TCP
- IPv4 UDP
- IPv6 TCP
- IPv6 UDP

These get prefixes like:

- `OUTBOUND_CONN_TCP`
- `OUTBOUND_CONN_UDP`
- `OUTBOUND_CONN_TCP6`
- `OUTBOUND_CONN_UDP6`

So this is the general-purpose logging for new outbound connections.

---

#### Priority 999: log blocked outbound attempts

This is the:

**"you tried to leave, but the firewall said no"**

rule.

Those log lines get the prefix:

```text
OUTBOUND_BLOCKED
```

So now you can see both:

- connections that were allowed
- connections that got denied

That is useful because blocked attempts can still be suspicious.

---

### 6. It reloads firewalld

After changing the firewall rules, it runs `firewall-cmd --reload`.

Without that, the new rules would not actually be active.

So this is the "make it real" step.

---

### 7. It configures `rsyslog`

The firewall logs messages, but you still need those messages routed into a file.

This script writes:

```text
/etc/rsyslog.d/10-outbound-connections.conf
```

That config tells `rsyslog`:

- if message contains `OUTBOUND_CONN`, write it to the outbound log
- if message contains `OUTBOUND_BLOCKED`, write it to the outbound log
- if message contains `OLLAMA_OUTBOUND`, write it to the outbound log

So this step is basically:

**"Take the firewall gossip and save it in the right notebook."**

Then it:

- creates the log file
- sets permissions
- restarts `rsyslog`

---

### 8. It configures log rotation

Logs can get big.

Very big.

So the script creates a `logrotate` config that says:

- rotate daily
- keep 30 old copies
- compress old logs

That stops the log file from becoming a disk-eating goblin.

If conntrack logging is enabled, it sets up rotation for that too.

---

## What is conntrack in this script?

Conntrack is optional extra logging/tracking for connections.

You enable it with:

```bash
sudo bash setup_outbound_logging.sh --with-conntrack
```

In this script, `--with-conntrack` mainly flips a flag so extra related setup like log rotation can happen.

So think of conntrack as:

**"more detailed network receipts, if you want them"**

---

## The important variables, but in normal-person language

### `LOG_FILE`

Where the main outbound logs go.

### `CONNTRACK_LOG`

Where optional conntrack logs go.

### `LOG_PREFIX`

Base text used to mark normal outbound log lines.

### `BLOCKED_PREFIX`

Base text used to mark blocked outbound attempts.

### `OLLAMA_USER`

The Linux user the script assumes Ollama runs as.

This matters because the script uses that user to identify Ollama-made traffic.

---

## Remember just this

- This script turns on outbound traffic logging.
- It ignores localhost noise.
- It gives Ollama its own special alarm label.
- It sends logs into `/var/log/outbound-connections.log`.
- It sets up log rotation so the file does not grow forever.

That is the whole deal.

---

## One-sentence summary

`setup_outbound_logging.sh` is the **"make the firewall log all internet-bound traffic, especially Ollama, and store it cleanly"** script.

<br>
