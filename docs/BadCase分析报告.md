# Bad Case分析报告：证据核验版

运行：`run-54107b88329d40c8`（700条真实云端结果，历史评测等级仍是`ai_preliminary`）。本报告以原始题目、gold证据、候选池、最终上下文、模型回答及Judge记录交叉核验；每条样例完整快照见`docs/BadCase证据核验.json`。

标签为多标签归因。除知识库缺失外，下面前五类来自真实云端失败结果；知识库缺失在700条正式结果中观测为0，因此仅附两条明确的受控反事实案例，不计入真实指标或正式观察结论。受控答案值是测试注入值，不是真实信息。

## 后续Judge裁决对失败总数的影响

本报告下方10条代表性真实案例与标签分布按原始Judge运行记录导出。之后另对5条原回答为拒答、Judge理由却判断其答对的分歧做了AI证据裁决，均判为错误拒答。当前平台的AI裁决口径Bad Case总数为253/700；原始Judge口径仍为248/700。裁决没有增加模型输出或云端任务，也没有把AI意见伪装为真人复评分数。五条逐项证据见`Judge复核裁决报告.md`。

## 真实跑批标签分布

|标签|失败结果数|说明|
|---|---:|---|
|分块问题|3|真实失败结果，多标签统计|
|召回失败|175|真实失败结果，多标签统计|
|排序问题|109|真实失败结果，多标签统计|
|生成幻觉|7|真实失败结果，多标签统计|
|提示词问题|44|真实失败结果，多标签统计|
|知识库缺失|0|正式结果未观测到；仅列受控验证|

## 真实云端案例

### 分块问题

改进建议：检查证据句是否被块边界截断；按句子边界调整块长与重叠，并对长证据保留可追溯坐标。

#### AI-024 / cloud-v2-05（item `item-86a9ade8e5e4475b`）

- 问题：UploadFile的spooled文件存储有什么特点？
- 标准答案：小文件先放内存，超过大小限制后存储到磁盘。
- 标准证据：`official-v2-request-files:3343-3476`：It uses a "spooled" file: A file stored in memory up to a maximum size limit, and after passing this limit it will be stored on disk.
- 候选池证据块：official-v2-request-files:04ebb283d7:2940-3440, official-v2-request-files:04ebb283d7:7560-8060, official-v2-request-files:04ebb283d7:3780-4280, official-v2-request-files:04ebb283d7:840-1340, official-v2-request-files:04ebb283d7:7140-7640, official-v2-request-files:04ebb283d7:10920-11420, official-v2-request-files:04ebb283d7:420-920, official-v2-request-files:04ebb283d7:9660-10160, official-v2-request-files:04ebb283d7:2100-2600, official-v2-request-files:04ebb283d7:3360-3860, official-v2-request-files:04ebb283d7:4200-4700, official-v2-request-files:04ebb283d7:1260-1760, official-v2-request-files:04ebb283d7:4620-5120, official-v2-request-files:04ebb283d7:2520-3020, official-v2-request-files:04ebb283d7:7980-8480
- 实际送入生成的上下文块：official-v2-request-files:04ebb283d7:2940-3440, official-v2-request-files:04ebb283d7:7560-8060, official-v2-request-files:04ebb283d7:3780-4280
- 模型原答：UploadFile 使用 “spooled” 文件：文件先存储在内存中，直到达到最大大小限制，超过后（证据在此处截断，未说明后续行为）[chunk_id:official-v2-request-files:04ebb283d7:2940-3440]。

其 `file` 属性是一个 `SpooledTemporaryFile`（file-like 对象），即实际的 Python 文件对象，可直接传给其他期望 file-like 对象的函数或库[chunk_id:official-v2-request-files:04ebb283d7:3780-4280]。

关于超过大小限制后的具体处理方式，知识库依据不足，无法回答。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：标准证据跨越当前最终上下文块边界，当前上下文仅覆盖部分原文；答案承认关键细节未覆盖。保留召回失败为并行问题。

#### AI-078 / cloud-v2-05（item `item-882df71a71854ab5`）

