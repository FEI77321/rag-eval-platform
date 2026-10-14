import pytest
from app.metrics import evidence_retrieval
from app.schemas import Parameters, Case
from app.rag import fixed_spans, recursive_spans


def test_multiple_sources_distinguish_hit_and_recall():
    case = {'type':'multihop','evidence':[{'doc_id':'a','quote':'alpha'}, {'doc_id':'b','quote':'beta'}]}
    result = evidence_retrieval(case,[{'doc_id':'a','text':'alpha','id':'x'}])
    assert result == {'recall':0.5,'hit':1.0,'all_evidence':0.0,'mrr':1.0,'hit1':1.0}


def test_refusal_is_not_retrieval_failure():
    assert all(v is None for v in evidence_retrieval({'type':'refusal','evidence':[]},[]).values())


def test_ranking_and_missing_evidence():
    case = {'type':'fact','evidence':[{'doc_id':'a','quote':'correct evidence'}]}
    chunks = [{'doc_id':'b','text':'noise'}, {'doc_id':'a','text':'correct evidence'}]
    assert evidence_retrieval(case,chunks)['mrr'] == 0.5
    assert evidence_retrieval(case,chunks)['hit1'] == 0
    assert evidence_retrieval(case,[])['recall'] == 0


def test_offset_mapping_across_chunk_versions():
    case = {'type':'fact','evidence':[{'doc_id':'d','quote':'1234567890','start':100,'end':110}]}
    assert evidence_retrieval(case,[{'doc_id':'d','start':98,'end':109,'text':'x','id':'new-version'}])['recall'] == 1
    assert evidence_retrieval(case,[{'doc_id':'d','start':98,'end':104,'text':'x'}])['recall'] == 0


@pytest.mark.parametrize('strategy',[fixed_spans,recursive_spans])
def test_chunker_covers_text_without_infinite_loop(strategy):
    text = ('段落正文。\n\n' * 200) + 'END'
    spans = list(strategy(text,100,80))
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(0 < end-start <= 100 for start,end in spans)
    assert all(spans[i][0] <= spans[i-1][1] for i in range(1,len(spans)))


def test_invalid_parameters_and_fake_review_are_rejected():
    with pytest.raises(ValueError):
        Parameters(chunk_size=100,chunk_overlap=100)
    with pytest.raises(ValueError):
        Parameters(top_k=5,candidate_k=2)
    with pytest.raises(ValueError):
        Case(id='q',question='无答案？',type='refusal',gold_answer='拒答',status='reviewed')
