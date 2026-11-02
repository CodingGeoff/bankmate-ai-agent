"""Opt-in providers for synthetic-data demo. Secrets are environment-only."""
import os,time,threading
import agent_tools
CATALOG={
 'ovh':('https://oai.endpoints.kepler.ai.cloud.ovh.net/v1','OVH_API_KEY','OVH_MODEL','gpt-oss-20b'),
 'siliconflow':('https://api.siliconflow.cn/v1','SILICONFLOW_API_KEY','SILICONFLOW_MODEL',''),
 'deepseek':('https://api.deepseek.com','DEEPSEEK_API_KEY','DEEPSEEK_MODEL',''),
 'groq':('https://api.groq.com/openai/v1','GROQ_API_KEY','GROQ_MODEL',''),
 'gemini':('https://generativelanguage.googleapis.com/v1beta/openai','GEMINI_API_KEY','GEMINI_MODEL',''),
 'openrouter':('https://openrouter.ai/api/v1','OPENROUTER_API_KEY','OPENROUTER_MODEL',''),
 'openai':('https://api.openai.com/v1','OPENAI_API_KEY','OPENAI_MODEL','')}
_lock=threading.Lock(); _cooldown={}
def configured():
 names=[x.strip().lower() for x in os.getenv('BANKMATE_PROVIDERS','').split(',') if x.strip()]; result=[]
 for n in names[:5]:
  if n not in CATALOG or any(x['name']==n for x in result):continue
  base,keyenv,modelenv,default=CATALOG[n];key=os.getenv(keyenv,'');model=os.getenv(modelenv,default)
  if not model or (not key and not (n=='ovh' and os.getenv('BANKMATE_ALLOW_ANONYMOUS')=='1')):continue
  result.append({'name':n,'base':base,'key':key,'model':model})
 return result
def run(text,bank,runner=agent_tools.run):
 attempts=[]
 for p in configured():
  with _lock: blocked=_cooldown.get(p['name'],0)>time.monotonic()
  if blocked:attempts.append({'provider':p['name'],'status':'cooldown'});continue
  try:
   result,trace=runner(text,p['base'],p['key'],p['model'],bank)
   attempts.append({'provider':p['name'],'status':'success'});return result,trace,attempts
  except agent_tools.AgentUnavailable:
   with _lock:_cooldown[p['name']]=time.monotonic()+30
   attempts.append({'provider':p['name'],'status':'failed'})
 raise RoutingUnavailable(attempts)
class RoutingUnavailable(Exception):
 def __init__(self,attempts):super().__init__('模型服务暂不可用');self.attempts=attempts