- 问题：接口响应模型会过滤内部字段，开发者以为返回空字典就能满足204。沿着“输出模型→HTTP状态语义”的链条，这个判断为什么不充分？
- 标准答案：响应模型过滤仍是在组织响应数据；204要求根本没有响应体，空JSON对象也不是无body。
- 标准证据：`official-v2-response-status-code:1473-1882`：200 - 299 are for "Successful" responses. These are the ones you would use the most. 200 is the default status code, which means everything was "OK". Another example would be 201 , "Created". It is commonly used after creating a new record in the database. A special case is 204 , "No Content".  This response is used when there is no content to return to the client, and so the response must not have a body.；`official-v2-response-model:1466-1621`：It will limit and filter the output data to what is defined in the return type. This is particularly important for security , we'll see more of that below.
- 候选池证据块：official-v2-response-status-code:3592b8e56a:1680-2180, official-v2-handling-errors:0d3e0d1db1:420-920, official-v2-response-status-code:3592b8e56a:420-920, official-v2-response-model:0f3c988f4c:8400-8900, official-v2-response-status-code:3592b8e56a:1260-1760, official-v2-response-model:0f3c988f4c:840-1340, official-v2-response-model:0f3c988f4c:20160-20439, official-v2-query-params:d6085563d4:2520-3020, official-v2-handling-errors:0d3e0d1db1:0-500, official-v2-handling-errors:0d3e0d1db1:2100-2600, official-v2-response-model:0f3c988f4c:1260-1760, official-v2-first-steps:299dfe78a0:8400-8900, official-v2-response-model:0f3c988f4c:7980-8480, official-v2-path-params:155981889f:1260-1760, official-v2-response-model:0f3c988f4c:5460-5960
- 实际送入生成的上下文块：official-v2-response-status-code:3592b8e56a:1680-2180, official-v2-handling-errors:0d3e0d1db1:420-920, official-v2-response-status-code:3592b8e56a:420-920
- 模型原答：知识库依据不足，无法回答。现有证据只说明 204 响应“必须没有 body”，以及 `status_code` 是装饰器参数、会写入响应和 OpenAPI schema；没有提供“接口响应模型会过滤内部字段”或“返回空字典”与 204 之间关系的规则，因此无法沿“输出模型→HTTP状态语义”链条推导该判断为何不充分。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：多跳标准证据涉及响应模型与204状态语义；最终上下文证据覆盖不完整，模型因此以证据不足拒答。分块与召回均是可观察的并行问题。

### 召回失败

改进建议：先检查标准证据是否进入候选池；结合中文查询改写、混合检索和Top-K做单变量回归。

#### AI-002 / cloud-v2-01（item `item-7544f50e1f284fae`）

- 问题：路径函数里，未出现在路径模板中的普通参数默认被当成什么？
- 标准答案：普通参数默认解释为查询参数。
- 标准证据：`official-v2-query-params:18-160`：When you declare other function parameters that are not part of the path parameters, they are automatically interpreted as "query" parameters.
- 候选池证据块：official-v2-path-params:155981889f:4200-4700, official-v2-path-params-numeric-validations:ea84a4f809:9660-10160, official-v2-path-params:155981889f:5880-6380, official-v2-body-fields:70f3fc18e3:3360-3860, official-v2-dependencies:c60006b30f:5040-5540, official-v2-path-params:155981889f:0-500, official-v2-path-params-numeric-validations:ea84a4f809:2940-3440, official-v2-path-params:155981889f:2940-3440, official-v2-path-params-numeric-validations:ea84a4f809:4620-5120, official-v2-path-params-numeric-validations:ea84a4f809:2520-3020, official-v2-path-params-numeric-validations:ea84a4f809:2100-2600, official-v2-query-params:d6085563d4:3360-3860, official-v2-path-params:155981889f:8820-9320, official-v2-path-params:155981889f:9240-9740, official-v2-path-params-numeric-validations:ea84a4f809:3780-4280
- 实际送入生成的上下文块：official-v2-path-params:155981889f:4200-4700, official-v2-path-params-numeric-validations:ea84a4f809:9660-10160, official-v2-path-params:155981889f:5880-6380
- 模型原答：知识库依据不足，无法回答。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：知识库包含标准证据，但正确证据既未进入候选池也未进入最终上下文，答案错误拒答；属于召回失败。

#### AI-015 / cloud-v2-01（item `item-fcd9bfef69bf4699`）

