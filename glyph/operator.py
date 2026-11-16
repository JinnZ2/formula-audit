"""operator -- the glyph: one reasoning step at a time. Co-authored.

Definition: the README section "Glyph (branch 3 reasoning operator)".

  input     purpose (SOLVE + target | EXPLORE), environment (references to
            records of branches 1 / 2a / 2b / 4 / 5, re-read), energy_budget,
            time_budget ({available, reserve}), needed_function_met (y / n /
            VOID), now, drift_rate. No purpose -> VOID; it is never defaulted.
  gate      EXPLORE only if needed_function_met = y AND energy surplus AND
            time surplus (available above reserve). Any "n" -> SOLVE. Anything
            VOID -> VOID, naming which.
  options   every tool of the tool table whose needed features are present in
            the environment and whose cost the energy available covers; and
            inaction, always. cost(inaction) = drift_rate x time since the
            newest environment record. No drift_rate, or a cost that comes to
            0 -> VOID: no ranking. It is never taken as zero.
  SOLVE     each option is a rival "this option moves toward the target";
            the rivals are ranked by branch 5 (infer) posterior x 1 / cost.
            All rivals are recorded, not only the winner.
  EXPLORE   tools whose features are present but unpaired (no candidate made
            from that instance yet); the first in table order. If none:
            inaction.
  one step  the chosen tool turns one feature instance into one candidate,
            written to proposals.json (the 2b seam); the environment is read
            again; the next step is chosen from the new state. Every step is
            logged; replay(log) reproduces the state.
  ceiling   nothing the glyph writes is above PROPOSED. Only checks by 2a /
            2b move anything further, and they are not run here.
"""
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

from infer.ladder import Void, rank as infer_rank

from .environment import FEATURES, read_environment
from .tools import TABLE_V0, _ref, apply_tool

VERSION = "glyph branch3-0"
MODES = ("SOLVE", "EXPLORE")
CASE_FIELDS = ("purpose", "environment", "energy_budget", "time_budget", "needed_function_met",
               "now", "drift_rate", "inaction_time", "tools", "evidence", "priors",
               "proposals", "note")


def _frac(x, what):
    if isinstance(x, bool) or x is None or isinstance(x, float):
        raise Void(f"{what} is VOID" if x is None else f"{what}: not an exact number")
    try:
        return Fraction(x)
    except (ValueError, ZeroDivisionError, TypeError):
        raise Void(f"{what}: cannot read {x!r} as a number")


def _budget(b, what):
    if not isinstance(b, dict) or b.get("available") is None or b.get("reserve") is None:
        raise Void(f"{what} is VOID (needs available and reserve)")
    return {"available": _frac(b["available"], f"{what}.available"),
            "reserve": _frac(b["reserve"], f"{what}.reserve")}


def candidate_key(tool, inst):
    text = tool + "|" + "|".join(sorted(r["sha256"] for r in inst["sources"])) \
        + "|" + str(inst.get("p", "")) + "|" + str(inst.get("q", ""))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_proposals(path):
    if not Path(path).exists():
        return {"proposals": [], "questions": []}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Void(f"cannot read {path}: {type(e).__name__}")
    if isinstance(data, list):
        data = {"proposals": data}
    if not isinstance(data, dict) or not isinstance(data.get("proposals"), list):
        raise Void(f"{path} is not a proposals file")
    data.setdefault("questions", [])
    return data


def _paired(data):
    return {e["glyph"]["key"] for part in ("proposals", "questions") for e in data[part]
            if isinstance(e, dict) and isinstance(e.get("glyph"), dict)}


def read_state(case):
    """The mutable part of a case, as exact numbers. Raises Void naming what is VOID."""
    return {"energy": _budget(case.get("energy_budget"), "energy_budget"),
            "time": _budget(case.get("time_budget"), "time_budget"),
            "now": _frac(case.get("now"), "now")}


