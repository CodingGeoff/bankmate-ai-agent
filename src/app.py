#!/usr/bin/env python3
"""BankMate demo. Standard library only; optional OpenAI-compatible intent parser."""
import os,json,sqlite3,uuid,hashlib,secrets,re,calendar,datetime,urllib.request,urllib.error
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from decimal import Decimal, InvalidOperation
import agent_tools, workflow, provider_router, expansion
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('BANKMATE_DB',ROOT/'bankmate.db'))
NOW=lambda: datetime.datetime.now().isoformat(timespec='seconds')
class ClosingConnection(sqlite3.Connection):
 def __exit__(self, exc_type, exc, tb):
  try: return super().__exit__(exc_type, exc, tb)
  finally: self.close()
def conn():
 c=sqlite3.connect(DB,timeout=10,factory=ClosingConnection); c.row_factory=sqlite3.Row; return c
def init(reset=False):
 with conn() as c:
  if reset: c.executescript('DROP TABLE IF EXISTS transactions; DROP TABLE IF EXISTS payees; DROP TABLE IF EXISTS subscriptions; DROP TABLE IF EXISTS actions; DROP TABLE IF EXISTS reminders; DROP TABLE IF EXISTS audit; DROP TABLE IF EXISTS account; DROP TABLE IF EXISTS cards; DROP TABLE IF EXISTS schedules; DROP TABLE IF EXISTS aa_requests; DROP TABLE IF EXISTS security_state; DROP TABLE IF EXISTS workflows;')
  c.executescript('''CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY, balance INTEGER NOT NULL, reserved INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS payees(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,account TEXT);
 CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,merchant TEXT,amount INTEGER,category TEXT,date TEXT,note TEXT);
 CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY,merchant TEXT,amount INTEGER,next_date TEXT,verified INTEGER,status TEXT);
 CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,status TEXT,token_hash TEXT,expires TEXT,created TEXT,result TEXT);
 CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY,title TEXT,date TEXT);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,action_id TEXT,event TEXT,time TEXT);
 CREATE TABLE IF NOT EXISTS security_state(id INTEGER PRIMARY KEY, failures INTEGER NOT NULL, locked INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY, name TEXT, last4 TEXT, status TEXT, daily_limit INTEGER);
 CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, payee_id INTEGER, payee TEXT, amount INTEGER, due_date TEXT, status TEXT);
 CREATE TABLE IF NOT EXISTS aa_requests(id TEXT PRIMARY KEY, title TEXT, total INTEGER, people INTEGER, shares TEXT, status TEXT);''')
  expansion.init(c,reset)
  if not c.execute('SELECT 1 FROM account').fetchone():
   c.execute('INSERT INTO account VALUES(1,860000,0)'); c.execute("INSERT INTO cards VALUES(1,'银伴借记卡','4826','active',500000)")
   c.executemany('INSERT INTO payees VALUES(?,?,?,?)',[(1,'林晓','138****1122','****3281'),(2,'林晓','139****3344','****6702'),(3,'王晨','137****5566','****1388')])
   today=datetime.date.today(); first=today.replace(day=1); last=first-datetime.timedelta(days=1); prev=(last.replace(day=1)-datetime.timedelta(days=1))
   rows=[]
   for month in (prev,last):
    for d,merchant,amt,cat in [(2,'早餐店',1800,'餐饮'),(3,'地铁',1200,'交通'),(5,'超市',9900,'购物'),(7,'音乐会员',1500,'订阅'),(8,'视频会员',2500,'订阅'),(9,'云存储',1200,'订阅'),(10,'餐厅',4500,'餐饮'),(13,'餐厅',5000,'餐饮'),(16,'咖啡店',2800,'餐饮'),(18,'网约车',3500,'交通'),(20,'书店',7800,'购物'),(22,'餐厅',68000 if month==last else 4200,'餐饮'),(25,'便利店',3200,'餐饮')]:
     rows.append((uuid.uuid4().hex,merchant,amt,cat,month.replace(day=min(d,calendar.monthrange(month.year,month.month)[1])).isoformat(),''))
   c.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?)',rows)
   nxt=(first+datetime.timedelta(days=32)).replace(day=8)
   c.executemany('INSERT INTO subscriptions VALUES(?,?,?,?,?,?)',[(1,'视频会员',2500,nxt.isoformat(),1,'active'),(2,'音乐会员',1500,nxt.replace(day=7).isoformat(),1,'active'),(3,'云存储',1200,nxt.replace(day=9).isoformat(),0,'suspected')])
  if not c.execute('SELECT 1 FROM security_state').fetchone(): c.execute('INSERT INTO security_state VALUES(1,0,0)')
  if not c.execute('SELECT 1 FROM cards').fetchone(): c.execute("INSERT INTO cards VALUES(1,'银伴借记卡','4826','active',500000)")