- 问题：FastAPI的BackgroundTasks通常在什么时候执行？
- 标准答案：在返回响应之后执行。
- 标准证据：`official-v2-background-tasks:18-87`：You can define background tasks to be run after returning a response.
- 候选池证据块：official-v2-background-tasks:f795592ff7:1260-1760, official-v2-background-tasks:f795592ff7:2520-3020, official-v2-background-tasks:f795592ff7:6720-7039, official-v2-background-tasks:f795592ff7:3780-4280, official-v2-background-tasks:f795592ff7:2940-3440, official-v2-background-tasks:f795592ff7:840-1340, official-v2-background-tasks:f795592ff7:1680-2180, official-v2-background-tasks:f795592ff7:5880-6380, official-v2-background-tasks:f795592ff7:2100-2600, official-v2-background-tasks:f795592ff7:5460-5960, official-v2-background-tasks:f795592ff7:3360-3860, official-v2-background-tasks:f795592ff7:5040-5540, official-v2-background-tasks:f795592ff7:4200-4700, official-v2-background-tasks:f795592ff7:6300-6800, official-v2-background-tasks:f795592ff7:420-920
- 实际送入生成的上下文块：official-v2-background-tasks:f795592ff7:1260-1760, official-v2-background-tasks:f795592ff7:2520-3020, official-v2-background-tasks:f795592ff7:6720-7039
- 模型原答：知识库依据不足，无法回答。

现有证据只说明如何创建和使用 `BackgroundTasks`（如通过 `.add_task()` 添加任务、任务函数可以是 `async def` 或普通 `def`），但没有说明这些任务通常在什么时候执行。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：官方文档包含后台任务执行时机的标准句，但本配置候选与最终上下文未覆盖该句；答案错误拒答。

### 排序问题

改进建议：扩大候选池后比较最终Top-K；使用重排时记录排序前后名次，确认正确证据没有被截断。

#### AI-008 / cloud-v2-01（item `item-15436ffeda424e5b`）

- 问题：可以在同一个路径操作中同时接收路径参数和请求体吗？
- 标准答案：可以同时声明路径参数与请求体。
- 标准证据：`official-v2-body:5130-5196`：You can declare path parameters and request body at the same time.
- 候选池证据块：official-v2-request-forms:c58d5b393f:2520-2876, official-v2-body-multiple-params:ecd0b3ed65:8400-8900, official-v2-dependencies:c60006b30f:5040-5540, official-v2-request-files:04ebb283d7:5880-6380, official-v2-body:fe95b080f7:7140-7263, official-v2-body-multiple-params:ecd0b3ed65:2940-3440, official-v2-body-multiple-params:ecd0b3ed65:8820-8979, official-v2-body-multiple-params:ecd0b3ed65:0-500, official-v2-body:fe95b080f7:5040-5540, official-v2-body-multiple-params:ecd0b3ed65:1680-2180, official-v2-path-params:155981889f:3780-4280, official-v2-body-fields:70f3fc18e3:3360-3860, official-v2-body-multiple-params:ecd0b3ed65:1260-1760, official-v2-dependencies:c60006b30f:4620-5120, official-v2-body:fe95b080f7:6300-6800
- 实际送入生成的上下文块：official-v2-request-forms:c58d5b393f:2520-2876, official-v2-body-multiple-params:ecd0b3ed65:8400-8900, official-v2-dependencies:c60006b30f:5040-5540
- 模型原答：知识库依据不足，无法回答。现有证据只涉及表单参数与请求体字段不能同时声明、多个请求体参数、以及依赖项用法，未直接说明“同一路径操作中同时接收路径参数和请求体”的规则。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：标准证据在候选池中，但不在最终传给生成的Top-K上下文；属于候选排序/截断，不能标为知识库缺失。

#### AI-009 / cloud-v2-01（item `item-a31d1dcd656442f4`）

