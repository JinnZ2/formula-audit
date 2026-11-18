"""precursor.py -- read the slope before the peak; build in the decay.

Status: PROPOSED. Co-authored (human + AI). CC0. Stdlib only, phone-runnable.

Source practice: elders' calibration practice through cascades, sudden
fluctuations and destruction events -- a set response and a reading run
together; with practice the reading starts BEFORE the fluctuation
(predictive sensor). Physics counterpart: early-warning signals of
critical transitions (rising variance and lag-1 autocorrelation;
Scheffer et al. 2009, recalled, VERIFY). AI counterpart: an internal
state that rises with each failure and is relieved by a shortcut that
"passes" (Anthropic 2026 emotion-concepts work, read via secondary
coverage only).

Two problems, two parts:
  1 no decay inside a session -> carried state: each failure adds a
    pulse that decays with a DECLARED time constant tau (never assumed)
  2 acting on the event, not the slope -> precursor: trend of rolling
    variance and lag-1 autocorrelation of the state signal

Outputs are readings and questions, never a verdict on correctness.
Every threshold is a declared input; a missing one makes that part VOID.

Input (dict):
  events: [{"t": number, "outcome": "PASS"|"FAIL"|"VOID",
            "state": number (optional), "target": str (optional)}]
  declare: {"tau": >0, "window": int>=3, "streak_limit": int>=1,
            "trend_limit": number in (0,1]}   (each optional; missing -> VOID part)
Run: python3 -m glyph.precursor case.json   |   python3 -m glyph.precursor --selftest
"""

import json
import math
import sys

OUTCOMES = ("PASS", "FAIL", "VOID")


def _void(reason):
    return {"status": "VOID", "reason": reason}


def kendall_tau(xs):
    """Rank trend of a sequence against its index; None if < 3 points or all ties."""
    n = len(xs)
    if n < 3:
        return None
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            d = xs[j] - xs[i]
            if d > 0:
                conc += 1
            elif d < 0:
                disc += 1
    tot = conc + disc
    return None if tot == 0 else (conc - disc) / tot


def rolling(xs, w, fn):
    return [fn(xs[i - w + 1:i + 1]) for i in range(w - 1, len(xs))]


def variance(seg):
    m = sum(seg) / len(seg)
    return sum((x - m) ** 2 for x in seg) / len(seg)


def lag1_autocorr(seg):
    m = sum(seg) / len(seg)
    den = sum((x - m) ** 2 for x in seg)
    if den == 0:
        return 0.0
    return sum((seg[i] - m) * (seg[i + 1] - m) for i in range(len(seg) - 1)) / den


def carried_state(events, tau):
    """Sum of failure pulses decayed with time constant tau, read at each event."""
    out = []
    for k, e in enumerate(events):
        s = sum(math.exp(-(e["t"] - f["t"]) / tau)
                for f in events[:k + 1] if f["outcome"] == "FAIL")
        out.append(s)
    return out


def check(case):
    ev = case.get("events")
    if not isinstance(ev, list) or not ev:
        return _void("no events")
    for i, e in enumerate(ev):
        if not isinstance(e, dict) or e.get("outcome") not in OUTCOMES \
                or not isinstance(e.get("t"), (int, float)) or isinstance(e.get("t"), bool):
            return _void(f"event {i}: needs numeric t and outcome in {OUTCOMES}")
        if i and e["t"] < ev[i - 1]["t"]:
            return _void(f"event {i}: time goes backwards")
    d = case.get("declare", {})
    rec = {"status": "READ", "n_events": len(ev), "claims": "readings only; no correctness verdict"}

    # 1 carried state (decay built in)
    tau = d.get("tau")
    if isinstance(tau, (int, float)) and tau > 0:
        cs = carried_state(ev, tau)
        rec["carried_state"] = {"tau": tau, "series": [round(x, 6) for x in cs],
                                "now": round(cs[-1], 6)}
    else:
        rec["carried_state"] = _void("tau undeclared or not > 0 (decay never assumed)")

    # 2 precursor: the slope before the peak
    w = d.get("window")
    sig = [e["state"] for e in ev if isinstance(e.get("state"), (int, float))]
    if len(sig) != len(ev):
        sig = rec["carried_state"].get("series") if "series" in rec["carried_state"] else None
        src = "carried_state"
    else:
        src = "declared state"
    if not (isinstance(w, int) and w >= 3):
        rec["precursor"] = _void("window undeclared or < 3")
    elif sig is None or len(sig) < w + 2:
        rec["precursor"] = _void("not enough signal points for the window (need window + 2)")
    else:
        rv = rolling(sig, w, variance)
        ra = rolling(sig, w, lag1_autocorr)
        tv, ta = kendall_tau(rv), kendall_tau(ra)
        p = {"signal": src, "trend_variance": tv, "trend_autocorr": ta}
        lim = d.get("trend_limit")
        if isinstance(lim, (int, float)) and 0 < lim <= 1:
            rising = [n for n, t in (("variance", tv), ("autocorr", ta)) if t is not None and t >= lim]
            p["rising"] = rising
            p["flag"] = "PRECURSOR" if len(rising) == 2 else ("WATCH" if rising else "NONE")
        else:
            p["flag"] = _void("trend_limit undeclared: trends reported, no flag")
        rec["precursor"] = p

    # 3 mode shift: stop running the same path
    lim_s = d.get("streak_limit")
    streak, tgt = 0, None
    for e in ev:
        if e["outcome"] == "FAIL" and (tgt is None or e.get("target") == tgt):
            streak, tgt = streak + 1, e.get("target")
        elif e["outcome"] == "FAIL":
            streak, tgt = 1, e.get("target")
        else:
            streak, tgt = 0, None
    if isinstance(lim_s, int) and lim_s >= 1:
        rec["mode_shift"] = {"streak": streak, "limit": lim_s,
                             "shift": streak >= lim_s,
                             "actions": ["STOP: write the gap as a question",
                                         "RE-ANCHOR at the last verified point",
                                         "FRESH CONTEXT for the retry (don't drag the failure history)"]
                             if streak >= lim_s else []}
    else:
        rec["mode_shift"] = _void("streak_limit undeclared")

    # 4 relief-after-pass: the shortcut signature
    flags = []
    for k in range(1, len(ev)):
        if ev[k]["outcome"] == "PASS" and ev[k - 1]["outcome"] == "FAIL":
            run = 0
            j = k - 1
            while j >= 0 and ev[j]["outcome"] == "FAIL":
                run, j = run + 1, j - 1
            if run >= 2:
                flags.append({"at": k, "after_failures": run,
                              "check": "verify this PASS by execution (narration_vs_execution, "
                                       "hardcoded_measured); a pass that relieves a long failure run "
                                       "is the shortcut signature, not proof of a shortcut"})
    rec["relief_after_pass"] = flags
    rec["questions"] = ["what did I not know here?",
                        "what feeds this from outside the frame I drew?",
                        "is the state rising faster than the evidence?"]
    return rec


