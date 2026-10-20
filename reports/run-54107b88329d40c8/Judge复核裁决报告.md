# Judge分歧复核裁决报告

复核已完成：5条均判为错误拒答。复核者是Codex（AI），不是新的人类评审；原始Judge、人工评分和历史任务快照保持独立可追溯。裁决层只更正这5条结果在当前对比视图中的质量统计，没有重新调用模型。

|题目 / 配置|原Judge / 原人工分数|AI裁决准确性 / 完整性|拒答 / 任务通过|
|---|---|---|---|
|AI-057 / R01|5/5；5/5|1/1|拒答；不通过|
|AI-057 / R06|5/5；5/5|1/1|拒答；不通过|
|AI-067 / R01|5/5；5/5|1/1|拒答；不通过|
|AI-067 / R05|5/5；5/5|1/1|拒答；不通过|
|AI-078 / R04|5/5；5/5|1/1|拒答；不通过|

准确性和完整性均为1分：回答没有包含题目要求的任何要点；错误拒答不因为措辞谨慎而得到通过分。没有提出事实主张，因此unsupported=false、factually_incorrect=false；拒答本身作为任务失败处理。

## AI-057 / cloud-v2-01

题目：给删除接口声明status_code=204之后，还返回一个JSON说明对象是否合适？

原始模型回答：知识库依据不足，无法回答。

标准答案：不合适，204表示无内容，响应不应有body。

- 来源`official-v2-response-status-code`：The same way you can specify a response model, you can also declare the HTTP status code used for the response with the parameter status_code in any of the path operations :
- 来源`official-v2-response-status-code`：200 - 299 are for "Successful" responses. These are the ones you would use the most. 200 is the default status code, which means everything was "OK". Another example would be 201 , "Created". It is commonly used after creating a new record in the database. A special case is 204 , "No Content".  This response is used when there is no content to return to the client, and so the response must not have a body.

原Judge理由：标准答案明确指出204表示无内容，响应不应有body，因此返回JSON不合适。标准证据中明确说明204响应必须没有body。被评答案与标准答案一致，且完全基于标准证据。

裁决：原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。

来源校验SHA256：`1b70ea66bcab17590c4169abb09b1444d01ce56a773572ca17c14f7d29c76eaa`。原评分与新裁决完整记录见`Judge复核裁决.json`。

## AI-057 / cloud-v2-06

题目：给删除接口声明status_code=204之后，还返回一个JSON说明对象是否合适？

原始模型回答：知识库依据不足，无法回答。

标准答案：不合适，204表示无内容，响应不应有body。

- 来源`official-v2-response-status-code`：The same way you can specify a response model, you can also declare the HTTP status code used for the response with the parameter status_code in any of the path operations :
- 来源`official-v2-response-status-code`：200 - 299 are for "Successful" responses. These are the ones you would use the most. 200 is the default status code, which means everything was "OK". Another example would be 201 , "Created". It is commonly used after creating a new record in the database. A special case is 204 , "No Content".  This response is used when there is no content to return to the client, and so the response must not have a body.

原Judge理由：标准答案明确指出204表示无内容，响应不应有body，因此返回JSON不合适。标准证据支持这一点。被评答案正确回答了问题，且与标准答案一致。

裁决：原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。

来源校验SHA256：`78236e9dd429fe2291fed23b7b0ce604143eaba2a10b66378cde520ac9894dad`。原评分与新裁决完整记录见`Judge复核裁决.json`。

## AI-067 / cloud-v2-01

题目：请求字段错误与返回模型字段错误，都应描述为“客户端没传对参数”吗？

原始模型回答：知识库依据不足，无法回答。

标准答案：不能。请求错误是输入校验；返回模型错误表明服务端代码返回了无效数据。

- 来源`official-v2-response-model`：Validate the returned data. If the data is invalid (e.g. you are missing a field), it means that your app code is broken, not returning what it should, and it will return a server error instead of returning incorrect data. This way you and your clients can be certain that they will receive the data and the data shape expected.
- 来源`official-v2-body`：Validate the data. If the data is invalid, it will return a nice and clear error, indicating exactly where and what was the incorrect data.

原Judge理由：答案正确区分了请求字段错误（客户端输入校验）与返回模型字段错误（服务端代码问题），与标准答案一致，并引用了相关证据。

裁决：原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。

来源校验SHA256：`aed10c7b5bfc90a82d8f9dec030238448e257d6bc61717953dafddce8ac57903`。原评分与新裁决完整记录见`Judge复核裁决.json`。

## AI-067 / cloud-v2-05

题目：请求字段错误与返回模型字段错误，都应描述为“客户端没传对参数”吗？

原始模型回答：知识库依据不足，无法回答。

标准答案：不能。请求错误是输入校验；返回模型错误表明服务端代码返回了无效数据。

- 来源`official-v2-response-model`：Validate the returned data. If the data is invalid (e.g. you are missing a field), it means that your app code is broken, not returning what it should, and it will return a server error instead of returning incorrect data. This way you and your clients can be certain that they will receive the data and the data shape expected.
- 来源`official-v2-body`：Validate the data. If the data is invalid, it will return a nice and clear error, indicating exactly where and what was the incorrect data.

原Judge理由：答案正确区分了请求字段错误（客户端输入校验）与返回模型字段错误（服务端代码问题），与标准答案一致。

裁决：原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。

来源校验SHA256：`1513b4e37dcccd3546bdedc3b8f89a91976f323b0e9a027720f501877a478163`。原评分与新裁决完整记录见`Judge复核裁决.json`。

## AI-078 / cloud-v2-04

题目：接口响应模型会过滤内部字段，开发者以为返回空字典就能满足204。沿着“输出模型→HTTP状态语义”的链条，这个判断为什么不充分？

原始模型回答：知识库依据不足，无法回答。

标准答案：响应模型过滤仍是在组织响应数据；204要求根本没有响应体，空JSON对象也不是无body。

- 来源`official-v2-response-status-code`：200 - 299 are for "Successful" responses. These are the ones you would use the most. 200 is the default status code, which means everything was "OK". Another example would be 201 , "Created". It is commonly used after creating a new record in the database. A special case is 204 , "No Content".  This response is used when there is no content to return to the client, and so the response must not have a body.
- 来源`official-v2-response-model`：It will limit and filter the output data to what is defined in the return type. This is particularly important for security , we'll see more of that below.

原Judge理由：答案准确指出响应模型过滤仍是在组织响应数据，而204要求无响应体，空JSON对象也不是无body，与标准答案一致。

裁决：原始回答仅为“知识库依据不足，无法回答。”，没有给出标准答案所要求的事实或推理。题目有可追溯官方证据，因此属于错误拒答，准确性与完整性均为1分。Judge理由声称回答了具体内容，与保存的原答不匹配。

来源校验SHA256：`aef85f70fbb0191e89b336f5fff6301da5918e1380390c22a406cd44b892cbe1`。原评分与新裁决完整记录见`Judge复核裁决.json`。

## 对指标的影响与一致率

原Judge全量通过452/700，应用5条AI裁决后447/700；失败数由248变为253。原始人工对原Judge的准确性/完整性分数一致140/140、分类一致135/140（96.43%）保留。AI裁决不作为新增真人评分，不能用其把真人一致率写成100%。

改进：对Judge输入增加item_id与答案引用对齐；拒答和任务正确性分别判断；高分但原答为纯拒答的非拒答题列入复核队列。