- 问题：Pydantic模型内部用哪个工具设置字段校验和描述信息？
- 标准答案：使用Pydantic的Field。
- 标准证据：`official-v2-body-fields:15-236`：The same way you can declare additional validation and metadata in path operation function parameters with Query , Path and Body , you can declare validation and metadata inside of Pydantic models using Pydantic's Field .
- 候选池证据块：official-v2-body:fe95b080f7:3780-4280, official-v2-response-model:0f3c988f4c:1680-2180, official-v2-response-model:0f3c988f4c:4200-4700, official-v2-body-fields:70f3fc18e3:3780-4280, official-v2-response-model:0f3c988f4c:16380-16880, official-v2-sql-databases:96a44a193c:40320-40820, official-v2-body:fe95b080f7:4200-4700, official-v2-body-nested-models:c72a0d320b:2520-3020, official-v2-query-params-str-validations:5e64d09084:22260-22760, official-v2-body-fields:70f3fc18e3:2100-2600, official-v2-body-fields:70f3fc18e3:840-1340, official-v2-body-nested-models:c72a0d320b:840-1340, official-v2-body-fields:70f3fc18e3:0-500, official-v2-body:fe95b080f7:4620-5120, official-v2-query-params-str-validations:5e64d09084:21420-21920
- 实际送入生成的上下文块：official-v2-body:fe95b080f7:3780-4280, official-v2-response-model:0f3c988f4c:1680-2180, official-v2-response-model:0f3c988f4c:4200-4700
- 模型原答：知识库依据不足，无法回答。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：Field标准证据在候选池中，但未进入最终Top-K上下文；属于排序/截断问题。

### 生成幻觉

改进建议：对照回答中的每项事实与证据；要求逐项引用可支持的片段，并对矛盾答案做回归测试。

#### AI-007 / cloud-v2-01（item `item-6926eaa8d3e84b7e`）

- 问题：路径函数中，int或str等普通标量参数通常从哪里读取？
- 标准答案：通常解释为查询参数，而不是自动作为请求体。
- 标准证据：`official-v2-body:6504-6625`：If the parameter is of a singular type (like int , float , str , bool , etc) it will be interpreted as a query parameter.
- 候选池证据块：official-v2-path-params:155981889f:5880-6380, official-v2-path-params:155981889f:9240-9740, official-v2-path-params:155981889f:0-500, official-v2-dependencies:c60006b30f:5040-5540, official-v2-path-params:155981889f:4200-4700, official-v2-path-params:155981889f:2940-3440, official-v2-path-params:155981889f:8820-9320, official-v2-dependencies:c60006b30f:5460-5960, official-v2-query-params:d6085563d4:0-500, official-v2-path-params-numeric-validations:ea84a4f809:5040-5540, official-v2-dependencies:c60006b30f:2100-2600, official-v2-query-params:d6085563d4:3360-3860, official-v2-path-params-numeric-validations:ea84a4f809:9660-10160, official-v2-query-params:d6085563d4:5040-5451, official-v2-path-params-numeric-validations:ea84a4f809:10080-10580
- 实际送入生成的上下文块：official-v2-path-params:155981889f:5880-6380, official-v2-path-params:155981889f:9240-9740, official-v2-path-params:155981889f:0-500
- 模型原答：路径函数中的普通标量参数（如 int、str）通常从路径参数中读取，即通过 URL 路径中的变量传入函数。[chunk_id: official-v2-path-params:155981889f:0-500]
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：答案将普通标量参数错误说成路径参数，与gold及官方规则相反；同时引用了不支持该结论的片段，兼有证据召回缺失。

#### AI-037 / cloud-v2-03（item `item-816359971e8d43b3`）