def money(n): return f'{n/100:,.2f}'
def audit(c,aid,event): c.execute('INSERT INTO audit(action_id,event,time) VALUES(?,?,?)',(aid,event,NOW()))
def risk_level(kind,payload,c):
 if kind in ('card_lock','card_unlock','wealth_buy','wealth_sell'): return 'red'
 if kind=='transfer':
  total=c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE category='转账' AND date=?",(datetime.date.today().isoformat(),)).fetchone()[0]
  return 'red' if total+payload['amount_fen']>100000 else 'yellow'
 return 'yellow'
def prepare(kind,payload):
 aid=uuid.uuid4().hex; token=secrets.token_urlsafe(24); exp=(datetime.datetime.now()+datetime.timedelta(minutes=10)).isoformat(timespec='seconds')
 with conn() as c:
  c.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(aid,kind,json.dumps(payload,ensure_ascii=False),'pending',hashlib.sha256(token.encode()).hexdigest(),exp,NOW(),None)); audit(c,aid,'prepared')
 with conn() as c: risk=risk_level(kind,payload,c)
 return {'id':aid,'kind':kind,'payload':payload,'token':token,'expires':exp,'risk':risk}
def get_state():
 with conn() as c:
  acc=dict(c.execute('SELECT * FROM account').fetchone()); subs=[dict(x) for x in c.execute('SELECT * FROM subscriptions')]; actions=[dict(x) for x in c.execute('SELECT id,kind,payload,status,created,result FROM actions ORDER BY created DESC,rowid DESC LIMIT 30')]; reminders=[dict(x) for x in c.execute('SELECT * FROM reminders ORDER BY date')]
 
 with conn() as c:
  cards=[dict(x) for x in c.execute('SELECT * FROM cards')]; schedules=[dict(x) for x in c.execute('SELECT * FROM schedules')]; aa=[dict(x) for x in c.execute('SELECT * FROM aa_requests')]; logs=[dict(x) for x in c.execute('SELECT action_id,event,time FROM audit ORDER BY id DESC LIMIT 40')]
 return {'cards':cards,'schedules':schedules,'aa_requests':aa,'audit':logs,'account':acc,'subscriptions':subs,'actions':actions,'reminders':reminders,'mode':('工具调用已配置（逐请求显示结果）' if os.getenv('BANKMATE_TOOL_AGENT')=='1' and (os.getenv('OPENAI_MODEL') or os.getenv('BANKMATE_PROVIDERS')) else '大模型意图解析' if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL') else '规则解析（可配置大模型）')}
def execute(aid,token,verification_code=""):
 c=conn()
 try:
  c.execute('BEGIN IMMEDIATE'); a=c.execute('SELECT * FROM actions WHERE id=?',(aid,)).fetchone()
  if not a: raise ValueError('操作不存在')
  if not secrets.compare_digest(a['token_hash'],hashlib.sha256(token.encode()).hexdigest()): raise ValueError('确认凭证无效')
  if a['status']=='executed': c.commit(); return json.loads(a['result'])
  if a['status']!='pending': raise ValueError('操作已取消或不可执行')
  if a['expires']<NOW(): c.execute("UPDATE actions SET status='expired' WHERE id=?",(aid,)); audit(c,aid,'expired'); c.commit(); raise ValueError('确认已过期，请重新发起')
  p=json.loads(a['payload']); kind=a['kind']; acc=c.execute('SELECT * FROM account WHERE id=1').fetchone()
  security=c.execute('SELECT * FROM security_state WHERE id=1').fetchone()
  if security['locked']: raise ValueError('演示安全锁已触发，请重置演示数据')
  if risk_level(kind,p,c)=='red':
   if not secrets.compare_digest(str(verification_code),'246810'):
    c.execute('UPDATE security_state SET failures=failures+1,locked=CASE WHEN failures+1>=3 THEN 1 ELSE 0 END WHERE id=1'); audit(c,aid,'demo_verification_failed'); c.commit(); raise ValueError('需要模拟验证码；失败三次触发演示安全锁')
   c.execute('UPDATE security_state SET failures=0 WHERE id=1'); audit(c,aid,'demo_verification_passed')
  if kind=='transfer':
   if not c.execute('SELECT 1 FROM payees WHERE id=?',(p['payee_id'],)).fetchone(): raise ValueError('收款人不存在')
   amount=p['amount_fen']
   card=c.execute('SELECT * FROM cards WHERE id=1').fetchone()
   if not card or card['status']!='active': raise ValueError('模拟卡片不可用')
   daily=c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE category='转账' AND date=?",(datetime.date.today().isoformat(),)).fetchone()[0]
   if daily+amount>card['daily_limit']:raise ValueError('超过模拟卡片日限额')
   if not isinstance(amount,int) or amount<=0 or amount>5000000: raise ValueError('金额无效或超过演示限额')
   if acc['balance']-acc['reserved']<amount: raise ValueError('可用余额不足')
   c.execute('UPDATE account SET balance=balance-? WHERE id=1',(amount,)); tid=uuid.uuid4().hex[:12]; c.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?)',(tid,p['payee'],amount,'转账',datetime.date.today().isoformat(),p['note']))
   result={'message':f"模拟转账成功：向 {p['payee']} 转出 ¥{money(amount)}。",'transaction_id':tid}
  elif kind=='cancel_subscription':
   sub=c.execute('SELECT * FROM subscriptions WHERE id=?',(p['subscription_id'],)).fetchone()
   if not sub or not sub['verified'] or sub['status']!='active': raise ValueError('协议不存在、未核实或已取消')
   c.execute("UPDATE subscriptions SET status='cancelled' WHERE id=?",(sub['id'],)); result={'message':f"已模拟取消 {sub['merchant']} 的代扣协议。"}
  elif kind=='reserve':
   amount=p['amount_fen']
   if not isinstance(amount,int) or amount<=0 or acc['balance']-acc['reserved']<amount: raise ValueError('金额无效或可用余额不足')
   c.execute('UPDATE account SET reserved=reserved+? WHERE id=1',(amount,)); rid=uuid.uuid4().hex[:12]; c.execute('INSERT INTO reminders VALUES(?,?,?)',(rid,p['reminder'],p['reminder_date']));
   if p.get('plan_order'): c.execute('INSERT INTO orders VALUES(?,?,?,?,?)',(uuid.uuid4().hex,'鲜花和蛋糕',amount,p['reminder_date'],'planned'))
   result={'message':f"已模拟预留 ¥{money(amount)}，并创建 {p['reminder_date']} 的提醒。"}
  elif kind=='card_lock':
   card=c.execute('SELECT * FROM cards WHERE id=?',(p['card_id'],)).fetchone()
   if not card or card['status']!='active': raise ValueError('卡片不存在或不可挂失')
   c.execute("UPDATE cards SET status='locked' WHERE id=?",(card['id'],)); result={'message':f"已模拟挂失尾号 {card['last4']} 的卡片；此操作不会影响真实银行卡。"}
  elif kind=='scheduled_transfer':
   if not c.execute('SELECT 1 FROM payees WHERE id=?',(p['payee_id'],)).fetchone(): raise ValueError('收款人不存在')
   if p['amount_fen']<=0 or p['amount_fen']>5000000: raise ValueError('金额无效')
   if datetime.date.fromisoformat(p['due_date'])<=datetime.date.today(): raise ValueError('日期必须在未来')
   sid=uuid.uuid4().hex[:12]; c.execute('INSERT INTO schedules VALUES(?,?,?,?,?,?)',(sid,p['payee_id'],p['payee'],p['amount_fen'],p['due_date'],'planned'))
   result={'message':f"已创建 {p['due_date']} 的模拟定时转账计划。演示系统不会到期自动扣款，请勿视为已转账。"}
  elif kind=='aa':
   if p['people']<2 or p['people']>100 or p['total_fen']<=0: raise ValueError('AA参数无效')
   n=p['people']; q,rem=divmod(p['total_fen'],n); shares=[q+(1 if i<rem else 0) for i in range(n)]
   c.execute('INSERT INTO aa_requests VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex[:12],p['title'],p['total_fen'],n,json.dumps(shares),'planned')); result={'message':f"已创建模拟 AA 计划：{n} 人分摊，总额 ¥{money(p['total_fen'])}。未发起真实收款。"}
  elif kind in ('wealth_buy','wealth_sell','card_apply','card_unlock','card_limit','mock_order'):
   import sys
   result=expansion.execute(c,kind,p,acc,sys.modules[__name__])
  else: raise ValueError('未知操作')
  c.execute("UPDATE actions SET status='executed',result=? WHERE id=?",(json.dumps(result,ensure_ascii=False),aid)); audit(c,aid,'executed'); workflow.sync_action(c,aid,'completed'); c.commit(); return result
 except Exception:
  c.rollback(); raise
 finally: c.close()
def cancel(aid,token):
 with conn() as c:
  a=c.execute('SELECT * FROM actions WHERE id=?',(aid,)).fetchone()
  if not a or not secrets.compare_digest(a['token_hash'],hashlib.sha256(token.encode()).hexdigest()): raise ValueError('操作或凭证无效')
  if a['status']!='pending': raise ValueError('操作不可取消')
  c.execute("UPDATE actions SET status='cancelled' WHERE id=?",(aid,)); audit(c,aid,'cancelled'); workflow.sync_action(c,aid,'cancelled')
 return {'message':'已取消，未执行任何业务操作。'}
def report():
 first=datetime.date.today().replace(day=1); last=first-datetime.timedelta(days=1); start=last.replace(day=1); prevlast=start-datetime.timedelta(days=1); prevstart=prevlast.replace(day=1)
 with conn() as c:
  rows=[dict(x) for x in c.execute('SELECT * FROM transactions WHERE date BETWEEN ? AND ? AND category != ?', (start.isoformat(),last.isoformat(),'转账'))]; prior=c.execute('SELECT COALESCE(SUM(amount),0) FROM transactions WHERE date BETWEEN ? AND ? AND category != ?', (prevstart.isoformat(),prevlast.isoformat(),'转账')).fetchone()[0]
 cats={}
 for r in rows: cats[r['category']]=cats.get(r['category'],0)+r['amount']
 anomalies=[]
 for r in rows:
  peers=sorted(x['amount'] for x in rows if x['category']==r['category'] and x['id']!=r['id'])
  if len(peers)>=3:
   n=len(peers); med=peers[n//2] if n%2 else (peers[n//2-1]+peers[n//2])/2
   if med and r['amount']>3*med: anomalies.append({**r,'median':med})
 return {'month':start.strftime('%Y-%m'),'total':sum(x['amount'] for x in rows),'prior':prior,'categories':cats,'anomalies':anomalies,'count':len(rows)}
def parse_llm(text):
 key=os.getenv('OPENAI_API_KEY'); model=os.getenv('OPENAI_MODEL')
 if not key or not model: return None
 base=os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/')
 instruction='你是银行演示应用的意图解析器。只输出JSON对象，不要执行任何操作。字段 intent 为 transfer、report、subscriptions、cancel、birthday、unknown之一；可选字段 name（收款人姓名）、amount（人民币数值）、merchant（商户）、birthday（YYYY-MM-DD）、note。不要猜测缺失值。'
 body={'model':model,'messages':[{'role':'system','content':instruction},{'role':'user','content':text}],'temperature':0}
 req=urllib.request.Request(base+'/chat/completions',json.dumps(body).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=15) as r: content=json.load(r)['choices'][0]['message']['content']
  content=re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip()); obj=json.loads(content)
  return obj if isinstance(obj,dict) and obj.get('intent') in ['transfer','report','subscriptions','cancel','birthday','unknown'] else None
 except Exception: return None
def yuan_fen(v):
 try:
  n=Decimal(str(v))*100
  if not n.is_finite() or n!=n.to_integral_value() or n<=0 or n>5000000: return None
  return int(n)
 except (InvalidOperation,ValueError,TypeError): return None
def chat(text,choice=None,use_llm=True):
 text=str(text).strip()[:1000];
 if re.search(r'[-－负]\s*\d+(?:\.\d+)?\s*(?:元|块)',text): return {'message':'金额不能为负数，未生成任何操作。'}
 import sys
 added=expansion.parse(text,sys.modules[__name__])
 if added is not None:return added
 # Sensitive capabilities are deterministic and do not depend on model output.
 if any(x in text for x in ['理财','产品对比','产品推荐']):
  return {'message':'以下为虚构产品，仅供功能演示，不构成投资建议或真实销售。稳健型示例：低波动目标，非保本，持有期示例30天；成长型示例：波动可能较大，非保本，持有期示例90天。实际风险、费用与流动性应以真实产品文件为准。本原型不提供个性化适当性评估，也不支持申购或赎回。'}
 if '卡片' in text or '银行卡' in text:
  if '挂失' not in text and '冻结' not in text:
   with conn() as c: card=c.execute('SELECT * FROM cards LIMIT 1').fetchone()
   return {'message':f"模拟卡片：{card['name']}，尾号 {card['last4']}，状态：{'正常' if card['status']=='active' else '已挂失'}。如需操作，请输入‘挂失我的银行卡’。"}
 if any(x in text for x in ['挂失','冻结卡']):
  with conn() as c: card=c.execute('SELECT * FROM cards LIMIT 1').fetchone()
  if not card or card['status']!='active': return {'message':'演示卡片已挂失或不存在。'}
  return {'message':'请确认模拟挂失。此操作不会影响真实银行卡。','action':prepare('card_lock',{'card_id':card['id'],'card':card['name'],'last4':card['last4']})}
 if ('AA' in text.upper() or '平摊' in text or '分摊' in text):
  am=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text); count=re.search(r'(\d+)\s*(?:个人|人)',text); amount=yuan_fen(am.group(1) if am else None); n=int(count.group(1)) if count else 0
  if not amount or n<2 or n>100: return {'message':'请提供总金额和2至100人的人数，例如：300元，3人AA平摊。'}
  q,rem=divmod(amount,n)
  return {'message':'按分精确平摊，余数分配给前几人；这是模拟计划，不会发送收款请求。','action':prepare('aa',{'title':'AA平摊','total_fen':amount,'people':n,'shares':[q+(1 if i<rem else 0) for i in range(n)]})}
 if '定时' in text and '转' in text:
  am=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text); dt=re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})日?',text); amount=yuan_fen(am.group(1) if am else None)
  try: date=datetime.date(int(dt.group(1)),int(dt.group(2)),int(dt.group(3))) if dt else None
  except ValueError: date=None
  with conn() as c: payees=[dict(x) for x in c.execute('SELECT * FROM payees')]
  matches=[p for p in payees if p['name'] in text and (not choice or p['id']==choice)]
  if not amount or not date or date<=datetime.date.today() or not matches: return {'message':'请提供未来完整日期、收款人和金额，例如：2027年12月20日定时给王晨转200元。'}
  if len(matches)>1: return {'message':'请先选择同名收款人。','choices':matches,'original':text}
  p=matches[0]; return {'message':'请确认模拟定时计划。系统不会自动扣款。','action':prepare('scheduled_transfer',{'payee_id':p['id'],'payee':p['name'],'account':p['account'],'amount_fen':amount,'due_date':date.isoformat()})}
 llm=parse_llm(text) if use_llm else None; intent=(llm or {}).get('intent');
 if not intent or intent=='unknown':
  if ('生日' in text and ('预留' in text or '提醒' in text)): intent='birthday'
  elif ('取消' in text or '关闭' in text) and any(s in text for s in ['会员','订阅','代扣']): intent='cancel'
  elif any(s in text for s in ['订阅','续费','代扣','会员']): intent='subscriptions'
  elif any(s in text for s in ['转账','转给','转给','转','汇款']): intent='transfer'
  elif any(s in text for s in ['账单','消费','支出','花了','异常']): intent='report'
  else: intent='unknown'
 if intent=='report':
  r=report(); detail='；'.join(f'{k} ¥{money(v)}' for k,v in r['categories'].items()); anomaly=' '.join(f"{x['date']} {x['merchant']} ¥{money(x['amount'])} 超过同类其他交易中位数的3倍，建议核实。" for x in r['anomalies']) or '未发现符合演示规则的异常。'
  return {'message':f"{r['month']} 支出 ¥{money(r['total'])}，共 {r['count']} 笔；上月 ¥{money(r['prior'])}。{detail}。{anomaly}统计仅供参考，不代表欺诈判断。",'report':r}
 if intent=='subscriptions': return {'message':'以下为演示订阅列表。已核实代表模拟协议库中存在协议；疑似订阅仅来自周期交易线索，不能直接取消。','subscriptions':get_state()['subscriptions']}
 if intent=='cancel':
  subs=get_state()['subscriptions']; merchant=(llm or {}).get('merchant') or next((s['merchant'] for s in subs if s['merchant'] in text),None)
  if not merchant: return {'message':'请指定要取消的订阅，例如：取消视频会员。'}
  s=next((x for x in subs if x['merchant']==merchant),None)
  if not s: return {'message':'没有找到对应订阅。'}
  if not s['verified']: return {'message':'该项目仅为疑似周期扣费，没有已核实的模拟代扣协议，不能直接取消。'}
  if s['status']!='active': return {'message':'该协议已取消。'}
  return {'message':'请核对以下信息。只有确认后才会模拟取消。','action':prepare('cancel_subscription',{'subscription_id':s['id'],'merchant':s['merchant'],'amount_fen':s['amount']})}
 if intent=='transfer':
  with conn() as c: payees=[dict(x) for x in c.execute('SELECT * FROM payees')]
  name=(llm or {}).get('name') or next((p['name'] for p in payees if p['name'] in text),None)
  matches=[p for p in payees if p['name']==name or (len(text)>=4 and p['account'][-4:] in text)]
  if choice: matches=[p for p in matches if p['id']==choice]
  m=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text); amount=yuan_fen((llm or {}).get('amount') or (m.group(1) if m else None))
  if not matches: return {'message':'未找到收款人。请使用演示收款人林晓或王晨，并注明金额（如“给王晨转200元”）。'}
  if not amount: return {'message':'请提供有效金额，例如“给王晨转200元”，演示单笔上限为 50,000 元。'}
  if len(matches)>1: return {'message':'找到多位同名收款人，请选择账户。','choices':matches,'original':text}
  p=matches[0]; note=(llm or {}).get('note') or ('饭钱' if '饭钱' in text else '')
  return {'message':'请核对收款人和金额。确认前不会执行转账。','action':prepare('transfer',{'payee_id':p['id'],'payee':p['name'],'account':p['account'],'amount_fen':amount,'note':str(note)[:100]})}
 if intent=='birthday':
  m=re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})日?',text); raw=(llm or {}).get('birthday')
  try: day=datetime.date.fromisoformat(raw) if raw else datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))) if m else None
  except (ValueError,TypeError): day=None
  am=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text); amount=yuan_fen((llm or {}).get('amount') or (am.group(1) if am else None))
  if not day or not amount: return {'message':'请提供完整生日日期和预留金额，例如：2027年12月20日是爱人生日，预留1000元，提前两天提醒。'}
  reminder=day-datetime.timedelta(days=2)
  if reminder<datetime.date.today(): return {'message':'提醒日期已过去，请提供未来日期。'}
  return {'message':'我将预留预算，并在生日前两天创建提醒；不会自动下单。请确认。','action':prepare('reserve',{'amount_fen':amount,'birthday':day.isoformat(),'reminder_date':reminder.isoformat(),'reminder':'准备生日蛋糕和鲜花'})}
 return {'message':'我可以帮你模拟转账、分析上月账单、查看订阅或规划生日预算。请描述具体需求。'}
