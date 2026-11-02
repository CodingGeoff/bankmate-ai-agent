"""Persisted birthday workflow. Demo only; no authentication or production isolation."""
import json,uuid,datetime,secrets,hashlib

def init(bank):
 with bank.conn() as c: c.execute('CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,status TEXT NOT NULL,steps TEXT NOT NULL,action_id TEXT,created TEXT NOT NULL)')
def get(bank,wid):
 init(bank)
 with bank.conn() as c: row=c.execute('SELECT * FROM workflows WHERE id=?',(wid,)).fetchone()
 if not row: raise ValueError('任务不存在')
 return {'id':row['id'],'status':row['status'],'steps':json.loads(row['steps']),'action_id':row['action_id'],'created':row['created']}
def sync_action(c,aid,status):
 if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='workflows'").fetchone():return
 row=c.execute('SELECT id,steps FROM workflows WHERE action_id=?',(aid,)).fetchone()
 if row:
  steps=json.loads(row['steps']); steps[2]['status']=status
  c.execute('UPDATE workflows SET status=?,steps=? WHERE id=?',(status,json.dumps(steps,ensure_ascii=False),row['id']))
def create(bank,amount_fen,birthday):
 if type(amount_fen)!=int or not 0<amount_fen<=5000000: raise ValueError('金额无效')
 try: day=datetime.date.fromisoformat(birthday)
 except (ValueError,TypeError): raise ValueError('请输入 YYYY-MM-DD 日期') from None
 reminder=day-datetime.timedelta(days=2)
 if reminder<datetime.date.today(): raise ValueError('提醒日期已过去')
 init(bank);r=bank.report();wid=uuid.uuid4().hex;aid=uuid.uuid4().hex;token=secrets.token_urlsafe(24);exp=(datetime.datetime.now()+datetime.timedelta(minutes=10)).isoformat(timespec='seconds')
 payload={'amount_fen':amount_fen,'birthday':day.isoformat(),'reminder_date':reminder.isoformat(),'reminder':'准备生日蛋糕和鲜花','plan_order':True}
 c=bank.conn()
 try:
  c.execute('BEGIN IMMEDIATE');acc=c.execute('SELECT * FROM account WHERE id=1').fetchone();available=acc['balance']-acc['reserved']
  if available<amount_fen:raise ValueError('可用余额不足，不生成任务')
  steps=[{'id':'balance','depends_on':[],'label':'查询可用余额','status':'done','detail':f'模拟可用余额 ¥{bank.money(available)}'}, {'id':'report','depends_on':['balance'],'label':'分析上月账单','status':'done','detail':f"{r['month']} 支出 ¥{bank.money(r['total'])}"}, {'id':'reserve','depends_on':['balance','report'],'label':'预留预算并记录订购计划','status':'waiting_confirmation','detail':'等待用户确认；不会实际推送、下单或付款'}]
  c.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(aid,'reserve',json.dumps(payload,ensure_ascii=False),'pending',hashlib.sha256(token.encode()).hexdigest(),exp,bank.NOW(),None));bank.audit(c,aid,'prepared')
  c.execute('INSERT INTO workflows VALUES(?,?,?,?,?)',(wid,'waiting_confirmation',json.dumps(steps,ensure_ascii=False),aid,bank.NOW()));risk=bank.risk_level('reserve',payload,c);c.commit()
 except Exception:c.rollback();raise
 finally:c.close()
 action={'id':aid,'kind':'reserve','payload':payload,'token':token,'expires':exp,'risk':risk}
 return {'message':'已完成只读查询并生成任务。请确认预留预算；不会实际下单或推送。','workflow':get(bank,wid),'action':action,'workflow_id':wid}
def finish(bank,wid,aid,token,code='',cancel=False):
 plan=get(bank,wid)
 if not plan['action_id'] or plan['action_id']!=aid:raise ValueError('任务和操作不匹配')
 if plan['status'] not in ('waiting_confirmation','completed'):raise ValueError('任务不可操作')
 if plan['status']=='completed' and cancel:raise ValueError('已完成的任务不可取消')
 res=bank.cancel(aid,token) if cancel else bank.execute(aid,token,code)
 return {'message':res['message'],'workflow':get(bank,wid)}
