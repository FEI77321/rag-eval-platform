"""Non-destructive metric views based on explicitly attributed review records."""
from types import SimpleNamespace
from sqlalchemy import select
from .models import Item, Adjudication
from .metrics import calculate, aggregate, suggest_tags


def review_view(db, run, enabled=False):
    originals = db.scalars(select(Item).where(Item.run_id == run.id).order_by(Item.case_id, Item.config_id)).all()
    reviews = {r.item_id: r.payload for r in db.scalars(select(Adjudication).join(Item, Item.id == Adjudication.item_id).where(Item.run_id == run.id)).all()}
    if not enabled:
        return originals, reviews
    cases = {c['id']: c for c in run.snapshot['cases']}
    rows = []
    for item in originals:
        if item.id not in reviews:
            rows.append(item)
            continue
        scores = reviews[item.id]['scores']
        metrics = calculate(cases[item.case_id], item.generation,
                            {**item.judgement, 'scores': scores}, run.snapshot['prices'])
        tags = suggest_tags(cases[item.case_id], metrics, item.generation, scores)
        rows.append(SimpleNamespace(**{key: value for key, value in vars(item).items() if key != '_sa_instance_state'} | {'metrics': metrics, 'tags': list(dict.fromkeys(item.tags + tags))}))
    return rows, reviews


def reviewed_aggregate(db, run, enabled=False):
    rows, reviews = review_view(db, run, enabled)
    result = aggregate(rows)
    # Agreement is always the original saved human scores vs original Judge.
    # Do not present agreement against AI-corrected metrics as human validation.
    baseline, _ = review_view(db, run, False) if enabled and reviews else (rows, reviews)
    raw = {r['config_id']: r for r in aggregate(baseline)}
    for row in result:
        for key in ('score_agreement', 'classification_agreement', 'agreement_n'):
            row[key] = raw[row['config_id']][key]
        row['adjudication_count'] = sum(i.id in reviews for i in rows if i.config_id == row['config_id'])
    return result, reviews
