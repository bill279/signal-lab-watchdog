"""One-time confirmation that live alerts work end to end, before Bill shares the friends channel.

Hourly: if the friends channel has a "Trump is live" ping, tell Bill once that it's safe to share.
If 3 days pass with none, tell Bill once that live alerts may not be catching events. State lives in
live_state.json (timestamps only - no secrets). Secrets: NTFY_TOPIC (Bill), FRIENDS_TOPIC.
"""
import json, os, time, urllib.request, pathlib
ST = pathlib.Path("live_state.json")
s = json.loads(ST.read_text()) if ST.exists() else {}
now = time.time()
s.setdefault("armed_at", now)
def push(topic, msg, title, tags):
    urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + topic, data=msg.encode(),
                           headers={"Title": title, "Tags": tags}), timeout=30).read()
if not s.get("confirmed"):
    raw = urllib.request.urlopen("https://ntfy.sh/%s/json?poll=1&since=12h" % os.environ["FRIENDS_TOPIC"], timeout=30).read().decode()
    live = [json.loads(l) for l in raw.splitlines() if l.strip()]
    live = [m for m in live if m.get("event") == "message" and (m.get("title") or "").startswith("Trump is live")]
    if live:
        push(os.environ["NTFY_TOPIC"], "Your first live alert went out (%s), so the friends channel works. "
             "Safe to share it now." % live[-1]["title"], "Live alerts confirmed", "white_check_mark")
        s["confirmed"] = now; print("CONFIRMED:", live[-1]["title"])
    elif now - s["armed_at"] > 3 * 86400 and not s.get("nudged"):
        push(os.environ["NTFY_TOPIC"], "No 'Trump is live' ping in 3 days - live alerts may not be catching his "
             "events. Hold off sharing the friends channel and tell Claude: check live alerts.",
             "Live alerts not confirmed yet", "warning")
        s["nudged"] = now; print("NUDGED")
    else:
        print("waiting; armed %.1fh ago" % ((now - s["armed_at"]) / 3600))
else:
    print("already confirmed")
ST.write_text(json.dumps(s))