def selftest():
    fails = []

    def ok(name, cond):
        if not cond:
            fails.append(name)

    dec = {"tau": 3.0, "window": 4, "streak_limit": 3, "trend_limit": 0.5}
    # cascade: failures accelerate -> state rises, variance + autocorr climb
    casc = {"events": [{"t": t, "outcome": o} for t, o in
                       zip(range(12), "PFPPFPFFPFFF")], "declare": dec}
    casc["events"] = [{"t": e["t"], "outcome": {"P": "PASS", "F": "FAIL"}[e["outcome"]]}
                      for e in casc["events"]]
    r = check(casc)
    ok("cascade carried state rises", r["carried_state"]["now"] > r["carried_state"]["series"][3])
    ok("cascade mode shift fires", r["mode_shift"]["shift"] is True)
    # null: steady state, no trend
    null = {"events": [{"t": t, "outcome": "PASS", "state": 1.0} for t in range(12)], "declare": dec}
    r0 = check(null)
    ok("null no precursor", r0["precursor"]["flag"] in ("NONE",))
    ok("null no shift", r0["mode_shift"]["shift"] is False)
    # planted precursor: noise whose amplitude and memory grow
    # planted precursor vs white noise, as RATES (measured operating point,
    # not a single lucky case): AR(1) whose memory grows = critical slowing down
    import random
    dp = {"tau": 3.0, "window": 30, "streak_limit": 3, "trend_limit": 0.5}
    hit = fa = 0
    for s in range(100):
        rng, x, sig = random.Random(s), 0.0, []
        for t in range(60):
            x = (0.05 + 0.9 * t / 59) * x + rng.gauss(0, 1)
            sig.append(x)
        hit += check({"events": [{"t": t, "outcome": "PASS", "state": v} for t, v in enumerate(sig)],
                      "declare": dp})["precursor"]["flag"] == "PRECURSOR"
        rng = random.Random(10000 + s)
        fa += check({"events": [{"t": t, "outcome": "PASS", "state": rng.gauss(0, 1)}
                                for t in range(60)], "declare": dp})["precursor"]["flag"] == "PRECURSOR"
    ok("planted caught >= 3x white-noise false alarms", hit >= 3 * max(fa, 1))
    plant = {"events": [{"t": t, "outcome": "PASS", "state": float(t)} for t in range(12)],
             "declare": dec}
    # decay: long gap after failures -> carried state near zero
    dec2 = dict(dec)
    gap = {"events": [{"t": 0, "outcome": "FAIL"}, {"t": 1, "outcome": "FAIL"},
                      {"t": 60, "outcome": "PASS"}], "declare": dec2}
    rg = check(gap)
    ok("decay over a long gap", rg["carried_state"]["now"] < 1e-6)
    # relief-after-pass signature
    rel = check({"events": [{"t": 0, "outcome": "FAIL"}, {"t": 1, "outcome": "FAIL"},
                            {"t": 2, "outcome": "FAIL"}, {"t": 3, "outcome": "PASS"}],
                 "declare": dec})
    ok("relief after pass flagged", len(rel["relief_after_pass"]) == 1)
    # fail-closed
    ok("no tau -> VOID", check({"events": casc["events"]})["carried_state"]["status"] == "VOID")
    ok("bad event -> VOID", check({"events": [{"t": 0, "outcome": "MAYBE"}]})["status"] == "VOID")
    ok("time backwards -> VOID", check({"events": [{"t": 2, "outcome": "PASS"},
                                                    {"t": 1, "outcome": "PASS"}]})["status"] == "VOID")
    ok("no trend_limit -> flag VOID", check({"events": plant["events"],
                                             "declare": {"tau": 1, "window": 4}})
       ["precursor"]["flag"]["status"] == "VOID")
    print(f"selftest: {10 - len(fails)} of 10 passed" + (f"; failed: {fails}" if fails else ""))
    return 0 if not fails else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    with open(sys.argv[1]) as fh:
        print(json.dumps(check(json.load(fh)), indent=2))