def gate(purpose, case, state):
    """The mode this step runs in, and why."""
    if not isinstance(purpose, dict) or purpose.get("mode") is None:
        raise Void("purpose is missing: it is an input and is never defaulted")
    mode = purpose["mode"]
    if mode not in MODES:
        raise Void(f"purpose mode {mode!r} is not SOLVE or EXPLORE")
    if mode == "SOLVE":
        if not purpose.get("target"):
            raise Void("purpose SOLVE needs a target")
        return "SOLVE", {"asked": "SOLVE", "gate": "not applied: SOLVE was asked for"}
    met = case.get("needed_function_met", "VOID")
    if met not in ("y", "n", "VOID"):
        raise Void(f"needed_function_met {met!r} is not y, n or VOID")
    e_surplus = state["energy"]["available"] - state["energy"]["reserve"]
    t_surplus = state["time"]["available"] - state["time"]["reserve"]
    answers = {"needed_function_met": met,
               "energy_surplus": "y" if e_surplus > 0 else "n",
               "time_surplus": "y" if t_surplus > 0 else "n"}
    detail = {"asked": "EXPLORE", "answers": answers,
              "energy_surplus_amount": str(e_surplus), "time_surplus_amount": str(t_surplus)}
    if met == "VOID":
        raise Void("gate: needed_function_met is VOID")
    no = [k for k, v in answers.items() if v == "n"]
    if no:
        if not purpose.get("target"):
            raise Void("gate turns EXPLORE to SOLVE (" + ", ".join(no)
                       + " = n), and the purpose names no target to solve for")
        return "SOLVE", {**detail, "gate": "EXPLORE refused: " + ", ".join(no) + " = n"}
    return "EXPLORE", {**detail, "gate": "EXPLORE allowed: function met, energy and time "
                                         "in surplus"}


def options(case, env, state, paired):
    """Every option with why it is or is not open. Raises Void when inaction
    has no cost: then nothing can be ranked."""
    table = case.get("tools") or TABLE_V0
    rate = case.get("drift_rate")
    if rate is None:
        raise Void("drift_rate is VOID: inaction has no cost, so nothing is ranked "
                   "(it is never taken as zero)")
    rate = _frac(rate, "drift_rate")
    since = state["now"] - env["newest"]
    drift = rate * since
    if drift <= 0:
        raise Void(f"inaction cost comes to {drift} (rate {rate} x time since the newest "
                   f"record {since}); it is not taken as zero: nothing is ranked")
    out = []
    for t in table:
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) \
                or not isinstance(t.get("needs"), list):
            raise Void("tool table: an entry needs name and needs")
        if t.get("status") != "PROPOSED":
            raise Void(f"tool {t['name']!r}: tool table entries are PROPOSED")
        unknown = [f for f in t["needs"] if f not in FEATURES]
        if unknown:
            raise Void(f"tool {t['name']!r} needs an unknown feature {unknown[0]!r}")
        cost = _frac(t.get("cost"), f"cost of {t['name']}")
        if cost <= 0:
            raise Void(f"cost of {t['name']} is not above 0")
        time = _frac(t.get("time", 1), f"time of {t['name']}")
        missing = [f for f in t["needs"] if not env["features"][f]]
        insts = [] if missing or not t["needs"] else env["features"][t["needs"][0]]
        unpaired = [i for i in insts if candidate_key(t["name"], i) not in paired]
        o = {"name": t["name"], "kind": "tool", "cost": cost, "time": time,
             "needs": t["needs"], "instances": len(insts), "unpaired": len(unpaired),
             "open": True, "why_not": None, "_insts": unpaired}
        if missing:
            o.update(open=False, why_not="feature not in the environment: " + ", ".join(missing))
        elif cost > state["energy"]["available"]:
            o.update(open=False, why_not=f"costs {cost}, energy available "
                                         f"{state['energy']['available']}")
        elif not unpaired:
            o.update(open=False, why_not="every instance already has a candidate")
        out.append(o)
    wait = _frac(case.get("inaction_time", 1), "inaction_time")
    out.append({"name": "inaction", "kind": "inaction", "cost": drift, "time": wait,
                "needs": [], "instances": None, "unpaired": None, "open": True,
                "why_not": None, "_insts": [],
                "cost_is": f"drift: rate {rate} x time since the newest record {since}"})
    return out