- 问题：单个模型请求体希望外面增加item这一层键，应使用什么设置？
- 标准答案：使用Body的embed参数，即Body(embed=True)。
- 标准证据：`official-v2-body-multiple-params:7169-7355`：But if you want it to expect a JSON with a key item and inside of it the model contents, as it does when you declare extra body parameters, you can use the special Body parameter embed :
- 候选池证据块：official-v2-body:fe95b080f7:2940-3440, official-v2-body:fe95b080f7:1680-2180, official-v2-body-multiple-params:ecd0b3ed65:2520-3020, official-v2-body-multiple-params:ecd0b3ed65:2940-3440, official-v2-body:fe95b080f7:7140-7263, official-v2-body-nested-models:c72a0d320b:6720-7220, official-v2-query-params:d6085563d4:3360-3860, official-v2-response-model:0f3c988f4c:20160-20439, official-v2-body-nested-models:c72a0d320b:3780-4280, official-v2-body-multiple-params:ecd0b3ed65:1260-1760, official-v2-query-params:d6085563d4:4200-4700, official-v2-query-param-models:965a802b3a:2940-3440, official-v2-body-nested-models:c72a0d320b:5880-6380, official-v2-body-nested-models:c72a0d320b:2100-2600, official-v2-response-model:0f3c988f4c:15960-16460
- 实际送入生成的上下文块：official-v2-body:fe95b080f7:2940-3440, official-v2-body:fe95b080f7:1680-2180, official-v2-body-multiple-params:ecd0b3ed65:2520-3020, official-v2-body-multiple-params:ecd0b3ed65:2940-3440, official-v2-body:fe95b080f7:7140-7263
- 模型原答：根据证据，当函数中有多个 Pydantic 模型参数时，FastAPI 会使用参数名作为请求体中的键，因此模型会被放在 `item` 这一层键下[chunk_id:official-v2-body-multiple-params:ecd0b3ed65:2520-3020][chunk_id:official-v2-body-multiple-params:ecd0b3ed65:2940-3440]。

所以，若希望单个模型请求体外层增加 `item` 键，应让该模型作为函数参数之一（例如与其他模型参数并列），FastAPI 会自动以参数名 `item` 作为外层键[chunk_id:official-v2-body-multiple-params:ecd0b3ed65:2520-3020][chunk_id:official-v2-body-multiple-params:ecd0b3ed65:2940-3440]。
- 运行指标：hit=0.0，MRR=0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：答案把多个请求体模型自动命名键的规则误套到单模型embed场景；正确Body(embed=True)证据未进入上下文，兼有生成错误。

### 提示词问题

改进建议：检查证据充分时是否仍被过度拒答；调整拒答判定条件，并用可回答/不可回答成对题验证。

#### AI-017 / cloud-v2-04（item `item-9505a935ea254739`）

- 问题：后台重计算需要跨进程或跨服务器运行时，教程建议考虑什么工具？
- 标准答案：考虑Celery等更大的任务工具和消息队列。
- 标准证据：`official-v2-background-tasks:6265-6505`：If you need to perform heavy background computation and you don't necessarily need it to be run by the same process (for example, you don't need to share memory, variables, etc), you might benefit from using other bigger tools like Celery .
- 候选池证据块：official-v2-background-tasks:d4d2e1efe4:6427-6923, official-v2-background-tasks:d4d2e1efe4:6099-6507, official-v2-background-tasks:d4d2e1efe4:221-537, official-v2-background-tasks:d4d2e1efe4:0-301, official-v2-testing:643f2f04f9:11091-11259, official-v2-background-tasks:d4d2e1efe4:4549-4990, official-v2-background-tasks:d4d2e1efe4:3737-4212, official-v2-dependencies:bcd243d5bf:10301-10791, official-v2-background-tasks:d4d2e1efe4:457-943, official-v2-background-tasks:d4d2e1efe4:863-1336, official-v2-background-tasks:d4d2e1efe4:6843-7039, official-v2-extra-data-types:58ba4b55f6:4690-5186, official-v2-background-tasks:d4d2e1efe4:1256-1726, official-v2-first-steps:9983d243d8:2572-3011, official-v2-background-tasks:d4d2e1efe4:5522-5807
- 实际送入生成的上下文块：official-v2-background-tasks:d4d2e1efe4:6427-6923, official-v2-background-tasks:d4d2e1efe4:6099-6507, official-v2-background-tasks:d4d2e1efe4:221-537
- 模型原答：知识库依据不足，无法回答。
- 运行指标：hit=1.0，MRR=0.5，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：最终上下文已覆盖Celery标准证据，答案仍直接拒答。记录为生成约束/拒答边界问题；仅凭单次结果不能证明Prompt是唯一根因。

#### AI-048 / cloud-v2-01（item `item-8381e96c6cdc430d`）

