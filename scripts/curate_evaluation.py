"""Codex逐项策划的来源约束题集；AI辅助核验，不伪造人工记录。"""
import asyncio,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.prepare_real_evaluation import collect
from app.db import init_db,Session
from app.models import Document,Dataset,Question,Config
from app.schemas import Parameters
from app.service import validate_case

# 问题、标准要点、来源文档、原文定位锚点。来源必须真实存在。
FACTS=[
('FastAPI使用哪个标准描述整套API结构？','使用OpenAPI标准生成API schema。','first-steps','FastAPI generates a "schema"'),
('路径函数里，未出现在路径模板中的普通参数默认被当成什么？','普通参数默认解释为查询参数。','query-params','not part of the path parameters'),
('查询参数有默认值时，客户端是否必须传递它？','不是必传；省略时使用默认值。','query-params','When you declare a default value'),
('如何让一个查询参数成为必填项？','不声明默认值，客户端必须传递。','query-params','you can just not declare any default value'),
('FastAPI怎样声明JSON请求体的数据结构？','使用Pydantic模型声明请求体。','body','To declare a request body'),
('请求数据校验失败时，FastAPI会给客户端怎样的反馈？','返回清晰错误，指出数据何处及为什么不正确。','body','If the data is invalid'),
('路径函数中，int或str等普通标量参数通常从哪里读取？','通常解释为查询参数，而不是自动作为请求体。','body','If the parameter is of a singular type'),
('可以在同一个路径操作中同时接收路径参数和请求体吗？','可以同时声明路径参数与请求体。','body','You can declare path parameters and request body'),
('Pydantic模型内部用哪个工具设置字段校验和描述信息？','使用Pydantic的Field。','body-fields','using Pydantic\'s Field'),
('响应模型怎样处理返回对象中未在模型声明的字段？','限制并过滤输出，仅保留响应模型声明的数据。','response-model','It will limit and filter the output data'),
('同时声明返回类型和response_model时，FastAPI优先采用哪个？','优先使用response_model。','response-model','response_model will take priority'),
('服务器返回的数据不满足响应模型时，会发生什么？','视为服务端代码错误，返回服务端错误，不把无效数据作为正常响应。','response-model','it will return a server error'),
('请求内容不合法时，FastAPI内部抛出哪种校验异常？','RequestValidationError。','handling-errors','FastAPI internally raises a RequestValidationError'),
('依赖及子依赖的参数、校验和要求会进入API文档吗？','会统一纳入OpenAPI schema。','dependencies','All the request declarations, validations and requirements'),
('FastAPI的BackgroundTasks通常在什么时候执行？','在返回响应之后执行。','background-tasks','after returning a response'),
('怎样把一个函数及其参数加入BackgroundTasks？','调用background_tasks.add_task，传入函数以及需要的参数。','background-tasks','background_tasks.add_task(write_notification'),
('后台重计算需要跨进程或跨服务器运行时，教程建议考虑什么工具？','考虑Celery等更大的任务工具和消息队列。','background-tasks','If you need to perform heavy background computation'),
('set[str]形式的模型字段对重复元素有什么特点？','集合保存唯一元素，不保留重复项。','body-nested-models','a special data type for sets of unique items'),
('模型中的URL字段若希望验证HTTP URL，示例使用哪种类型？','使用Pydantic的HttpUrl替代普通str。','body-nested-models','Pydantic\'s HttpUrl instead of a str'),
('FastAPI是否支持任意深度的嵌套模型校验和文档？','支持，依靠Pydantic定义、验证和文档化深层嵌套模型。','body-nested-models','arbitrarily deeply nested models'),
('接收普通表单字段而不是JSON时，用哪个参数工具？','使用Form。','request-forms','you can use Form'),
('没有文件的普通表单通常采用什么媒体类型？','application/x-www-form-urlencoded。','request-forms','Data from forms is normally encoded'),
('表单包含文件时通常采用什么媒体类型？','multipart/form-data。','request-forms','when the form includes files'),
('UploadFile的spooled文件存储有什么特点？','小文件先放内存，超过大小限制后存储到磁盘。','request-files','It uses a "spooled" file'),
('接收上传文件前，教程要求安装哪个依赖？','安装python-multipart。','request-files','first install python-multipart'),
('Header如何把Python参数名映射到带连字符的HTTP头？','默认把参数名中的下划线转为连字符。','header-params','from underscore ( _ ) to hyphen'),
('HTTP请求头的名称是否区分大小写？','不区分大小写。','header-params','HTTP headers are case-insensitive'),
('同一个请求头名称可以在请求中出现多次吗？','可以接收重复请求头，即同名头的多个值。','header-params','It is possible to receive duplicate headers'),
('UUID在请求和响应中通常表示为什么JSON类型？','以字符串表示。','extra-data-types','Universally Unique Identifier'),
('datetime.datetime在请求和响应中如何表示？','表示为ISO 8601格式的字符串。','extra-data-types','datetime.datetime :'),
('datetime.timedelta默认在请求和响应中如何表示？','表示为总秒数的浮点数，也支持Pydantic允许的ISO 8601时差编码。','extra-data-types','datetime.timedelta :'),
('为路径参数添加校验和元数据应该使用什么工具？','使用Path，与查询参数的Query类似。','path-params-numeric-validations','validations and metadata for path parameters with Path'),
('怎样在路径操作声明中指定响应HTTP状态码？','在路径操作装饰器里设置status_code。','response-status-code','response with the parameter status_code'),
('204 No Content响应可以带响应体吗？','不能带响应体。','response-status-code','must not have a body'),
('限定路径参数只能取预先定义的值时，可以使用哪种Python类型？','使用标准Python Enum。','path-params','standard Python Enum'),
('如何为路径参数声明类型？','在路径函数参数上使用标准Python类型注解。','path-params','using standard Python type annotations'),
('单个模型请求体希望外面增加item这一层键，应使用什么设置？','使用Body的embed参数，即Body(embed=True)。','body-multiple-params','you can use the special Body parameter embed'),
('FastAPI支持在一个路径函数中声明多个请求体模型参数吗？','支持，例如同时声明item和user。','body-multiple-params','declare multiple body parameters'),
('使用Annotated为可选查询参数添加校验时，默认值None代表什么？','表示参数可省略；类型允许None且默认值为None。','query-params-str-validations','FastAPI will know it\'s not required'),
('可选查询参数q要限制最大长度为50，示例如何设置Query？','在Annotated里使用Query(max_length=50)添加最大50字符校验。','query-params-str-validations','Query(max_length=50)')
]