def choose_solve(case, opts):
    rivals = [o for o in opts if o["open"]]
    if len(rivals) == 1:
        return rivals[0], [{"name": rivals[0]["name"], "posterior": None,
                            "cost": str(rivals[0]["cost"]), "score": None}], \
            "the only open option", None
    names = {o["name"] for o in rivals}
    priors = case.get("priors") or {}
    hyps = [{"id": o["name"], "statement": f"{o['name']} moves toward the target",
             **({"prior": priors[o["name"]]["prior"],
                 "prior_source": priors[o["name"]].get("prior_source")}
                if isinstance(priors.get(o["name"]), dict) else {"prior_flag": "unknown"})}
            for o in rivals]
    evidence = [e for e in (case.get("evidence") or [])
                if not isinstance(e, dict) or e.get("hypothesis") in names
                or (e.get("type") == "shadow"
                    and set(e.get("consistent_with") or []) <= names)]
    rep = infer_rank({"hypotheses": hyps, "evidence": evidence})
    if rep["verdict"] != "RANKED":
        raise Void(f"branch 5 could not rank the options: {rep['void_reason']}")
    post = {h["id"]: Fraction(h["posterior"]) for h in rep["hypotheses"]}
    table = sorted(({"name": o["name"], "posterior": str(post[o["name"]]),
                     "cost": str(o["cost"]), "score": str(post[o["name"]] / o["cost"]),
                     "direction": next(h["direction"] for h in rep["hypotheses"]
                                       if h["id"] == o["name"])} for o in rivals),
                   key=lambda r: (-Fraction(r["score"]), r["name"]))
    tie = len(table) > 1 and table[0]["score"] == table[1]["score"]
    best = next(o for o in rivals if o["name"] == table[0]["name"])
    return best, table, "highest posterior x 1 / cost" + (
        "; tied with " + table[1]["name"] + ", taken by name" if tie else ""), \
        {"evidence_used": len(evidence), "counts": rep["counts"],
         "status": rep["status"], "prior": rep["log"][1]["op"]}


def choose_explore(opts):
    tools = [o for o in opts if o["kind"] == "tool" and o["open"]]
    table = [{"name": o["name"], "unpaired": o["unpaired"], "cost": str(o["cost"])}
             for o in opts if o["kind"] == "tool"]
    if tools:
        return tools[0], table, "first tool in table order with a feature present and unpaired"
    return opts[-1], table, "no tool has an unpaired feature: inaction"


def step(case, state, base_dir, n, log, write=True):
    """One step. Appends to log; returns the log entry."""
    entry = {"step": n, "verdict": "VOID", "void_reason": None, "status": None,
             "purpose": case.get("purpose"), "mode": None, "gate": None,
             "environment": None, "options": None, "rivals": None, "chosen": None,
             "choice_reason": None, "infer": None, "candidate": None,
             "state_before": _show(state), "state_after": _show(state)}
    log.append(entry)
    try:
        extra = [k for k in case if k not in CASE_FIELDS]
        if extra:
            raise Void(f"undeclared field {extra[0]!r}")
        mode, entry["gate"] = gate(case.get("purpose"), case, state)
        entry["mode"] = mode
        env = read_environment(case.get("environment"), base_dir)
        ppath = Path(base_dir or ".") / case.get("proposals", "proposals.json")
        data = read_proposals(ppath)
        paired = _paired(data)
        entry["environment"] = {
            "references": len(env["records"]), "all_re_read": True,
            "newest": str(env["newest"]),
            "features": {f: len(v) for f, v in env["features"].items()},
            "candidates_already_made": len(paired)}
        opts = options(case, env, state, paired)
        entry["options"] = [{k: (str(v) if isinstance(v, Fraction) else v)
                             for k, v in o.items() if k != "_insts"} for o in opts]
        if mode == "SOLVE":
            best, entry["rivals"], entry["choice_reason"], entry["infer"] = \
                choose_solve(case, opts)
        else:
            best, entry["rivals"], entry["choice_reason"] = choose_explore(opts)
        entry["chosen"] = best["name"]
        delta = {"energy": Fraction(0), "time": best["time"]}
        if best["kind"] == "tool":
            inst = best["_insts"][0]
            kind, body = apply_tool(best["name"], inst)
            key = candidate_key(best["name"], inst)
            cand = {**body, "status": "PROPOSED", "tag": mode,
                    "proof": None, "proof_attempted": False,
                    "glyph": {"key": key, "tool": best["name"], "tool_status": "PROPOSED",
                              "step": n, "mode": mode,
                              "target": (case["purpose"].get("target")
                                         if mode == "SOLVE" else None),
                              "sources": [_ref(r) for r in inst["sources"]]},
                    "ceiling": "PROPOSED: only a 2a / 2b check moves this further",
                    "human_interest": None, "ai_interest": None}
            part = "proposals" if kind == "proposal" else "questions"
            data[part].append(cand)
            data.setdefault("note", "candidates; each entry carries its own status")
            if write:
                tmp = ppath.with_name(ppath.name + ".tmp")
                tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
                os.replace(tmp, ppath)
            entry["candidate"] = {"key": key, "kind": kind, "written_to": str(ppath.name),
                                  "list": part, "status": "PROPOSED", "tag": mode,
                                  "lhs": body.get("lhs"), "rhs": body.get("rhs"),
                                  "word": body.get("word")}
            delta["energy"] = best["cost"]
            if write:                                 # read the world again before going on
                env2 = read_environment(case.get("environment"), base_dir)
                entry["environment_after"] = {
                    "features": {f: len(v) for f, v in env2["features"].items()},
                    "candidates_made": len(_paired(read_proposals(ppath)))}
        state["energy"]["available"] -= delta["energy"]
        state["time"]["available"] -= delta["time"]
        state["now"] += delta["time"]
        entry["delta"] = {"energy": str(delta["energy"]), "time": str(delta["time"])}
        entry["state_after"] = _show(state)
        entry.update(verdict="STEPPED", status="PROPOSED")
    except Void as v:
        entry.update(verdict="VOID", void_reason=str(v), status=None)
    except Exception as e:                       # fail closed
        entry.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}",
                     status=None)
    return entry


