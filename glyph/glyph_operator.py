"""glyph_operator -- the glyph: one reasoning step at a time. Co-authored.

Definition: the README section "Glyph (branch 3 reasoning operator)".

  input     purpose (SOLVE + target | EXPLORE), environment (references to
            records of branches 1 / 2a / 2b / 4 / 5, re-read, each with its
            time "at" and its drift "rate"), energy_budget, time_budget
            ({available, reserve}), needed_function_met (y / n / VOID), now,
            units, default_drift_rate (optional). No purpose -> VOID; it is
            never defaulted.
  gate      EXPLORE only if needed_function_met = y AND energy surplus AND
            time surplus (available above reserve). Any "n" -> SOLVE. Anything
            VOID -> VOID, naming which.
  units     the case declares units for energy, cost, time and drift_rate.
            Branch 1 (unitaudit) is run on cost = drift_rate x time and on
            energy = cost; a FAIL or VOID there makes the step VOID.
  options   every tool of the tool table whose needed features are present in
            the environment and whose cost the energy available covers; and
            inaction, always.
            cost(inaction) = sum over the environment references of
                             rate_i x age_i,   age_i = now - at_i
            rate_i is on the reference, or the case's default_drift_rate (its
            use is flagged on the step). A reference with no rate and no
            default -> VOID, naming it. The cost is DERIVED from those inputs.
              every age 0, rates above 0 -> cost 0: the world was just read;
                                            inaction scores 0, and a tool
                                            must have a net score above 0
              a rate of 0 declared       -> VOID: a static world is claimed
                                            and nothing here evidences it
  SOLVE     each option is a rival "this option moves toward the target";
            branch 5 (infer) gives each a posterior. The rivals are ranked by
            NET SCORE, in the cost unit:
                a tool     posterior x gain - cost
                inaction   - sum of rate_i x age_i        (what waiting loses)
            gain is a case input: what moving toward the target is worth, in
            the cost unit (checked by branch 1). No gain -> the step is VOID
            ("gain undeclared"). All rivals are recorded, not only the winner.
            (An earlier rule, posterior x 1 / cost, let a free inaction beat
            any tool whatever the evidence; it is kept only as a regression
            test.)
  EXPLORE   tools whose features are present but unpaired (no candidate made
            from that instance yet); the first in table order. If none:
            inaction.
  one step  the chosen tool turns one feature instance into one candidate,
            written to proposals.json (the 2b seam); the environment is read
            again; the next step is chosen from the new state. Every step is
            logged. The branch 5 input and log of each ranking are saved to a
            file named in the step log with its sha256; replay re-runs branch
            5 from that file and FAILS if the file or the result differs.
  scope     a case may declare the scope its environment was drawn in:
            {place, time, population}. The tool frame_edge then asks four
            questions about what lies past that edge (UPSTREAM, LAG, SHIFT,
            WHOSE), each logged as a slot: answered in the case's frame_edge
            field with a source -> FILLED; otherwise VOID, and kept. Any VOID
            slot raises the case's margin flag: margin_required true, reason
            "unfilled frame-edge slots". Not asked yet -> margin_required null.
            The tool writes questions only; it states nothing about the world.
  ceiling   nothing the glyph writes is above PROPOSED. Only checks by 2a /
            2b move anything further, and they are not run here.
"""
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

from infer.ladder import Void, rank as infer_rank
from unitaudit.check import check_formula as unit_check

from .environment import FEATURES, read_environment
from .tools import TABLE_V0, _ref, apply_tool, margin

VERSION = "glyph branch3-3"
MODES = ("SOLVE", "EXPLORE")
CASE_FIELDS = ("purpose", "environment", "energy_budget", "time_budget", "needed_function_met",
               "now", "default_drift_rate", "units", "gain", "inaction_time", "tools",
               "evidence", "priors", "proposals", "note", "scope", "frame_edge",
               "event_log")
UNIT_FIELDS = ("energy", "cost", "time", "drift_rate")       # always needed
OPTIONAL_UNITS = ("gain",)                                   # needed when a step ranks
LOG_DIR = "glyph_log"


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
    if inst.get("scope") is not None:        # a scope, with the answers given so far
        text += "|" + json.dumps([inst["scope"], inst.get("answers")], sort_keys=True)
    if inst.get("log") is not None:          # an event log, as given
        text += "|" + json.dumps(inst["log"], sort_keys=True)
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