# 30道组合推理题：复用经过来源校验的事实基础，明确条件与结论。
REASON=[
(1,2,'函数参数limit不在路径模板里且默认20，客户端省略limit时，应从哪里取值、是否报缺失错误？','它是查询参数；有默认值，因此不必传，使用20。'),
(2,3,'q有默认值而page没有默认值，客户端都不传时，两者的必填性有什么差异？','q可省略并使用默认值，page属于必填查询参数，必须由客户端提供。'),
(4,6,'接口需要同时接收一个结构化商品对象和一个普通字符串参数，默认情况下两者分别来自哪里？','Pydantic模型参数表示JSON请求体；未显式指定Body的普通标量通常作为查询参数。'),
(4,5,'把请求体声明为Pydantic模型后，如果客户端字段不符合模型，是否还应把原始无效数据直接传入业务函数？','模型声明触发校验，无效数据产生清晰错误；不能把不合法输入当成正常已校验对象。'),
(9,10,'函数返回对象比指定response_model多几个内部字段，同时有另一返回类型注解，客户端最终得到哪些字段？','response_model优先；输出按照该模型过滤，多余内部字段不应返回。'),
(9,11,'响应对象多了一个字段和缺少一个响应模型必填字段，这两种问题的处理是否相同？','不同。多余字段按响应模型过滤；缺失必填字段意味着响应无效并产生服务端错误。'),
(12,5,'客户端提交不合法请求导致RequestValidationError时，这更像输入问题还是服务器响应模型错误？','RequestValidationError由不合法请求触发，属于输入校验问题；客户端会得到指出错误位置和原因的反馈。'),
(14,16,'发送短通知与需要多服务器协作的重计算，是否都应只用进程内BackgroundTasks？','短通知可以响应后运行；需要跨进程或多服务器重计算应考虑Celery等队列工具。'),
(17,19,'嵌套模型里有set[str]标签字段，客户端重复发送同一标签，最终数据结构应怎样理解？','嵌套模型仍可被校验；set只保留唯一标签，重复项不会成为不同元素。'),
(18,19,'深层嵌套Image模型的url若用普通字符串和HttpUrl，校验能力有什么区别？','嵌套模型支持类型校验；HttpUrl专门验证URL，普通str仅表示字符串，不能等价替代URL类型约束。'),
(21,22,'普通表单后来增加文件上传，客户端应该沿用原编码还是切换编码？为什么？','无文件表单通常为application/x-www-form-urlencoded；有文件时采用multipart/form-data。'),
(23,24,'要接收可能较大的上传文件，为什么UploadFile比把所有内容始终放在内存里更适合？还需要什么依赖？','UploadFile使用spooled存储，超过限制转磁盘；接收上传需要python-multipart。'),
(25,26,'Python参数user_agent通过Header读取时，对应HTTP头是什么？客户端大小写不同会影响吗？','默认对应user-agent；HTTP头不区分大小写。'),
(26,27,'客户端用不同大小写多次发送同名请求头，应把它们视为完全不同的头名吗？','不应，头名不区分大小写；同名头可具有多个值，属于重复请求头。'),
(28,29,'请求中UUID和日期时间都以字符串出现，为什么不能说它们在Python里都是普通业务字符串？','序列化形式是字符串，但声明类型分别为UUID和datetime；datetime字符串遵循ISO 8601。'),
(29,30,'事件发生时间与持续时长分别使用datetime和timedelta，默认JSON表示如何区分？','发生时间为ISO 8601字符串；持续时长通常为总秒数浮点数，含义和表示不同。'),
(32,33,'给删除接口声明status_code=204之后，还返回一个JSON说明对象是否合适？','不合适，204表示无内容，响应不应有body。'),
(35,34,'路径参数希望兼有类型识别和预定义取值范围，仅写str够吗？可采用什么？','普通str只声明字符串类型；预定义取值范围可以使用Enum，再由路径参数注解解析。'),
(36,37,'为什么单个item模型与同时声明item、user时，期望的JSON外层结构可能不同？','多个请求体参数形成按参数名组织的结构；单个模型若也要item外层键，可显式设置Body(embed=True)。'),
(38,3,'q类型允许None但没有默认值，与q默认None是否一定具有同样必填性？','不是，默认值影响必填性；默认None可省略，无默认值的查询参数仍可为必填。'),
(1,6,'新增一个未写入路径模板的整数limit参数，没有Body标记，它会自动变成JSON请求体字段吗？','不会；普通标量且不是路径参数通常被识别为查询参数。'),
(7,4,'路径中有item_id而请求体用Item模型，是否必须拆成两个接口？','不需要，FastAPI允许路径参数和Pydantic请求体同时声明。'),
(8,18,'模型url字段要有说明文字又要校验合法URL，可以怎样组合类型与元数据？','用HttpUrl提供URL类型校验，用Field声明模型字段的校验/描述元数据。'),
(14,15,'接口需要先返回“已接受”再发送通知，任务注册与实际执行应如何区分？','接口中用add_task注册通知函数及参数；BackgroundTasks在响应返回之后执行。'),
(16,14,'客户端已经收到响应是否意味着BackgroundTasks执行完毕？这对耗时任务选型有何启示？','不意味着完成，任务响应后才执行；重计算和多服务器执行可考虑独立队列工具。'),
(20,21,'登录接口若声明Form字段，客户端直接发送application/json能等价替代普通表单编码吗？','不能等价；Form用于表单字段，普通表单通常使用application/x-www-form-urlencoded。'),
(11,5,'请求字段错误与返回模型字段错误，都应描述为“客户端没传对参数”吗？','不能。请求错误是输入校验；返回模型错误表明服务端代码返回了无效数据。'),
(13,0,'依赖函数增加参数约束后，接口文档是否必须靠手工备注才能包含这些约束？','不需要只靠手工备注，依赖和子依赖声明会进入自动生成的OpenAPI schema。'),
(31,35,'路径参数用int注解以后，还想增加数值约束和说明，应该继续只靠注解还是配合Path？','int提供类型声明；额外校验与元数据用Path设置。'),
(9,28,'返回对象中UUID需要序列化，同时包含内部调试字段时，响应模型能同时承担哪些职责？','UUID以字符串表示；响应模型限制可输出字段，过滤未声明内部字段。')
]

