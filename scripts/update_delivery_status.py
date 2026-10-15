"""依据当前真实完成记录刷新交付入口，不改变人工或协作状态。"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
record=json.loads((ROOT/'docs/真实云运行完成记录.json').read_text(encoding='utf-8'))
assert record['state']=='completed' and record['succeeded']==700
text='''# 本机验证记录（2026-10-15）

- Python3.13 / Node24 / SQLite，pip check通过。
- 23项pytest通过；存在一条上游TestClient/httpx弃用提示。测试使用独立临时数据库，未清空用户结果。
- Vue3生产构建通过，ECharts分包，最大包约388KB。
- 本轮浏览器无JS异常；云预评测标识显示；390px平台与既有报告无横向溢出。独立报告旧构建的来源查看及Evidence flow功能通过；最新报告构建被插件卸载阻断，不能视为最新已验证版本。
- v2真实来源23份、固定500/80共714块；100题AI核验40/30/20/10，来源哈希与证据坐标校验通过，去空白casefold题干全文复制匹配0。人工审核0题，未冒填。
- 两轮10题×2配置真实试跑各20/20成功；全量七配置×100题700/700成功。
- 全量700条生成均deepseek-flash，Judge均deepseek-v4-pro；每项成功生成HTTP调用恰好1次，Judge失败续跑没有重复已成功生成。原始结果及失败尝试均持久化，详见真实续跑与调用核验.json。
- 余额不足自动暂停队列的测试通过；该修复前的全量曾出现重复402失败请求，账本如实保存，未把失败尝试计成有效问答。
- Judge输出的合法块ID严格校验；最终680/19/1条分别用原协议、合法ID列表、引用格式反馈协议；评分提示词/阈值/模型不变，协议差异在报告披露。
- 固定种子42抽20题，七配置140条独立人工评分底稿已导出；评分栏为空，一致率N/A。
- 六类各2条受控故障注入验证通过，单独保存，不计入700条正常质量结果。真实Bad Case中知识库缺失0例，分块2例为同一题两配置，缺口保留。
- Windows PowerShell5启动/停止脚本UTF-8 BOM实测；平台仍可访问且历史结果保留。
- MySQL服务运行但有效登录凭据未配置，曾认证1045；DDL、Compose和空库迁移工具已准备，MySQL实测未通过。
- Git有本地main/dev/feature规范提交，无远程PR/真实他人评审。凭据精确扫描0匹配，.env/runtime/依赖排除。
'''
(ROOT/'docs/验证记录.md').write_text(text,encoding='utf-8')
path=ROOT/'docs/交付入口.md';text=path.read_text(encoding='utf-8')
text=text.replace('- 真实结果分析报告：http://127.0.0.1:8020。页面支持查看指标来源、原始汇总和证据说明。',
'''- 最新真实结果：平台结果看板选择“100题×7配置 · 真实云AI预评测”；docs/配置对比报告.md有完整七配置结论。
- 独立交互报告源码位于相邻rag-eval-report目录，已填入700条汇总；Data插件在工作中卸载，最新构建未完成。8020旧预览仅包含54条，已停止，避免误认为最终结果。恢复Data插件标准构建后才可交付此独立预览。''')
path.write_text(text,encoding='utf-8')
report=ROOT.parent/'rag-eval-report/src/data.json'
if report.exists():
    data=json.loads(report.read_text(encoding='utf-8'));data['buildStatus']='paused'
    report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Delivery status refreshed from verified 700/700; external/manual gaps preserved')
