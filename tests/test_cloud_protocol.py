"""验证请求/响应协议与调用账本，不消耗真实云额度。"""
import json
from types import SimpleNamespace
import pytest
from app.providers import Gateway, CALL_CONTEXT
from app.schemas import Parameters
from app.db import Session
from app.models import ApiCall
from sqlalchemy import select


class Usage:
    prompt_tokens=100
    completion_tokens=20
    def model_dump(self):
        return {'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}


@pytest.mark.asyncio
async def test_generation_does_not_receive_gold_and_records_usage():
    requests=[]
    class Completion:
        async def create(self,**kwargs):
            requests.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='证据答案'))],usage=Usage(),model='deepseek-flash')
    fake=SimpleNamespace(chat=SimpleNamespace(completions=Completion()))
    gateway=Gateway('cloud')
    gateway.client=lambda role:fake
    token=CALL_CONTEXT.set(('test-run','test-item'))
    result=await gateway.generate('问题',[{'id':'chunk','text':'retrieved only'}],Parameters().model_dump())
    CALL_CONTEXT.reset(token)
    content=requests[0]['messages'][1]['content']
    assert 'gold_answer' not in content and 'retrieved only' in content
    assert result['usage']=={'input_tokens':100,'output_tokens':20}
    with Session() as db:
        call=db.scalars(select(ApiCall)).one()
        assert call.role=='generation' and call.item_id=='test-item'
        assert call.payload['usage']['total_tokens']==120


@pytest.mark.asyncio
async def test_embedding_batches_follow_ten_input_limit():
    sizes=[]
    class Embedding:
        async def create(self,model,input):
            sizes.append(len(input))
            return SimpleNamespace(data=[SimpleNamespace(index=i,embedding=[1.0,0.0]) for i in range(len(input))],usage=None)
    gateway=Gateway('cloud')
    gateway.client=lambda role:SimpleNamespace(embeddings=Embedding())
    result=await gateway.embed(['x']*23)
    assert sizes==[10,10,3] and len(result)==23


@pytest.mark.asyncio
async def test_judge_rejects_invented_citation():
    class Completion:
        async def create(self,**kwargs):
            output={'accuracy':5,'completeness':5,'refused':False,'unsupported':False,
                    'factually_incorrect':False,'reason':'test fixture','evidence_ids':['invented']}
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(output)))],usage=Usage(),model='judge')
    gateway=Gateway('cloud')
    gateway.client=lambda role:SimpleNamespace(chat=SimpleNamespace(completions=Completion()))
    with pytest.raises(ValueError,match='不存在'):
        await gateway.judge({'question':'q','type':'fact','gold_answer':'a','evidence':[]},
                            {'answer':'a','chunks':[{'id':'actual','text':'a'}]})