def _show(state):
    return {"energy_available": str(state["energy"]["available"]),
            "energy_reserve": str(state["energy"]["reserve"]),
            "time_available": str(state["time"]["available"]),
            "time_reserve": str(state["time"]["reserve"]), "now": str(state["now"])}


def run(case, base_dir=None, steps=1, write=True):
    log = []
    rep = {"tool": VERSION, "verdict": "VOID", "void_reason": None, "status": None,
           "ceiling": "nothing the glyph writes is above PROPOSED",
           "tool_table": "v0, every entry PROPOSED" if not (isinstance(case, dict)
                                                            and case.get("tools")) else "case",
           "steps_asked": steps, "log": log, "human_interest": None, "ai_interest": None}
    try:
        if not isinstance(case, dict):
            raise Void("case is not a record")
        state = read_state(case)
    except Void as v:
        rep["void_reason"] = str(v)
        return rep
    log.append({"step": 0, "verdict": "INIT", "state_after": _show(state)})
    for n in range(1, steps + 1):
        e = step(case, state, base_dir, n, log, write)
        if e["verdict"] == "VOID":
            rep["void_reason"] = f"step {n}: {e['void_reason']}"
            break
    done = [e for e in log if e["verdict"] == "STEPPED"]
    rep["steps_done"] = len(done)
    rep["candidates"] = [e["candidate"]["key"] for e in done if e["candidate"]]
    rep["final_state"] = log[-1]["state_after"] if log else None
    if len(done) == steps:
        rep.update(verdict="STEPPED", status="PROPOSED")
    rep["replay_matches"] = replay(log) == {"state": rep["final_state"],
                                            "candidates": rep["candidates"]}
    return rep


def replay(log):
    """The final state and the candidates made, from the log alone."""
    state, cands = None, []
    for e in log:
        if e["verdict"] == "INIT":
            state = dict(e["state_after"])
        elif e["verdict"] == "STEPPED":
            state["energy_available"] = str(Fraction(state["energy_available"])
                                            - Fraction(e["delta"]["energy"]))
            state["time_available"] = str(Fraction(state["time_available"])
                                          - Fraction(e["delta"]["time"]))
            state["now"] = str(Fraction(state["now"]) + Fraction(e["delta"]["time"]))
            if e["candidate"]:
                cands.append(e["candidate"]["key"])
    return {"state": state, "candidates": cands}
