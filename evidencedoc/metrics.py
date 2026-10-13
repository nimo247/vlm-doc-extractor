"""Transparent task metrics. Do not equate quote consistency with visual grounding."""
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation
from itertools import combinations
from .schema import Document, normalized


def ratio(n,d):
    return n/d if d else None


def iou(a,b):
    intersection=max(0,min(a.x1,b.x1)-max(a.x0,b.x0))*max(0,min(a.y1,b.y1)-max(a.y0,b.y0))
    union=(a.x1-a.x0)*(a.y1-a.y0)+(b.x1-b.x0)*(b.y1-b.y0)-intersection
    return intersection/union if union else 0


def field_value(name,value):
    if value is None:return None
    if name=="total":
        try:return str(Decimal(value.replace(",","").strip()).normalize())
        except InvalidOperation:pass
    return normalized(value)


def edit_distance(a,b):
    previous=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current=[i]
        for j,cb in enumerate(b,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous=current
    return previous[-1]


def score(gold:Document,pred:Document|None)->dict:
    gf={f.name:f for f in gold.fields}; pf={f.name:f for f in pred.fields} if pred else {}
    raw={"field_correct":0,"field_count":len(gf),"emitted_correct":0,"emitted_count":0,"missing_gold_count":0,"false_on_missing":0,"unsupported_literal_count":0,"table_cell_correct":0,"table_cell_count":0,"order_correct":0,"order_count":0,"matched_blocks":0,"gold_blocks":sum(len(p.blocks) for p in gold.pages)}
    gold_text=normalized("\n".join(b.content() for p in gold.pages for b in p.blocks))
    for name,f in gf.items():
        candidate=pf.get(name)
        correct=candidate is not None and field_value(name,candidate.value)==field_value(name,f.value)
        raw["field_correct"]+=int(correct)
        if f.value is None:
            raw["missing_gold_count"]+=1
            raw["false_on_missing"]+=int(candidate is not None and candidate.value is not None)
    for name,f in pf.items():
        if f.value is not None:
            raw["emitted_count"]+=1
            raw["emitted_correct"]+=int(name in gf and field_value(name,f.value)==field_value(name,gf[name].value))
            raw["unsupported_literal_count"]+=int(normalized(f.value) not in gold_text)
    for page in gold.pages:
        predicted=pred.pages[page.index].blocks if pred and page.index<len(pred.pages) else []
        # Greedy one-to-one matching by region overlap + text similarity, with explicit thresholds.
        candidates=[]
        for gi,g in enumerate(page.blocks):
            for pi,p in enumerate(predicted):
                if g.type!=p.type:continue
                overlap=iou(g.bbox,p.bbox)
                similarity=SequenceMatcher(None,normalized(g.content()),normalized(p.content())).ratio()
                if overlap>=.1 and similarity>=.35:
                    candidates.append((overlap+similarity,gi,pi))
        matched={};used=set()
        for _,gi,pi in sorted(candidates,reverse=True):
            if gi not in matched and pi not in used:matched[gi]=pi;used.add(pi)
        raw["matched_blocks"]+=len(matched)
        for ga,gb in combinations(sorted(matched),2):
            raw["order_count"]+=1
            raw["order_correct"]+=int(matched[ga]<matched[gb])
        seen_tables=set()
        for gi,g in enumerate(page.blocks):
            if g.type!="table":continue
            p=predicted[matched[gi]] if gi in matched else None
            if p:seen_tables.add(matched[gi])
            gr=len(g.rows);gc=len(g.rows[0]);pr=len(p.rows) if p else 0;pc=len(p.rows[0]) if p else 0
            raw["table_cell_count"]+=max(gr,pr)*max(gc,pc)
            if p:
                raw["table_cell_correct"]+=sum(normalized(g.rows[r][c])==normalized(p.rows[r][c]) for r in range(min(gr,pr)) for c in range(min(gc,pc)))
        for pi,p in enumerate(predicted):
            if p.type=="table" and pi not in seen_tables:
                raw["table_cell_count"]+=len(p.rows)*len(p.rows[0])
    pred_text=normalized("\n".join(b.content() for p in pred.pages for b in p.blocks)) if pred else ""
    raw["character_edits"]=edit_distance(gold_text,pred_text)
    raw["gold_characters"]=len(gold_text)
    return raw


def summarize(raw:dict)->dict:
    return {"field_accuracy":ratio(raw["field_correct"],raw["field_count"]),"emitted_field_accuracy":ratio(raw["emitted_correct"],raw["emitted_count"]),"unsupported_literal_value_rate":ratio(raw["unsupported_literal_count"],raw["emitted_count"]),"false_extraction_on_absent_fields_rate":ratio(raw["false_on_missing"],raw["missing_gold_count"]),"table_cell_accuracy":ratio(raw["table_cell_correct"],raw["table_cell_count"]),"reading_order_pair_accuracy":ratio(raw["order_correct"],raw["order_count"]),"block_match_recall":ratio(raw["matched_blocks"],raw["gold_blocks"]),"character_error_rate":ratio(raw["character_edits"],raw["gold_characters"]),"raw_counts":raw}
