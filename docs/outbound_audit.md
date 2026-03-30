# outbound_audit.py

## The ultra-short version

This script is basically a **security recap bot** for your server's outbound traffic.

Translation:

- Your server makes internet connections.
- Firewall logs that stuff.
- `outbound_audit.py` reads those logs.
- Then it tells you:
  - where the server tried to connect
  - what ports it used
  - whether anything got blocked
  - whether **Ollama** tried to phone home
  - whether something looks weird

So the vibe is:

**"Yo, server, who were you talking to, and was it sketchy?"**

---

## What goes in

The script reads a log file.

Default file:

```text
/var/log/outbound-connections.log
```

That log is supposed to contain firewall/kernel lines like:

```text
Mar 20 14:23:01 server1 kernel: OUTBOUND_CONN_TCP: SRC=10.0.0.5 DST=104.18.32.7 DPT=443 ...
```

Meaning:

- `SRC` = who sent it
- `DST` = where it went
- `DPT` = destination port
- `PROTO` = protocol like TCP/UDP

So the raw log is messy nerd soup, and this script turns it into something readable.

---

## Main character energy: what the script actually does

### 1. It parses each log line

It grabs the useful bits from each line:

- time
- hostname
- source IP
- destination IP
- source port
- destination port
- protocol
- whether it looks like Ollama traffic
- whether it was blocked

If a line is junk or doesn't match the expected format, the script basically says:

**"nah, not useful"**

and skips it.

---

### 2. It builds little data objects

Each log line gets turned into a Python dictionary.

Think:

```python
{
  "timestamp": ...,
  "src": "...",
  "dst": "...",
  "dpt": 443,
  "proto": "TCP",
  "is_ollama": False,
  "is_blocked": False
}
```

So instead of wrestling ugly text, the script now has clean structured info.

Big win.

---

### 3. It can reverse-lookup IPs into hostnames

Example:

- `8.8.8.8` might become `dns.google`

That part is optional, and it caches results so it doesn't keep asking DNS the same question over and over.

So:

- nicer output
- less repeated work

---

## The 3 big reports

If you run the script normally, it prints 3 sections.

### 1. Summary report

This is the **"what happened overall?"** section.

It shows things like:

- total connections
- allowed vs blocked
- Ollama-related connections
- top destinations
- top destination ports
- top source hosts
- hourly activity graph
- protocol breakdown

Basically a scoreboard.

If your server was busy all day, this is the bird's-eye view.

---

### 2. Ollama report

This is the **"did Ollama do something sus?"** section.

The script is clearly very interested in Ollama.

If Ollama made outbound connections, this section calls it out hard:

- destination
- port
- how many times
- first seen
- last seen

If Ollama made no outbound connections, the script is like:

**"cool, that's what we wanted"**

So this is basically the special alarm panel for Ollama.

---

### 3. Anomaly report

This is the **"what looks weird?"** section.

It flags stuff like:

- unusual destination ports
- blocked outbound attempts
- any Ollama outbound traffic
- new destinations not seen before
- new destination+port combos not in the baseline

So if the summary is the recap, anomaly detection is the **"red flag detector."**

---

## What is a baseline?

A baseline is just a saved snapshot of traffic that you consider normal.

Like:

**"This is our usual boring healthy behavior."**

The script can save one as JSON.

Later, it can compare new logs against that baseline and say:

- this destination is new
- this port is new
- this combo wasn't here before

That matters because "new" can equal "worth checking."

Not always bad.
But definitely worth side-eye.

---

## The important functions, but in normal-person language

### `parse_syslog_timestamp()`

Turns a syslog timestamp like:

```text
Mar 20 14:23:01
```

into an actual Python `datetime`.

So the script can compare times without being dumb.

---

### `parse_log_line()`

The parser.

This is where one raw line gets cracked open and turned into a structured entry.

Very important function. Kind of the front door.

---

### `read_log_file()`

Opens the file, reads every line, parses it, keeps the valid entries.

Also handles errors like:

- file missing
- permission denied

If permissions are bad, it tells you to try `sudo`.

---

### `resolve_ip()`

Does reverse DNS lookup.

Turns IPs into names when possible.

Also cached for speed.

---

### `print_summary_report()`

Makes the general dashboard.

This is where the script counts things and prints the top talkers, ports, hours, etc.

---

### `print_ollama_report()`

Makes the Ollama-specific warning/report section.

This one is basically:

**"Ollama, explain yourself."**

---

### `print_anomaly_report()`

Builds the suspicious-stuff list.

This is the part that assigns severity like:

- `CRITICAL`
- `HIGH`
- `MEDIUM`

So you know what deserves attention first.

---

### `save_baseline()` / `load_baseline()`

These handle the baseline JSON file.

- save normal behavior
- load it later
- compare against it

Simple but useful.

---

## How the script flows from top to bottom

Here is the whole movie in simple steps:

1. Parse command-line options.
2. Read the log file.
3. Apply time filters if you asked for them.
4. Quit early if there are no matching entries.
5. Save a baseline and exit if you asked for that.
6. Load a baseline if you gave one.
7. Optionally resolve IPs to hostnames.
8. Print either:
   - just the Ollama report
   - or the full set of reports

That is the whole pipeline.

It's honestly pretty clean.

---

## CLI flags in plain English

### `-f` / `--file`

Use a different log file.

### `-n` / `--top`

Show more or fewer "top" results.

### `--ollama-only`

Only print the Ollama section.

### `--no-resolve`

Don't try to turn IPs into hostnames.

Faster, less pretty.

### `--baseline FILE`

Compare current traffic against a saved normal snapshot.

### `--save-baseline FILE`

Save current traffic as the new normal snapshot, then exit.

### `--after "YYYY-MM-DD HH:MM"`

Only include entries after that time.

### `--before "YYYY-MM-DD HH:MM"`

Only include entries before that time.

---

## What the script cares about most

The script seems built around one core anxiety:

**"Is this server, especially Ollama, making outbound connections it shouldn't be making?"**

That is the whole personality of the file.

Everything supports that:

- parsing logs
- counting destinations
- highlighting weird ports
- yelling about blocked attempts
- extra yelling about Ollama
- comparing against a baseline

So the script is not random analytics.

It is specifically a **network audit / suspicious outbound traffic checker**.

---

## What is "normal" vs "weird" in this script?

The script treats these ports as pretty normal outbound traffic:

- `53` = DNS
- `80` = HTTP
- `123` = NTP
- `443` = HTTPS
- `853` = DNS-over-TLS

If traffic goes to other ports, the script may flag it as unusual.

Important:

That does **not** automatically mean evil.

It just means:

**"hey, this is less common, maybe look at it"**

---

## Remember just this

If you forget everything else, keep this:

- The script reads outbound firewall logs.
- It turns messy log text into structured data.
- It summarizes who the server talked to.
- It checks whether Ollama talked to anything.
- It flags weird/new/blocked stuff.
- A baseline is just "known normal" saved in JSON.

That is the whole thing.

---

## One-sentence summary

`outbound_audit.py` is a **"who did my server talk to, and should I be worried?"** script.

<br>