def frame_margin(data, scope):
    """The margin flag of a case, from the newest frame_edge question asked on
    its scope. Not asked yet, or no scope: margin_required stays null."""
    out = {"margin_required": None, "reason": None, "void_slots": None,
           "from": None, "state": "no scope declared" if scope is None
           else "frame_edge has not been asked on this scope"}
    if scope is None:
        return out
    for q in data["questions"]:
        g = q.get("glyph") if isinstance(q, dict) else None
        if isinstance(g, dict) and g.get("tool") == "frame_edge" and q.get("scope") == scope:
            out = {**margin(q["frame_slots"]), "from": g["key"], "state": "asked"}
    return out


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


def check_units(case, env):
    """Branch 1 on the quantities the step adds and compares. Raises Void."""
    units = case.get("units")
    if not isinstance(units, dict):
        raise Void("units are VOID: the case must declare units for "
                   + ", ".join(UNIT_FIELDS))
    extra = [k for k in units if k not in UNIT_FIELDS + OPTIONAL_UNITS]
    if extra:
        raise Void(f"units: undeclared field {extra[0]!r}")
    missing = [k for k in UNIT_FIELDS if not isinstance(units.get(k), str)]
    if missing:
        raise Void("units are VOID for: " + ", ".join(missing))
    checks = [("energy = cost", {"energy": units["energy"], "cost": units["cost"]}, "the case")]
    rate_units = [(units["drift_rate"], "the case's drift_rate unit")] + [
        (r["rate_unit"], f"environment reference {r['index']}")
        for r in env["records"] if r["rate_unit"] is not None]
    for u, where in rate_units:
        checks.append(("cost = rate*dt", {"cost": units["cost"], "rate": u,
                                          "dt": units["time"]}, where))
    out = []
    for formula, symbols, where in checks:
        r = unit_check({"formula": formula, "symbols": symbols})
        out.append({"formula": formula, "units": symbols, "of": where,
                    "verdict": r["verdict"], "status": r["status"]})
        if r["verdict"] != "PASS":
            why = r["void_reason"] if r["verdict"] == "VOID" else (
                r["located_error"]["rule"] + ": " + " vs ".join(r["located_error"]["dims"]))
            raise Void(f"units {r['verdict']} for {formula} ({where}; "
                       + ", ".join(f"{k} in {v}" for k, v in symbols.items()) + f"): {why}")
    return out


def read_gain(case):
    """What moving toward the target is worth, in the cost unit. Raises Void."""
    if case.get("gain") is None:
        raise Void("gain undeclared: a SOLVE step ranks by posterior x gain - cost and "
                   "the case gives no gain")
    gain = _frac(case["gain"], "gain")
    if gain < 0:
        raise Void("gain is below 0")
    units = case.get("units") or {}
    if not isinstance(units.get("gain"), str):
        raise Void("units are VOID for: gain")
    r = unit_check({"formula": "gain = cost",
                    "symbols": {"gain": units["gain"], "cost": units["cost"]}})
    check = {"formula": "gain = cost", "units": {"gain": units["gain"], "cost": units["cost"]},
             "of": "the case's gain", "verdict": r["verdict"], "status": r["status"]}
    if r["verdict"] != "PASS":
        why = r["void_reason"] if r["verdict"] == "VOID" else (
            r["located_error"]["rule"] + ": " + " vs ".join(r["located_error"]["dims"]))
        raise Void(f"units {r['verdict']} for gain = cost (gain in {units['gain']}, cost in "
                   f"{units['cost']}): {why}")
    return gain, check


def inaction_cost(case, env, state):
    """sum of rate_i x age_i. Returns (cost, parts, references on the default).
    Raises Void: a reference with no rate and no default, a rate of 0, a
    reference dated after now."""
    default = case.get("default_drift_rate")
    if default is not None:
        default = _frac(default, "default_drift_rate")
    parts, used_default, total = [], [], Fraction(0)
    for r in env["records"]:
        rate = r["rate"]
        if rate is None:
            if default is None:
                raise Void(f"environment reference {r['index']} ({r['file']}, record "
                           f"{r['record']!r}) has no drift rate and the case gives no "
                           "default_drift_rate: inaction has no cost, so nothing is ranked")
            rate = default
            used_default.append(r["index"])
        if rate == 0:
            raise Void(f"environment reference {r['index']}: drift rate 0 "
                       "(static world claimed, unevidenced)")
        if rate < 0:
            raise Void(f"environment reference {r['index']}: drift rate below 0")
        age = state["now"] - r["at"]
        if age < 0:
            raise Void(f"environment reference {r['index']} is dated after now")
        total += rate * age
        parts.append({"reference": r["index"], "rate": str(rate), "age": str(age),
                      "cost": str(rate * age), "rate_from": "default" if r["rate"] is None
                      else "the reference"})
    return total, parts, used_default


