"""Re-score a banked raw.jsonl offline ($0, no pod). Usage: python scripts/rescore_raw.py <raw.jsonl>"""
import json, sys, statistics as st
from tests.persona_evaluation.personas import get_persona_by_name
from tests.persona_evaluation.evaluation_scoring import ResultEvaluator
from scripts.eval_hardware_matrix import submetrics
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
ov, sp, rc, au, gr = [], [], [], [], []
for r in rows:
    try: p = get_persona_by_name(r["persona"])
    except Exception: continue
    s = ResultEvaluator.evaluate_search_result(r["result"], p, r["variant"])
    _, _, grounded = submetrics(s)
    ov.append(s["overall_score"]); sp.append(s["avg_spot_score"]); rc.append(s["avg_rec_score"])
    if s.get("blind_spot_auth_grounded_pct") is not None: au.append(s["blind_spot_auth_grounded_pct"])
    if grounded is not None: gr.append(grounded)
m = lambda x: round(st.mean(x), 3) if x else None
print("n=%d  overall=%s  spot=%s  rec=%s  auth%%=%s  posting_grounded%%=%s" % (
    len(ov), m(ov), m(sp), m(rc), m(au), m(gr)))
