# What To Do If You Didn't Wait Before Creating the Baseline

So logging is running, the cron is scheduled, but you created the baseline too early — before enough traffic had accumulated. The baseline is probably thin, which means the anomaly detector will cry wolf every night because everything looks "new."

Good news: the scripts and cron are fine. You just need to rebuild the baseline.

## Step 1 — Confirm logs are actually being written

```bash
sudo tail -20 /var/log/outbound-connections.log
```

If you see recent entries, logging is working. Keep going.

If the file is empty or missing, go back and run `setup_outbound_logging.sh` first.

## Step 2 — Wait until you have real traffic

Just let the server run. Come back tomorrow, or ideally the day after.

You want at least a full day of normal activity in the log before you snapshot a baseline. The more representative the traffic, the fewer false alarms you'll get.

## Step 3 — Rebuild the baseline

When you're ready, overwrite the old baseline:

```bash
sudo python3 /usr/local/bin/outbound_audit.py --save-baseline /etc/outbound-baseline.json
```

This replaces whatever was there before. It reads everything currently in the log and saves it as the new "normal."

## Step 4 — Verify it looks reasonable

```bash
cat /etc/outbound-baseline.json | python3 -m json.tool | grep entry_count
```

If `entry_count` is a handful of entries, the baseline is still too thin. Wait longer and redo Step 3.

A healthy baseline for an active server is typically hundreds to thousands of entries.

## Step 5 — Nothing else to change

The cron job, the scripts, the log file — all of that is fine. The nightly job will automatically use the new baseline the next time it runs.

## Sanity Check: Run the audit manually right now

```bash
sudo python3 /usr/local/bin/outbound_audit.py --baseline /etc/outbound-baseline.json
```

If the anomaly count is near zero, your baseline is solid. If it's flagging hundreds of things as new, wait another day and rebuild again.

<br>