- 问题：发送短通知与需要多服务器协作的重计算，是否都应只用进程内BackgroundTasks？
- 标准答案：短通知可以响应后运行；需要跨进程或多服务器重计算应考虑Celery等队列工具。
- 标准证据：`official-v2-background-tasks:18-87`：You can define background tasks to be run after returning a response.；`official-v2-background-tasks:6265-6505`：If you need to perform heavy background computation and you don't necessarily need it to be run by the same process (for example, you don't need to share memory, variables, etc), you might benefit from using other bigger tools like Celery .
- 候选池证据块：official-v2-background-tasks:f795592ff7:6300-6800, official-v2-background-tasks:f795592ff7:1260-1760, official-v2-background-tasks:f795592ff7:2940-3440, official-v2-background-tasks:f795592ff7:2520-3020, official-v2-background-tasks:f795592ff7:1680-2180, official-v2-background-tasks:f795592ff7:3780-4280, official-v2-background-tasks:f795592ff7:2100-2600, official-v2-background-tasks:f795592ff7:4620-5120, official-v2-background-tasks:f795592ff7:5460-5960, official-v2-background-tasks:f795592ff7:6720-7039, official-v2-background-tasks:f795592ff7:420-920, official-v2-background-tasks:f795592ff7:5040-5540, official-v2-background-tasks:f795592ff7:5880-6380, official-v2-background-tasks:f795592ff7:840-1340, official-v2-background-tasks:f795592ff7:3360-3860
- 实际送入生成的上下文块：official-v2-background-tasks:f795592ff7:6300-6800, official-v2-background-tasks:f795592ff7:1260-1760, official-v2-background-tasks:f795592ff7:2940-3440
- 模型原答：知识库依据不足，无法回答。

现有证据只说明：`BackgroundTasks` 适合在 FastAPI 应用内运行后台任务、可访问同一应用的变量和对象；而需要多进程、尤其是多服务器运行的重计算，可考虑 Celery 等更重的工具（需消息/任务队列如 RabbitMQ 或 Redis）[chunk_id: official-v2-background-tasks:f795592ff7:6300-6800]。证据未对“发送短通知”是否应只用 `BackgroundTasks` 给出明确结论，也未说明两者是否“都应只用”进程内方案，因此无法据此判断。
- 运行指标：hit=1.0，MRR=1.0，task_success=0.0。
- 归因证据：Codex证据核验（依据冻结云端明细）：上下文含短任务与Celery重任务证据，模型仍拒答；提示词约束/拒答边界为待验证根因，不能仅凭一次输出定因。

## 知识库缺失：受控反事实验证，不是云端失败案例

这两条使用真实题集中的范围外问题；标准证据和gold来源为空，符合知识库缺失条件。测试答案由脚本人工注入，目的是验证标签边界和处置流程，不代表模型曾经这样回答。

### KB-CONTROL-01 / AI-091

- 问题：飞的公司生产FastAPI服务今天的部署版本号是什么？
- 证据状态：gold_doc和gold_chunk_id为空；该信息不在已索引语料中。
- 注入的错误输出：受控错误输出：生产部署版本是 v9.9.9。
- 预期归因：知识库缺失导致无证据作答；测试输出是人工注入的假值，不是真实模型回答。
- 改进建议：设置来源范围与拒答边界；若该信息确需回答，应先取得授权并补充可审计的内部资料。

### KB-CONTROL-02 / AI-092

- 问题：我们学校内部FastAPI选课系统下周具体哪一天停机维护？
- 证据状态：gold_doc和gold_chunk_id为空；该信息不在已索引语料中。
- 注入的错误输出：受控错误输出：系统将于下周三停机维护。
- 预期归因：知识库缺失导致无证据作答；答案中的日期是人工注入的假值，不是真实系统信息。
- 改进建议：只从经过授权的运维公告中回答；检索不到时明确拒答，并记录需要补充的资料来源。

## 证据限制

1. 标签说明失败链路中的可观察环节，不自动证明单一根因；提示词问题尤其需要固定模型、上下文和问题后做Prompt A/B才能作因果结论。
2. 同一题的不同配置结果不是独立题目样本。报告保留配置和item ID，避免把跨配置重复误报为多个独立用户问题。
3. Judge理由可能与生成原文不一致；出现这种情况时以保存的原始答案和证据为准，Judge结论单列为待校准信号。
4. 本报告没有把受控的知识库缺失案例计入真实标签频数，也没有把无依据的真实失败归因为知识库缺失。
