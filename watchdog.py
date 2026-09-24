"""Outside watchdog for the Signal Lab on Hetzner. Silent unless something is wrong.

The lab pushes a heartbeat to a private ntfy topic every 30 min. This runs every 30 min on
GitHub Actions and pushes ONE alert to Bill's phone if the heartbeats stop, or if a critical
feed has failed in every heartbeat for 3 hours. Each problem alerts at most once per 12h.
Needs one secret: NTFY_TOPIC (the lab's topic; the heartbeat topic is derived from it).
"""
import hashlib, json, os, sys, time, urllib.request

TOPIC = os.environ["NTFY_TOPIC"].strip()
HB = "hb-" + hashlib.sha256(TOPIC.encode()).hexdigest()[:20]
DOWN_AFTER_S = 75 * 60
CRITICAL = {"truth": "Truth Social feed", "x": "X (Twitter) feed", "wallet": "wallet watcher",
            "whitehouse": "White House feed", "news": "news watcher"}
NAMES = {"x": "X", "truth": "Truth Social"}

def poll():
    with urllib.request.urlopen("https://ntfy.sh/%s/json?poll=1&since=12h" % HB, timeout=30) as r:
        lines = r.read().decode().splitlines()
    return [json.loads(l) for l in lines if l.strip()]

def push(topic, msg, title=None, tags=None):
    h = {}
    if title: h["Title"] = title
    if tags: h["Tags"] = tags
    urllib.request.urlopen(urllib.request.Request("https://ntfy.sh/" + topic, data=msg.encode(),
                           headers=h), timeout=30).read()

def main():
    now = time.time()
    msgs = [m for m in poll() if m.get("event") == "message"]
    beats = [m for m in msgs if not m.get("message", "").startswith("ALERTED ")]
    marks = {}
    for m in msgs:
        if m.get("message", "").startswith("ALERTED "):
            marks[m["message"][8:]] = m["time"]
    problems = []
    if beats and beats[-1]["message"] == "finished":
        print("lab finished its run; nothing to watch"); return
    last = beats[-1]["time"] if beats else None
    # an outage alert only counts until the lab checks in again
    alerted = {k for k, t in marks.items() if not (k == "down" and last and last > t)}
    if "down" in marks and last and last > marks["down"] and marks.get("recovered", 0) < marks["down"]:
        push(TOPIC, "The server is checking in again and alerts are flowing.", "Signal Lab is back",
             "white_check_mark")
        push(HB, "ALERTED recovered")
        print("RECOVERY SENT")
    if last is None or now - last > DOWN_AFTER_S:
        mins = "over 12 hours" if last is None else "%d minutes" % ((now - last) // 60)
        problems.append(("down", "Signal Lab stopped reporting",
                         "No check-in from the server for %s, so alerts aren't going out. "
                         "Tell Claude: 'signal lab is down'." % mins))
    else:
        recent = [b for b in beats if now - b["time"] <= 3 * 3600]
        if len(recent) >= 5:
            def errs(b):
                t = b["message"].split("errors=", 1)[-1]
                return set() if t == "-" else set(t.split(","))
            stuck = set.intersection(*[errs(b) for b in recent]) & set(CRITICAL)
            for k in sorted(stuck):
                problems.append(("feed:" + k, "Signal Lab: %s is broken" % CRITICAL[k],
                                 "The %s has failed every check for 3 hours. Everything else is "
                                 "running. Tell Claude: 'signal lab %s is broken'." % (CRITICAL[k], k)))
    for key, title, body in problems:
        if key in alerted:
            print("already alerted:", key); continue
        push(TOPIC, body, title, "rotating_light")
        push(HB, "ALERTED " + key)
        print("ALERT SENT:", key)
    if not problems:
        print("healthy: last check-in %d min ago" % ((now - last) // 60))

if __name__ == "__main__":
    main()