class Handler(BaseHTTPRequestHandler):
 def respond(self,code,obj):
  b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/state': return self.respond(200,get_state())
  if path.startswith('/api/workflow/'):
   try:
    import sys
    return self.respond(200,workflow.get(sys.modules[__name__],path.rsplit('/',1)[-1]))
   except ValueError as e: return self.respond(404,{'error':str(e)})
  if path=='/api/report': return self.respond(200,report())
  files={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/app.js':'app.js'}
  if path not in files: return self.respond(404,{'error':'未找到'})
  f=ROOT/'static'/files[path]; b=f.read_bytes(); self.send_response(200); self.send_header('Content-Type',{'html':'text/html','css':'text/css','js':'application/javascript'}[f.suffix[1:]]+'; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_POST(self):
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>20000: raise ValueError('请求过大')
   data=json.loads(self.rfile.read(length) or b'{}'); path=urlparse(self.path).path
   if path=='/api/chat':
    text=data.get('message',''); choice=data.get('choice')
    import sys
    extended=expansion.parse(str(text)[:1000],sys.modules[__name__])
    if extended is not None: result=extended;result['parser_mode']='规则解析'
    elif os.getenv('BANKMATE_TOOL_AGENT')=='1' and provider_router.configured() and not choice:
     try:
      import sys
      result,trace,attempts=provider_router.run(str(text)[:1000],sys.modules[__name__]);result['trace']=trace;result['providers']=attempts;result['parser_mode']='工具调用模型：'+attempts[-1]['provider']
     except provider_router.RoutingUnavailable as e:
      result=chat(text,choice,use_llm=False);result['providers']=e.attempts;result['parser_mode']='模型不可用，已回退规则解析；请核对'
    elif os.getenv('BANKMATE_TOOL_AGENT')=='1' and os.getenv('BANKMATE_PROVIDERS') and not choice:
     result=chat(text,choice,use_llm=False);result['parser_mode']='未配置可用模型，使用规则解析'
    elif os.getenv('BANKMATE_TOOL_AGENT')=='1' and os.getenv('OPENAI_MODEL') and (os.getenv('OPENAI_API_KEY') or (os.getenv('BANKMATE_ALLOW_ANONYMOUS')=='1' and os.getenv('OPENAI_BASE_URL','').rstrip('/')=='https://oai.endpoints.kepler.ai.cloud.ovh.net/v1')) and not choice:
     try:
      import sys
      result,trace=agent_tools.run(str(text)[:1000],os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1'),os.getenv('OPENAI_API_KEY',''),os.environ['OPENAI_MODEL'],sys.modules[__name__]); result['trace']=trace; result['parser_mode']='工具调用模型（单次请求）'
     except agent_tools.AgentUnavailable:
      result=chat(text,choice,use_llm=False); result['parser_mode']='工具调用未完成，已回退规则解析；请核对'
    else: result=chat(text,choice); result['parser_mode']='常规解析'
   elif path=='/api/workflow/create':
    import sys
    result=workflow.create(sys.modules[__name__],data.get('amount_fen'),data.get('birthday'))
   elif path in ('/api/workflow/confirm','/api/workflow/cancel'):
    import sys
    result=workflow.finish(sys.modules[__name__],str(data.get('workflow_id','')),str(data.get('id','')),str(data.get('token','')),str(data.get('verification_code','')),path.endswith('cancel'))
   elif path=='/api/confirm': result=execute(str(data.get('id','')),str(data.get('token','')),str(data.get('verification_code','')))
   elif path=='/api/cancel': result=cancel(str(data.get('id','')),str(data.get('token','')))
   elif path=='/api/reset': init(True); result={'message':'演示数据已重置。'}
   else: return self.respond(404,{'error':'未找到'})
   self.respond(200,result)
  except (ValueError,TypeError,json.JSONDecodeError) as e: self.respond(400,{'error':str(e)})
  except Exception as e: print('ERROR',repr(e),flush=True); self.respond(500,{'error':'服务器错误，请查看服务日志'})
if __name__=='__main__':
 init(); port=int(os.getenv('PORT','8000')); print(f'BankMate demo running on http://0.0.0.0:{port}',flush=True); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