def options(case, env, state, paired):
    """Every option with why it is or is not open. Raises Void when inaction's
    cost cannot be had: then nothing can be ranked."""
    table = case.get("tools") or TABLE_V0
    drift, parts, used_default = inaction_cost(case, env, state)
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
                "why_not": None, "_insts": [], "cost_status": "DERIVED",
                "cost_is": "drift: sum of rate x age over the environment references",
                "cost_parts": parts, "default_rate_used_for": used_default})
    return out


def net_score(kind, post, gain, cost):
    """A tool: posterior x gain - cost. Inaction: - its drift cost."""
    return -cost if kind == "inaction" else post * gain - cost


def choose_solve(case, opts, gain):
    """Returns (best option, rival table, reason, infer summary, infer input)."""
    rivals = [o for o in opts if o["open"]]
    kinds = {o["name"]: o["kind"] for o in rivals}
    costs = {o["name"]: o["cost"] for o in rivals}
    if len(rivals) == 1:
        o = rivals[0]
        return o, [{"name": o["name"], "kind": o["kind"], "posterior": None,
                    "gain": str(gain), "cost": str(o["cost"]),
                    "score": str(-o["cost"]) if o["kind"] == "inaction" else None}], \
            "the only open option", None, None
    names = set(kinds)
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
    infer_input = {"hypotheses": hyps, "evidence": evidence}
    rep = infer_rank(infer_input)
    if rep["verdict"] != "RANKED":
        raise Void(f"branch 5 could not rank the options: {rep['void_reason']}")
    table = rival_table(rep, costs, kinds, gain)
    tie = len(table) > 1 and table[0]["score"] == table[1]["score"]
    best = next(o for o in rivals if o["name"] == table[0]["name"])
    reason = "highest net score (tool: posterior x gain - cost; inaction: - drift)" + (
        "; tied with " + table[1]["name"] + ", taken by name" if tie else "")
    return best, table, reason, \
        {"evidence_used": len(evidence), "counts": rep["counts"],
         "status": rep["status"], "prior": rep["log"][1]["op"]}, \
        {"input": infer_input, "log": rep["log"], "gain": str(gain),
         "score_rule": "tool: posterior x gain - cost; inaction: - sum of rate x age",
         "posteriors": {h["id"]: h["posterior"] for h in rep["hypotheses"]}}


def rival_table(rep, costs, kinds, gain):
    post = {h["id"]: Fraction(h["posterior"]) for h in rep["hypotheses"]}
    rows = []
    for name, cost in costs.items():
        sc = net_score(kinds[name], post[name], gain, cost)
        rows.append({"name": name, "kind": kinds[name], "posterior": str(post[name]),
                     "gain": None if kinds[name] == "inaction" else str(gain),
                     "cost": str(cost), "score": str(sc),
                     "direction": next(h["direction"] for h in rep["hypotheses"]
                                       if h["id"] == name)})
    rows.sort(key=lambda r: (-Fraction(r["score"]), r["name"]))
    return rows


