# RAG Lab · RAG应用质量评测与调优平台

面向RAG配置对比的独立开发项目：知识库来源 → 人工标注题集 → 配置化检索与生成 → 批量评测 → 指标 / 证据 / Bad Case / 人工核验。

**当前状态（2026-10-15）：工程已运行，23项测试通过，真实云服务全部连通；两轮10题×2配置试跑完成，100题×7配置真实云预评测700/700成功。** 候选R07与R03非拒答正确率均71.11%，按MRR选择R07；题集为AI辅助核验，尚需真实人工审核与评分。MySQL实测、远程PR和他人评审未完成。最新交付入口见`docs/交付入口.md`，不得把demo或AI审核记录当作正式验收。

## 快速启动

环境：Python 3.10+；Node 20.19+或22.12+（Vite 7）；正式部署MySQL 8。无需GPU。

Windows PowerShell，在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

脚本创建项目`.venv`、安装依赖、构建前端、复制`.env.example`（仅在`.env`不存在时）、初始化演示题集，并后台启动API与Worker。浏览器访问 `http://127.0.0.1:8010`，接口文档访问 `/docs`。脚本不写入云API密钥。

停止：`powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1`。日志、SQLite数据库与PID记录都在忽略的`runtime/`。

手动启动（Windows）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m app.seed
```

API与Worker分别在两个终端运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
.\.venv\Scripts\python.exe -m app.worker
```

Linux/macOS使用`python -m venv .venv`、`.venv/bin/python`、`npm`及`cp .env.example .env`，其余模块命令相同。不要覆盖已有`.env`。前端开发可用`npm --prefix frontend run dev`，Vite会将`/api`代理至8010。

## 演示与真实资产

- 演示：12份合成办事文档、100道demo题（40/30/20/10）、9套候选配置。Hash向量、抽取式答案、规则Judge均明确标为demo。
- 真实语料v2：`data/corpus_v2/`中的23份FastAPI官方教程，固定500/重叠80的基线共714块，详情见`docs/数据来源清单.md`。旧v1保留历史复现，运行使用document_ids明确隔离。
- `data/eval_set_ai_verified.json`：100题来源约束的AI辅助核验题集，40事实/30推理/20多跳/10拒答；人工审核0题。`docs/AI题集核验记录.json`记录100题坐标检查与全文泄漏检查，`docs/人工标注复核底稿.csv`保留空白人工记录栏。
- `data/eval_candidates.json`：100题待审核底稿。规则提取可能不自然或不符合推理/多跳定义，**每题须人工重写问题、提炼答案要点、检查题型和全部来源**。没有任何伪造审核人/时间。
- 实际题集以数据库/界面为准；用题集导出接口取得正式`eval_set.json`与真实审核记录。草稿文件不是验收题集。

重新采集官方语料：`python scripts/collect_sources.py`。已存在原文快照会复用，不覆盖文档版本和人工题目修改。

## 云端服务配置

生成默认`deepseek-flash`；Judge默认`deepseek-v4-pro`，依据2026-10-14查询的[DeepSeek官方文档](https://api-docs.deepseek.com/)。模型与端点可改；任务保存版本快照。DeepSeek使用OpenAI-compatible Chat Completions，默认关闭思考模式以保证有限输出预算。

在本地`.env`填写`GENERATION_API_KEY`，Judge Key可留空复用同一凭据。Embedding单独填写`EMBEDDING_API_KEY/BASE_URL/MODEL`。示例给出百炼兼容接口参数，端点和地区以账号实际可用服务为准；每批最多10条，参考[百炼Embedding API](https://www.alibabacloud.com/help/en/model-studio/text-embedding-synchronous-api)。

Rerank支持百炼原生`/api/v1/services/rerank/text-rerank/text-rerank`（model/input/parameters请求、output.results响应）及model/query/documents/top_n兼容接口。百炼qwen3-rerank已真实验证。在`.env`填写`RERANK_URL/API_KEY/MODEL`；密钥属于百炼账号，不使用DeepSeek Key。

价格单位为**每百万Token**，币种由`CURRENCY`指定。全局价格适用于默认生成模型；其他模型需要在配置版本填入输入/输出单价，否则成本显示N/A。只计算成功生成和Judge的对话成本；Embedding、Rerank和失败尝试的计费不能忽略，应结合调用账本和厂商账单结算。

## 跑批命令

```powershell
python -m app.cli run --dataset dataset-demo --mode demo --concurrency 3
python -m app.cli status RUN_ID
python -m app.cli pause RUN_ID
python -m app.cli resume RUN_ID
python -m app.cli wait RUN_ID
python scripts/export_reports.py RUN_ID
```

`run`默认选C01/C02/C03/C04/C06/C07六套。正式题集人工审核完成后，把`--dataset`改为实际ID、`--mode`改为cloud。首次正式试跑请复制10题到新题集；配置了额度与速率限制后再跑全量。

默认并发3、全Worker每分钟30次API请求，429/暂时故障指数退避+抖动。当前部署保持**一个Worker**以实现进程内共享限额；多Worker虽有任务抢占保护，但不能共享该限流器，需要另加分布式限流。

## 题目格式

```json
{
  "id": "Q-001", "question": "这里填写人工编写的问题", "type": "fact",
  "gold_answer": "人工核验的标准答案要点", "gold_doc": ["fastapi-body"],
  "gold_chunk_id": [],
  "evidence": [{"doc_id": "fastapi-body", "quote": "从对应原文复制的证据文本"}],
  "difficulty": "easy", "status": "draft", "annotator": null, "reviewed_at": null,
  "annotation_note": "标注说明"
}
```

`quote`必须真实存在，保存时补齐规范化原文坐标和固定500/80基线块ID。多跳题使用多条`evidence`；拒答题`evidence/gold_doc/gold_chunk_id`为空数组。四题型值为`fact/reasoning/multihop/refusal`；难度为`easy/medium/hard`。

标为`reviewed`时须有真实`annotator`及`reviewed_at`。CSV列与JSON字段相同，三个数组字段用JSON字符串，标准CSV引号转义。批量导入完整校验后单次事务写入；错误时不部分导入。

## 目录结构

```text
app/          API、契约、数据库、RAG、指标、云服务、Worker、CLI、演示初始化
frontend/     Vue3 + Vite + ECharts
data/         官方原文快照、来源清单、demo题、待审核底稿、九套YAML
tests/        独立临时数据库上的指标/接口/恢复测试
scripts/      来源采集、报告导出、Windows启动/停止
docs/         架构、接口、部署、指标、题集、验收与讲解
reports/      运行汇总与有限样本，完整原始结果保存在数据库
runtime/      本地数据库、日志（不提交）
```

验证：`python -m pytest -q`；`npm --prefix frontend run build`。MySQL部署见`docs/部署说明.md`，验收完成情况见`docs/验收状态.md`。版本控制使用main/dev/feature分支与Conventional Commits；独立开发不能虚构他人PR评审。
