"""读取项目.env，发起一次两条文本的真实Embedding连通测试。"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def check():
    from openai import AsyncOpenAI, APIStatusError, APIConnectionError, APITimeoutError
    from app.settings import settings

    if not settings.embedding_api_key:
        raise SystemExit('请先在项目.env填写EMBEDDING_API_KEY（百炼API Key）。')
    if '{' in settings.embedding_base_url or '}' in settings.embedding_base_url:
        raise SystemExit('EMBEDDING_BASE_URL仍包含占位符；请替换成实际业务空间地址。')
    if settings.embedding_base_url.rstrip('/').endswith('/embeddings'):
        raise SystemExit('BASE_URL不要带末尾/embeddings，SDK会自动添加该路径。')
    texts = ['FastAPI通过Pydantic模型校验请求体。', '怎样验证FastAPI接口收到的数据？']
    try:
        async with AsyncOpenAI(api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url, timeout=settings.request_timeout, max_retries=0) as client:
            reply = await client.embeddings.create(model=settings.embedding_model,
                input=texts, encoding_format='float')
    except APIStatusError as exc:
        status = exc.status_code
        hints = {400:'检查模型名、输入参数及业务空间地址。',
                 401:'检查Key是否有效，以及Key与接口地域是否一致。',
                 403:'检查业务空间的模型调用权限和账号服务状态。',
                 404:'检查BASE_URL和模型是否在所选地域可用。',
                 429:'检查调用限额、额度或服务端返回的限流原因。'}
        raise SystemExit(f'Embedding调用失败：HTTP {status}。' + hints.get(status,'请检查百炼控制台服务状态。')) from None
    except (APIConnectionError, APITimeoutError):
        raise SystemExit('Embedding网络连接失败或超时，请检查接口地址及网络。') from None
    vectors = sorted(reply.data, key=lambda item:item.index)
    if len(vectors) != len(texts) or any(not item.embedding for item in vectors):
        raise SystemExit('响应向量数量或内容异常。')
    print(json.dumps({'status':'success','model':reply.model,'texts':len(texts),
        'dimensions':[len(item.embedding) for item in vectors],
        'usage':reply.usage.model_dump() if reply.usage else None,
        'note':'本次只测试Embedding；不会创建RAG任务或调用DeepSeek。'},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='使用项目.env真实调用一次Embedding（两条短文本，有实际用量）')
    parser.parse_args()
    asyncio.run(check())
