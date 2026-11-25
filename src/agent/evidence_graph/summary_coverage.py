"""Conservative E2 fallback: measurable retention is necessary, never sufficient."""
from __future__ import annotations
import re
try:
    from ..quantity_grounding import quantities, comparison_text
except ImportError:
    from quantity_grounding import quantities, comparison_text

_CONDITIONS = (
    ('near_neutral',r'近中性|near[- ]neutral'),
    ('acidic',r'酸性|\bacidic\b'), ('alkaline',r'碱性|\balkaline\b'),
    ('all_iron',r'全铁|all[- ]iron'), ('iron_chromium',r'铁铬|iron[- ]chromium|\bICRFB\b'),
    ('glycine',r'甘氨酸|\bglycine\b'), ('imidazole',r'咪唑|imidazole'),
    ('drying',r'干燥|\bdry(?:ing)?\b'), ('melting',r'熔融|熔化|\bmelt(?:ing)?\b'),
    ('stirring',r'搅拌|\bstirr?ing\b'), ('cooling',r'冷却|\bcool(?:ing)?\b'),
    ('adsorption',r'吸附|adsorption'), ('capillarity',r'毛细|capillar'),
)


def check_summary_coverage(question, full_context, summary, plan=None):
    full, brief = comparison_text(full_context), comparison_text(summary)
    expected = {(q.dimension,str(q.base_value.normalize())):q.raw for q in quantities(full)}
    kept = {(q.dimension,str(q.base_value.normalize())) for q in quantities(brief)}
    missing = [raw for key,raw in expected.items() if key not in kept]
    conditions = [name for name,pattern in _CONDITIONS
                  if re.search(pattern,full,re.I) and not re.search(pattern,brief,re.I)]
    # Ratios can be central even without a physical unit (e.g. 6:4).
    ratios = set(re.findall(r'(?<![\d.])\d+(?:\.\d+)?\s*[:∶]\s*\d+(?:\.\d+)?(?![\d.])',full))
    brief_ratios = set(re.findall(r'(?<![\d.])\d+(?:\.\d+)?\s*[:∶]\s*\d+(?:\.\d+)?(?![\d.])',brief))
    ratios = sorted(re.sub(r'\s+','',r) for r in ratios
                    if re.sub(r'\s+','',r) not in {re.sub(r'\s+','',b) for b in brief_ratios})
    missing_requirements=[]
    for item in plan or []:
        # A requirement with no currently selected source cannot be presumed
        # covered merely because the planner marked it done.
        source_ids=item.get('evidence_source_ids') or []
        if not source_ids or not any(source_id in summary for source_id in source_ids):
            missing_requirements.append(str(item.get('step') or '未具名需求'))
    passed=bool(summary.strip()) and not (missing or conditions or ratios or missing_requirements)
    return {'passed':passed,'policy':'conservative_quantity_condition_requirement_retention_v1',
            'missing_quantities':missing[:40],'missing_quantity_count':len(missing),
            'missing_conditions':conditions,'missing_ratios':ratios[:20],
            'requirements_without_selected_source':missing_requirements,
            'semantic_coverage_verified':False,
            'note':'保留检查是必要条件；通过不证明语义覆盖。任何缺口均回退完整融合证据；不将回退计为摘要节省。'}