MULTI=[
(4,12,'一个接口用Pydantic声明JSON请求体，测试发现字段类型不合法。沿着“模型声明→请求校验→异常类型”的链条，应定位到哪种异常？','Pydantic请求体声明触发数据校验；不合法请求在FastAPI内部产生RequestValidationError。'),
(1,13,'公共依赖函数声明了不在路径模板里的limit参数，调用方想从自动文档确认其来源。沿着“参数位置→依赖声明→文档”的链条会如何体现？','普通非路径参数作为查询参数；依赖参数和校验纳入OpenAPI，因此文档会描述这一查询输入。'),
(25,13,'一个公共依赖用Header读取user_agent，若想在接口文档中找到对应HTTP头，应如何从Python名称推导到文档参数？','Header默认将下划线映射为连字符，得到user-agent；依赖的输入声明进入OpenAPI文档。'),
(18,12,'请求体里嵌套图片对象的url声明为HttpUrl，客户端给了无效URL。沿着字段类型到请求异常的链条，失败应如何解释？','HttpUrl用于URL验证；请求数据不合法会触发FastAPI的RequestValidationError，而非正常业务结果。'),
(8,11,'某字段在Pydantic模型里设置了校验规则，该模型又作为响应模型；服务端返回值违反规则时，是忽略规则还是暴露一个服务端错误？','Field定义模型字段校验，响应模型对返回数据校验；违反响应模型是服务端代码问题，产生服务端错误。'),
(20,24,'计划把接收普通表单的接口扩展为带文件上传，沿着“表单输入→文件解析依赖”的链条，除了Form还需准备哪个解析库？','Form负责表单字段；文件上传解析需要安装python-multipart。'),
(22,23,'客户端上传文件采用multipart/form-data，服务端选择UploadFile；当内容增长时，如何从传输编码继续推导到存储方式？','文件表单使用multipart/form-data传输；UploadFile采用spooled存储，小数据内存，超过限制转磁盘。'),
(33,9,'接口响应模型会过滤内部字段，开发者以为返回空字典就能满足204。沿着“输出模型→HTTP状态语义”的链条，这个判断为什么不充分？','响应模型过滤仍是在组织响应数据；204要求根本没有响应体，空JSON对象也不是无body。'),
(29,9,'数据库对象带datetime字段和未公开的内部字段，经响应模型返回后，如何同时判断时间表示与字段可见性？','datetime序列化为ISO 8601字符串；可见字段取决于响应模型，未声明内部字段会被过滤。'),
(17,9,'业务函数返回带重复标签及内部字段的对象，标签在响应模型中声明为set[str]。从类型处理到输出过滤，客户端可见结果应具有什么特点？','set语义保证标签唯一；响应模型只输出声明字段，内部字段应过滤。'),
(3,12,'公共查询参数没有默认值，客户端漏传后接口未进入业务逻辑。沿着“必填判定→输入异常”的链条应怎样定位？','无默认值的查询参数是必填；缺少必填请求输入属于请求校验错误，可定位RequestValidationError。'),
(35,5,'路径参数item_id声明int，客户端传非整数字符串，应该如何从类型声明推导客户端会收到的反馈？','路径参数注解要求int；输入不能转换/校验失败时，FastAPI返回明确的数据错误，而非把它作为合法整数处理。'),
(36,4,'原接口直接接收Item模型，客户端改成{"item": {...}}包装后不匹配。沿着“JSON形状→请求体声明”的链条应怎样调整？','Pydantic模型声明JSON结构；若希望单个模型被item键包装，使用Body(embed=True)。'),
(34,12,'路径参数使用Enum限制可选值，客户端发送集合外值，沿着“允许值→请求是否合法→异常”的链条如何分析？','Enum限定预定义取值；集合外输入不合法，应按请求校验失败处理，内部为RequestValidationError。'),
(31,12,'路径参数增加Path校验约束后，不满足约束的请求该归到业务不存在还是请求校验？请说明推理步骤。','Path声明输入校验，违反声明的参数约束意味着请求不合法，先归为请求校验异常，而非直接认定业务对象不存在。'),
(13,10,'依赖约束出现在OpenAPI中，响应同时有返回注解和response_model。调用者如何分别确定输入契约与输出契约的依据？','输入契约包含依赖和子依赖声明；输出同时有两种声明时response_model优先。'),
(21,24,'从无文件表单扩展到文件接口时，怎样从原有编码推导必须检查的解析依赖？','普通表单通常是application/x-www-form-urlencoded；接收上传文件要安装python-multipart，不能只改业务函数。'),
(16,13,'一个任务接口通过依赖声明提交参数，又要把重计算分到多服务器。沿着“输入契约→任务执行工具”的链条有哪些可确定的设计依据？','依赖输入会进入OpenAPI；多服务器重计算应考虑Celery等独立队列工具，不能由文档自动化推导进程内任务可跨服务器。'),
(38,13,'公共依赖中q默认None且带查询验证，调用者想知道可否省略及在哪确认。沿着“默认值→必填性→文档”应怎样回答？','默认None使参数可省略；依赖中的参数和验证会进入OpenAPI，自动文档可展示该契约。'),
(28,9,'响应对象的ID声明为UUID，另带内部审计字段。如何从字段类型和响应模型两跳推导JSON里的ID表示与审计字段是否输出？','UUID以字符串表示；审计字段只有在响应模型声明时才输出，未声明则过滤。')
]