def save_infer(saved, base_dir):
    """Write the branch 5 input and log of one ranking; content-addressed."""
    text = json.dumps(saved, indent=1, sort_keys=True) + "\n"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    folder = Path(base_dir or ".") / LOG_DIR
    folder.mkdir(exist_ok=True)
    path = folder / f"infer_{sha[:16]}.json"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return {"file": f"{LOG_DIR}/{path.name}", "sha256": sha}


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
             "choice_reason": None, "infer": None, "infer_log": None, "units": None,
             "gain": None, "margin": None,
             "candidate": None,
             "state_before": _show(state), "state_after": _show(state)}
    log.append(entry)
    try:
        extra = [k for k in case if k not in CASE_FIELDS]
        if extra:
            raise Void(f"undeclared field {extra[0]!r}")
        mode, entry["gate"] = gate(case.get("purpose"), case, state)
        entry["mode"] = mode
        env = read_environment(case.get("environment"), base_dir, case.get("scope"),
                               case.get("frame_edge"), case.get("event_log"))
        ppath = Path(base_dir or ".") / case.get("proposals", "proposals.json")
        data = read_proposals(ppath)
        paired = _paired(data)
        entry["environment"] = {
            "references": len(env["records"]), "all_re_read": True,
            "newest": str(env["newest"]),
            "features": {f: len(v) for f, v in env["features"].items()},
            "candidates_already_made": len(paired)}
        entry["units"] = check_units(case, env)
        opts = options(case, env, state, paired)
        entry["options"] = [{k: (str(v) if isinstance(v, Fraction) else v)
                             for k, v in o.items() if k != "_insts"} for o in opts]
        if mode == "SOLVE":
            gain, gain_check = read_gain(case)
            entry["units"].append(gain_check)
            entry["gain"] = str(gain)
            best, entry["rivals"], entry["choice_reason"], entry["infer"], saved = \
                choose_solve(case, opts, gain)
            if saved is not None and write:
                entry["infer_log"] = save_infer(saved, base_dir)
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
                                  "word": body.get("word"),
                                  "margin_required": body.get("margin_required"),
                                  "void_slots": body.get("void_slots")
                                  if best["name"] == "frame_edge" else None}
            delta["energy"] = best["cost"]
            if write:                                 # read the world again before going on
                env2 = read_environment(case.get("environment"), base_dir,
                                        case.get("scope"), case.get("frame_edge"),
                                        case.get("event_log"))
                entry["environment_after"] = {
                    "features": {f: len(v) for f, v in env2["features"].items()},
                    "candidates_made": len(_paired(read_proposals(ppath)))}
        entry["margin"] = frame_margin(data, env["scope"])
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
           "margin_required": None, "margin_reason": None, "margin_void_slots": None,
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
    if done and done[-1].get("margin"):
        m = done[-1]["margin"]
        rep.update(margin_required=m["margin_required"], margin_reason=m["reason"],
                   margin_void_slots=m["void_slots"])
    if len(done) == steps:
        rep.update(verdict="STEPPED", status="PROPOSED")
    rep["replay"] = replay(log, base_dir)
    rep["replay_matches"] = (rep["replay"]["verdict"] == "REPRODUCED"
                             and rep["replay"]["state"] == rep["final_state"]
                             and rep["replay"]["candidates"] == rep["candidates"])
    return rep


def replay(log, base_dir=None):
    """The final state and the candidates made, from the log; and every saved
    branch 5 ranking run again from its file. verdict REPRODUCED, or FAILS
    with the step and what differs."""
    state, cands, failures, rerun = None, [], [], 0
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
            ref = e.get("infer_log")
            if ref:
                rerun += 1
                why = _rerun_infer(e, ref, base_dir)
                if why:
                    failures.append({"step": e["step"], "reason": why})
    return {"verdict": "FAILS" if failures else "REPRODUCED", "failures": failures,
            "infer_logs_rerun": rerun, "state": state, "candidates": cands}


def _rerun_infer(entry, ref, base_dir):
    path = Path(base_dir or ".") / ref["file"]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return f"cannot read {ref['file']}: {type(e).__name__}"
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != ref["sha256"]:
        return f"{ref['file']}: sha256 differs from the step log"
    try:
        saved = json.loads(text)
        rep = infer_rank(saved["input"])
        if rep["verdict"] != "RANKED":
            return f"branch 5 does not rank the saved input: {rep['void_reason']}"
        costs = {r["name"]: Fraction(r["cost"]) for r in entry["rivals"]}
        kinds = {r["name"]: r["kind"] for r in entry["rivals"]}
        if saved.get("gain") != entry.get("gain"):
            return "the gain in the saved file is not the gain in the step log"
        again = rival_table(rep, costs, kinds, Fraction(entry["gain"]))
    except Exception as e:
        return f"{ref['file']}: {type(e).__name__}: {e}"
    if again != entry["rivals"]:
        return "branch 5 run again gives a different ranking than the step log"
    if again[0]["name"] != entry["chosen"]:
        return "the option chosen is not the first of the ranking"
    return None
