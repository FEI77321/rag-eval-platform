"""读取DeepSeek实际余额，不调用模型，不输出密钥。"""
import json,sys
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.settings import settings
with httpx.Client(timeout=20,trust_env=False) as client:
    response=client.get(settings.generation_base_url.rstrip('/')+'/user/balance',
                        headers={'Authorization':'Bearer '+settings.generation_api_key})
    if response.status_code!=200:raise SystemExit('余额查询HTTP '+str(response.status_code))
    data=response.json()
    print(json.dumps({'is_available':data.get('is_available'),'balance_infos':data.get('balance_infos',[])},ensure_ascii=False))
