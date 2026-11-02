"""Explicit real API probe using fictional data. Optional --write saves sanitized summary."""
import os,sys,tempfile,json,datetime,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
tmp=tempfile.TemporaryDirectory();os.environ['BANKMATE_DB']=str(Path(tmp.name)/'probe.db')
import app,agent_tools
base=os.getenv('OPENAI_BASE_URL','https://oai.endpoints.kepler.ai.cloud.ovh.net/v1').rstrip('/')
model=os.getenv('OPENAI_MODEL','gpt-oss-20b');key=os.getenv('OPENAI_API_KEY','')
if not key and base!='https://oai.endpoints.kepler.ai.cloud.ovh.net/v1':
 print('没有 API key；仅允许无密钥访问指定的 OVHcloud 沙箱式公开推理入口。',file=sys.stderr);sys.exit(2)
app.init();start=time.monotonic();record={'time_local':datetime.datetime.now().isoformat(timespec='seconds'),'base_url':base,'model':model,'mode':'real_remote_tool_call','input_type':'synthetic only'}
try:
 r,t=agent_tools.run('请查询模拟账户上月账单',base,key,model,app)
 record.update(success=bool(r.get('report') and any(x['tool']=='get_monthly_report' for x in t)),trace=t,transaction_count=r.get('report',{}).get('count'),elapsed_seconds=round(time.monotonic()-start,2))
except Exception as e: record.update(success=False,error=type(e).__name__,elapsed_seconds=round(time.monotonic()-start,2))
print(json.dumps(record,ensure_ascii=False,indent=2))
if '--write' in sys.argv:
 p=Path('evidence/live_model_probe.json');p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
tmp.cleanup();sys.exit(0 if record['success'] else 1)
