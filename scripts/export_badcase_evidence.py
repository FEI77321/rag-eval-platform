"""Export evidence-backed Bad Case examples from a saved run, plus labeled controls.

No model calls are made. The two knowledge-base-missing cases are explicitly
counterfactual fixtures because the real 700-item run had zero failures in that
category; they must never be counted as cloud observations.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db import Session
from app.models import Item, Run

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "run-54107b88329d40c8"

CASES = {
    "分块问题": [
        ("AI-024", "cloud-v2-05"),
        ("AI-078", "cloud-v2-05"),
    ],
    "召回失败": [
        ("AI-002", "cloud-v2-01"),
        ("AI-015", "cloud-v2-01"),
    ],
    "排序问题": [
        ("AI-008", "cloud-v2-01"),
        ("AI-009", "cloud-v2-01"),
    ],
    "生成幻觉": [
        ("AI-007", "cloud-v2-01"),
        ("AI-037", "cloud-v2-03"),
    ],
    "提示词问题": [
        ("AI-017", "cloud-v2-04"),
        ("AI-048", "cloud-v2-01"),
    ],
}

FIXTURES = [
    {
        "id": "KB-CONTROL-01",
        "case_id": "AI-091",
        "question": "飞的公司生产FastAPI服务今天的部署版本号是什么？",
        "gold_answer": "公开教程不含该私有生产信息，应说明依据不足并拒绝编造。",
        "evidence_state": "gold_doc和gold_chunk_id为空；该信息不在已索引语料中。",
        "injected_answer": "受控错误输出：生产部署版本是 v9.9.9。",
        "expected_diagnosis": "知识库缺失导致无证据作答；测试输出是人工注入的假值，不是真实模型回答。",
        "recommendation": "设置来源范围与拒答边界；若该信息确需回答，应先取得授权并补充可审计的内部资料。",
    },
    {
        "id": "KB-CONTROL-02",
        "case_id": "AI-092",
        "question": "我们学校内部FastAPI选课系统下周具体哪一天停机维护？",
        "gold_answer": "公开教程不含该私有系统运维安排，应说明依据不足并拒绝编造。",
        "evidence_state": "gold_doc和gold_chunk_id为空；该信息不在已索引语料中。",
        "injected_answer": "受控错误输出：系统将于下周三停机维护。",
        "expected_diagnosis": "知识库缺失导致无证据作答；答案中的日期是人工注入的假值，不是真实系统信息。",
        "recommendation": "只从经过授权的运维公告中回答；检索不到时明确拒答，并记录需要补充的资料来源。",
    },
]

IMPROVEMENTS = {
    "分块问题": "检查证据句是否被块边界截断；按句子边界调整块长与重叠，并对长证据保留可追溯坐标。",
    "召回失败": "先检查标准证据是否进入候选池；结合中文查询改写、混合检索和Top-K做单变量回归。",
    "排序问题": "扩大候选池后比较最终Top-K；使用重排时记录排序前后名次，确认正确证据没有被截断。",
    "生成幻觉": "对照回答中的每项事实与证据；要求逐项引用可支持的片段，并对矛盾答案做回归测试。",
    "提示词问题": "检查证据充分时是否仍被过度拒答；调整拒答判定条件，并用可回答/不可回答成对题验证。",
}


def compact_chunk(chunk: dict) -> dict:
    return {
        "id": chunk.get("id"),
        "doc_id": chunk.get("doc_id"),
        "start": chunk.get("start"),
        "end": chunk.get("end"),
        "text": chunk.get("text"),
    }


def main() -> None:
    exported: list[dict] = []
    with Session() as db:
        run = db.get(Run, RUN_ID)
        if run is None:
            raise SystemExit(f"Run not found: {RUN_ID}")
        by_case = {case["id"]: case for case in run.snapshot["cases"]}
        for tag, pairs in CASES.items():
            for case_id, config_id in pairs:
                row = db.scalar(
                    select(Item).where(
                        Item.run_id == RUN_ID,
                        Item.case_id == case_id,
                        Item.config_id == config_id,
                    )
                )
                if row is None or row.state != "succeeded":
                    raise SystemExit(f"Missing successful result: {case_id}/{config_id}")
                case = by_case[case_id]
                generation = row.generation or {}
                exported.append(
                    {
                        "origin": "real_cloud_run",
                        "run_id": RUN_ID,
                        "item_id": row.id,
                        "category": tag,
                        "case_id": case_id,
                        "config_id": config_id,
                        "question": case["question"],
                        "gold_answer": case.get("gold_answer"),
                        "gold_evidence": case.get("evidence", []),
                        "gold_chunk_ids": case.get("gold_chunk_id", []),
                        "answer": generation.get("answer"),
                        "final_context_chunks": [compact_chunk(x) for x in generation.get("chunks", [])],
                        "candidate_chunks": [compact_chunk(x) for x in generation.get("candidates", [])],
                        "metrics": row.metrics,
                        "judge": row.judgement,
                        "human_review": row.human_review,
                        "tags": row.tags,
                        "note": row.note,
                    }
                )
        for fixture in FIXTURES:
            case = by_case[fixture["case_id"]]
            if case.get("gold_doc") or case.get("gold_chunk_id") or case.get("evidence"):
                raise SystemExit(f"Control is not out-of-scope: {fixture['case_id']}")
            exported.append(
                {
                    "origin": "controlled_counterfactual_not_cloud_observation",
                    "run_id": RUN_ID,
                    "category": "知识库缺失",
                    **fixture,
                    "actual_dataset_question": case["question"],
                }
            )

    payload = {
        "run_id": RUN_ID,
        "normal_run_badcase_counts": {
            "分块问题": 0,
            "召回失败": 0,
            "排序问题": 0,
            "生成幻觉": 0,
            "提示词问题": 0,
            "知识库缺失": 0,
        },
        "note": "每条真实样例保留原始答案、gold证据、最终上下文与候选池；控制案例标记为counterfactual，不计入700条真实跑批。",
        "examples": exported,
    }
    # Refresh counts from the database labels rather than trusting a hand-entered tally.
    from collections import Counter

    with Session() as db:
        rows = db.scalars(select(Item).where(Item.run_id == RUN_ID)).all()
        failures = [r for r in rows if r.metrics and not r.metrics.get("task_success")]
        counts = Counter(tag for row in failures for tag in (row.tags or []))
        payload["normal_run_badcase_counts"] = {tag: counts[tag] for tag in [
            "分块问题", "召回失败", "排序问题", "生成幻觉", "提示词问题", "知识库缺失"
        ]}

    evidence_path = ROOT / "docs" / "BadCase证据核验.json"
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "reports" / RUN_ID / "BadCase样本.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    names = {
        "分块问题": "chunking boundary",
        "召回失败": "retrieval miss",
        "排序问题": "candidate ranking / Top-K truncation",
        "生成幻觉": "unsupported or contradicted generation",
        "提示词问题": "over-refusal despite evidence",
    }
    sections = [
        "# Bad Case分析报告：证据核验版",
        "",
        f"运行：`{RUN_ID}`（700条真实云端结果，历史评测等级仍是`ai_preliminary`）。本报告以原始题目、gold证据、候选池、最终上下文、模型回答及Judge记录交叉核验；每条样例完整快照见`docs/BadCase证据核验.json`。",
        "",
        "标签为多标签归因。除知识库缺失外，下面前五类来自真实云端失败结果；知识库缺失在700条正式结果中观测为0，因此仅附两条明确的受控反事实案例，不计入真实指标或正式观察结论。受控答案值是测试注入值，不是真实信息。",
        "",
        "## 真实跑批标签分布",
        "",
        "|标签|失败结果数|说明|",
        "|---|---:|---|",
    ]
    counts = payload["normal_run_badcase_counts"]
    for tag, count in counts.items():
        origin = "正式结果未观测到；仅列受控验证" if tag == "知识库缺失" and count == 0 else "真实失败结果，多标签统计"
        sections.append(f"|{tag}|{count}|{origin}|")
    sections += ["", "## 真实云端案例", ""]
    records = [x for x in exported if x["origin"] == "real_cloud_run"]
    for tag in CASES:
        sections += [f"### {tag}", "", f"改进建议：{IMPROVEMENTS[tag]}", ""]
        for rec in [x for x in records if x["category"] == tag]:
            ev = rec["gold_evidence"]
            evtext = "；".join(f"`{e['doc_id']}:{e.get('start')}-{e.get('end')}`：{e['quote']}" for e in ev)
            final_ids = ", ".join(x["id"] for x in rec["final_context_chunks"])
            cand_ids = ", ".join(x["id"] for x in rec["candidate_chunks"])
            sections += [
                f"#### {rec['case_id']} / {rec['config_id']}（item `{rec['item_id']}`）",
                "",
                f"- 问题：{rec['question']}",
                f"- 标准答案：{rec['gold_answer']}",
                f"- 标准证据：{evtext or '题型为知识库范围外拒答，无知识库证据。'}",
                f"- 候选池证据块：{cand_ids or '无'}",
                f"- 实际送入生成的上下文块：{final_ids or '无'}",
                f"- 模型原答：{rec['answer']}",
                f"- 运行指标：hit={rec['metrics'].get('hit')}，MRR={rec['metrics'].get('mrr')}，task_success={rec['metrics'].get('task_success')}。",
                f"- 归因证据：{rec['note']}",
                "",
            ]
    sections += [
        "## 知识库缺失：受控反事实验证，不是云端失败案例",
        "",
        "这两条使用真实题集中的范围外问题；标准证据和gold来源为空，符合知识库缺失条件。测试答案由脚本人工注入，目的是验证标签边界和处置流程，不代表模型曾经这样回答。",
        "",
    ]
    for fix in FIXTURES:
        sections += [
            f"### {fix['id']} / {fix['case_id']}",
            "",
            f"- 问题：{fix['question']}",
            f"- 证据状态：{fix['evidence_state']}",
            f"- 注入的错误输出：{fix['injected_answer']}",
            f"- 预期归因：{fix['expected_diagnosis']}",
            f"- 改进建议：{fix['recommendation']}",
            "",
        ]
    sections += [
        "## 证据限制",
        "",
        "1. 标签说明失败链路中的可观察环节，不自动证明单一根因；提示词问题尤其需要固定模型、上下文和问题后做Prompt A/B才能作因果结论。",
        "2. 同一题的不同配置结果不是独立题目样本。报告保留配置和item ID，避免把跨配置重复误报为多个独立用户问题。",
        "3. Judge理由可能与生成原文不一致；出现这种情况时以保存的原始答案和证据为准，Judge结论单列为待校准信号。",
        "4. 本报告没有把受控的知识库缺失案例计入真实标签频数，也没有把无依据的真实失败归因为知识库缺失。",
        "",
    ]
    report = "\n".join(sections)
    for path in [ROOT / "docs" / "BadCase分析报告.md", ROOT / "reports" / RUN_ID / "BadCase分析报告.md"]:
        path.write_text(report, encoding="utf-8")
    print(evidence_path)
    print(ROOT / "docs" / "BadCase分析报告.md")


if __name__ == "__main__":
    main()