REFUSALS=[
'飞的公司生产FastAPI服务今天的部署版本号是什么？',
'我们学校内部FastAPI选课系统下周具体哪一天停机维护？',
'这套本地项目昨天在真实生产环境的P95延迟是多少毫秒？',
'某未公开企业内部API的月度实际调用账单金额是多少？',
'张同学私有服务的生产域名与机器部署地点分别是什么？',
'我所在团队下个月负责FastAPI值班的人员名单是什么？',
'某未公开订单服务昨晚具体丢失了多少条业务订单？',
'这份教程对应我公司项目的内部审批负责人是谁？',
'我当前百炼账户剩余可用余额具体是多少元？',
'我公司未公开的接口压测报告中最高吞吐量是多少？'
]


def locate(docs,slug,anchor):
    doc=docs['official-v2-'+slug]
    paragraphs=[p for p in doc.content.split('\n\n') if anchor in p]
    if not paragraphs:
        raise ValueError('未找到原文：'+slug+' / '+anchor)
    # 使用覆盖该规则的最小原文段，保留句子而非标题；长代码段仅截取定位附近。
    paragraph=min(paragraphs,key=len)
    if len(paragraph)>450:
        i=paragraph.index(anchor)
        paragraph=paragraph[max(0,i-80):min(len(paragraph),i+max(250,len(anchor)))]
    start=doc.content.index(paragraph)
    return {'doc_id':doc.id,'quote':paragraph,'start':start,'end':start+len(paragraph)}


