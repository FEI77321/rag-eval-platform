"""使用.env连接MySQL，检查或迁移至空表；不猜密码、不清空已有数据。"""
import argparse,json,sys
from pathlib import Path
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.engine import URL
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.settings import settings
from app.db import Base
from app import models
parser=argparse.ArgumentParser();parser.add_argument('--migrate',action='store_true');args=parser.parse_args()
if not settings.mysql_host or not settings.mysql_password or settings.mysql_password.startswith('replace_'):
    raise SystemExit('请先在本地.env填写MYSQL_HOST/USER/PASSWORD。凭据不发到聊天，不重置现有数据库。')
target=create_engine(URL.create('mysql+pymysql',username=settings.mysql_user,password=settings.mysql_password,
    host=settings.mysql_host,port=settings.mysql_port,database=settings.mysql_database,query={'charset':'utf8mb4'}),pool_pre_ping=True)
try:
    with target.connect() as connection:
        version=connection.scalar(text('SELECT VERSION()'))
        print(json.dumps({'connected':True,'version':version,'database':settings.mysql_database},ensure_ascii=False))
except Exception as error:
    code=error.orig.args[0] if hasattr(error,'orig') and hasattr(error.orig,'args') else type(error).__name__
    raise SystemExit('MySQL连接失败，错误代码：'+str(code)+'。未输出凭据，未修改数据。') from None
if args.migrate:
    source_path=ROOT/'runtime/platform.db'
    if not source_path.is_file():raise SystemExit('SQLite源数据库不存在')
    source=create_engine('sqlite:///'+source_path.as_posix())
    Base.metadata.create_all(target)
    with source.connect() as source_conn,target.begin() as dest_conn:
        tables=Base.metadata.sorted_tables
        if any(dest_conn.scalar(select(func.count()).select_from(table)) for table in tables):
            raise SystemExit('目标含已有项目数据，拒绝覆盖；请选择独立空数据库。')
        counts={}
        for table in tables:
            rows=[dict(row) for row in source_conn.execute(select(table)).mappings()]
            for offset in range(0,len(rows),200):dest_conn.execute(table.insert(),rows[offset:offset+200])
            actual=dest_conn.scalar(select(func.count()).select_from(table))
            assert actual==len(rows)
            counts[table.name]=actual
    print(json.dumps({'migrated':True,'counts':counts,'note':'事务全部提交；SQLite源未修改。重启API/Worker后使用MySQL，再运行小样本和恢复验证。'},ensure_ascii=False))
else:print('只验证连接；没有建表或迁移。迁移到空数据库需显式--migrate。')
