# Bad Case分析报告

运行：run-2227d85ffbc64bce；模式：cloud。自动建议标签须人工确认。

## 标签分布

{"分块问题": 0, "召回失败": 9, "排序问题": 2, "生成幻觉": 0, "提示词问题": 0, "知识库缺失": 0}

## 分块问题

改进建议：调整块大小或重叠，检查标准证据是否跨块；保持证据坐标。

此次运行未观察到已归入本类的案例；正式验收案例待人工确认，未补造结果。

## 召回失败

改进建议：对照向量分数与BM25命中，尝试混合检索、阈值或Top-K。

- `AI-002` / `cloud-v2-01`：路径函数里，未出现在路径模板中的普通参数默认被当成什么？；任务成功：0.0；Judge理由：The answer refuses to answer, claiming insufficient knowledge base evidence. However, the gold evidence clearly states that non-path parameters are automatically interpreted as query parameters, so the refusal is incorrect.
- `AI-002` / `cloud-v2-05`：路径函数里，未出现在路径模板中的普通参数默认被当成什么？；任务成功：0.0；Judge理由：标准答案明确指出未出现在路径模板中的普通参数默认解释为查询参数，且标准证据支持这一点。被评答案以知识库依据不足为由拒绝回答，但检索到的证据中虽未直接包含该信息，但标准证据明确存在，因此该拒答是错误的。
## 排序问题

改进建议：检查候选池与最终上下文，单变量测试Rerank。

- `AI-041` / `cloud-v2-01`：函数参数limit不在路径模板里且默认20，客户端省略limit时，应从哪里取值、是否报缺失错误？；任务成功：0.0；Judge理由：The answer refuses to answer, claiming insufficient evidence, but the provided gold evidence directly addresses the question: non-path parameters are query parameters, and default values make them not required. Therefore the refusal is incorrect.
- `AI-041` / `cloud-v2-05`：函数参数limit不在路径模板里且默认20，客户端省略limit时，应从哪里取值、是否报缺失错误？；任务成功：0.0；Judge理由：答案以知识库依据不足为由拒绝回答，但标准答案明确说明limit是查询参数且有默认值20，客户端省略时使用默认值，不报缺失错误。检索到的证据中已包含相关规则（如默认值使用示例），因此拒答不正确。
## 生成幻觉

改进建议：核验标准证据、收紧来源约束；不足时拒答，再做回归。

此次运行未观察到已归入本类的案例；正式验收案例待人工确认，未补造结果。

## 提示词问题

改进建议：根据具体失败调整Prompt约束，并固化新版本。

此次运行未观察到已归入本类的案例；正式验收案例待人工确认，未补造结果。

## 知识库缺失

改进建议：补充可溯源材料；若业务不可回答，应设计正确拒答。

此次运行未观察到已归入本类的案例；正式验收案例待人工确认，未补造结果。