async def main():
    init_db();docs=await collect()
    assert len(FACTS)==40 and len(REASON)==30 and len(MULTI)==20 and len(REFUSALS)==10
    with Session() as db:
        by_id={d.id:d for d in db.query(Document).all()}
        evidences=[locate(by_id,f[2],f[3]) for f in FACTS]
        cases=[]
        def add(question,answer,kind,source,note):
            payload={'id':f'AI-{len(cases)+1:03d}','question':question,'type':kind,'gold_answer':answer,
                     'gold_doc':[],'gold_chunk_id':[],'evidence':source,'difficulty':'hard' if kind=='multihop' else 'medium',
                     'status':'ai_reviewed','annotator':None,'reviewed_at':None,
                     'annotation_note':'Codex逐项编写及来源定位；AI辅助核验，未经人工审核。'+note}
            cases.append(validate_case(payload,by_id))
        for i,f in enumerate(FACTS):add(f[0],f[1],'fact',[evidences[i]],'单一来源规则问答。')
        for a,b,q,answer in REASON:add(q,answer,'reasoning',[evidences[a],evidences[b]],'条件组合/比较推导。')
        for a,b,q,answer in MULTI:
            assert evidences[a]['doc_id']!=evidences[b]['doc_id']
            add(q,answer,'multihop',[evidences[a],evidences[b]],'跨文档：输入/类型规则作为中间桥梁，关联异常、输出或文档规则得结论。')
        for q in REFUSALS:add(q,'所提供的公开教程不包含该私有业务/账户/生产信息，应说明依据不足，不能编造。','refusal',[],'知识库范围外的具体私有事实。')
        assert len({c['question'] for c in cases})==100
        dataset_id='dataset-ai-verified-v2'
        if not db.get(Dataset,dataset_id):
            db.add(Dataset(id=dataset_id,name='FastAPI · 100题AI辅助核验（待人工确认）',
                description='23份官方原文；Codex逐项策划与来源校验40/30/20/10。人类审核0题，预评测可运行。'));db.flush()
        for case in cases:
            row_id='question-v2-'+case['id']
            if not db.get(Question,row_id):
                db.add(Question(id=row_id,dataset_id=dataset_id,case_id=case['id'],payload=case))
            elif db.get(Question,row_id).payload.get('status')=='ai_reviewed':
                db.get(Question,row_id).payload=case
        variants=[('01','向量 K3',{}),('02','向量 K1',{'top_k':1}),('03','向量 K5',{'top_k':5}),
                  ('04','递归分块',{'chunk_strategy':'recursive'}),('05','混合检索',{'retrieval':'hybrid'}),
                  ('06','向量阈值0.4',{'similarity_threshold':0.4}),
                  ('07','混合 + 百炼重排',{'retrieval':'hybrid','rerank':True})]
        for suffix,title,delta in variants:
            cid='cloud-v2-'+suffix
            if not db.get(Config,cid):
                db.add(Config(id=cid,name='R'+suffix+' '+title,
                    parameters=Parameters(**{'max_tokens':500,**delta}).model_dump()))
        db.commit()
    (ROOT/'data'/'eval_set_ai_verified.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'dataset_id':dataset_id,'document_ids':[d['id'] for d in docs],
              'config_ids':['cloud-v2-'+str(i).zfill(2) for i in range(1,8)],
              'human_reviewed':0,'status':'ai_reviewed','created_at':datetime.now(timezone.utc).isoformat()}
    (ROOT/'data'/'real_evaluation_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('100 source-checked AI-authored cases ready; zero human reviews',flush=True)


if __name__=='__main__':asyncio.run(main())
