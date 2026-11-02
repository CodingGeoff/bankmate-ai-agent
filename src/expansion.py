"""Additional six-scenario demo operations. No external financial services."""
import re,datetime,uuid

def init(c,reset=False):
 if reset:c.executescript('DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS holdings; DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS card_applications;')
 c.executescript('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT,risk TEXT,term TEXT);
 CREATE TABLE IF NOT EXISTS holdings(product_id INTEGER PRIMARY KEY,amount INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,item TEXT,budget INTEGER,delivery_date TEXT,status TEXT);
 CREATE TABLE IF NOT EXISTS card_applications(id TEXT PRIMARY KEY,created TEXT,status TEXT);''')
 if not c.execute('SELECT 1 FROM products').fetchone():c.executemany('INSERT INTO products VALUES(?,?,?,?)',[(1,'稳健示例','R2','30天'),(2,'成长示例','R4','90天')])

def parse(text,b):
 if re.search(r'[-－负]\s*\d+(?:\.\d+)?\s*(?:元|块)',text):return {'message':'金额不能为负数，未生成任何操作。'}
 if '识别' in text and ('订阅' in text or '代扣' in text):
  with b.conn() as c: rows=c.execute("SELECT merchant,COUNT(DISTINCT substr(date,1,7)) AS months FROM transactions WHERE category='订阅' GROUP BY merchant HAVING months>=2 ORDER BY merchant").fetchall()
  return {'message':'模拟周期扣费线索（仅提示，不代表已签约）：'+('；'.join(f"{x['merchant']} 连续数据覆盖 {x['months']} 个月" for x in rows) if rows else '暂无')+'。取消前仍需核实协议。'}
 if any(x in text for x in ['年度账单','年报','全年账单']):
  year=datetime.date.today().year
  with b.conn() as c: rows=c.execute("SELECT category,COUNT(*) n,SUM(amount) total FROM transactions WHERE date>=? AND date<=? AND category!='转账' GROUP BY category ORDER BY total DESC",(f'{year}-01-01',f'{year}-12-31')).fetchall()
  return {'message':f'{year} 年模拟账单：'+('；'.join(f"{x['category']} {x['n']}笔 ¥{b.money(x['total'])}" for x in rows) if rows else '暂无消费记录')+'。数据仅供演示。'}
 if '理财' in text or '稳健示例' in text or '成长示例' in text:
  with b.conn() as c:
   products=[dict(x) for x in c.execute('SELECT * FROM products')];holdings=[dict(x) for x in c.execute('SELECT p.name,h.amount FROM holdings h JOIN products p ON p.id=h.product_id')]
  if any(x in text for x in ['风险评估','风险测评']):return {'message':'风险提示：模拟产品R2、R4仅为虚构示例；此处不构成真实客户风险测评或投资建议。请根据真实机构流程完成适当性评估。'}
  if '持仓' in text:return {'message':'模拟理财持仓：'+('；'.join(f"{x['name']} ¥{b.money(x['amount'])}" for x in holdings) if holdings else '暂无持仓')+'。'}
  if any(x in text for x in ['购买','申购','买入','赎回']):
   product=next((x for x in products if x['name'] in text),None);m=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text);amount=b.yuan_fen(m.group(1) if m else None)
   if not product or not amount:return {'message':'请指定模拟产品与金额，例如：申购稳健示例100元，或赎回稳健示例100元。'}
   kind='wealth_sell' if '赎回' in text else 'wealth_buy';op='赎回' if kind=='wealth_sell' else '申购'
   return {'message':f'请核对模拟{op}；产品为虚构、金额不代表投资建议。','action':b.prepare(kind,{'product_id':product['id'],'product':product['name'],'amount_fen':amount,'description':f"模拟{op}：{product['name']}，¥{b.money(amount)}，{product['risk']}。不接入真实市场。"})}
  return {'message':'虚构理财产品，仅供演示，不构成投资建议或真实销售：'+ '；'.join(f"{x['name']} {x['risk']} 参考期限{x['term']}" for x in products)+'。可输入“申购稳健示例100元”或“查看理财持仓”。'}
 if any(x in text for x in ['申请银行卡','申请新卡']):return {'message':'请确认创建模拟申请，不会开立真实账户。','action':b.prepare('card_apply',{'description':'模拟申请一张借记卡；不会开立真实银行卡。'})}
 if any(x in text for x in ['银行卡解锁','解锁银行卡','解除挂失']):return {'message':'请确认模拟解锁，当前演示码不是实际多因子认证。','action':b.prepare('card_unlock',{'description':'模拟解锁尾号4826银行卡。'})}
 if ('限额' in text and ('卡' in text or '交易' in text)):
  m=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text);amount=b.yuan_fen(m.group(1) if m else None)
  if not amount:return {'message':'请提供模拟卡片日限额，例如：银行卡限额调整为2000元。'}
  return {'message':'请确认调整模拟日限额。','action':b.prepare('card_limit',{'amount_fen':amount,'description':f'模拟卡片日限额调整为¥{b.money(amount)}。'})}
 if '生日' in text and any(x in text for x in ['下单计划','订购计划']):
  m=re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})',text);am=re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:元|块)',text)
  try:day=datetime.date(*map(int,m.groups())) if m else None
  except ValueError:day=None
  amount=b.yuan_fen(am.group(1) if am else None)
  if not day or not amount or day-datetime.timedelta(days=2)<datetime.date.today():return {'message':'请提供未来生日和预算，如：2027年12月20日生日订购计划300元。'}
  date=(day-datetime.timedelta(days=2)).isoformat();return {'message':'仅创建本地模拟订购计划，不发送商家，不付款。','action':b.prepare('mock_order',{'amount_fen':amount,'date':date,'description':f'鲜花和蛋糕模拟计划，预算¥{b.money(amount)}，计划日期{date}。不下单、不支付。'})}
 return None

def execute(c,kind,p,acc,b):
 if kind in ('wealth_buy','wealth_sell'):
  amount=p['amount_fen'];product=c.execute('SELECT * FROM products WHERE id=?',(p['product_id'],)).fetchone()
  if not product or type(amount)!=int or not 0<amount<=5000000:raise ValueError('产品或金额无效')
  row=c.execute('SELECT amount FROM holdings WHERE product_id=?',(product['id'],)).fetchone();holding=row['amount'] if row else 0
  if kind=='wealth_buy':
   if acc['balance']-acc['reserved']<amount:raise ValueError('可用余额不足')
   c.execute('UPDATE account SET balance=balance-? WHERE id=1',(amount,));c.execute('INSERT INTO holdings VALUES(?,?) ON CONFLICT(product_id) DO UPDATE SET amount=amount+excluded.amount',(product['id'],amount));op='申购'
  else:
   if holding<amount:raise ValueError('模拟持仓不足')
   c.execute('UPDATE account SET balance=balance+? WHERE id=1',(amount,));c.execute('UPDATE holdings SET amount=amount-? WHERE product_id=?',(amount,product['id']));op='赎回'
  return {'message':f'模拟{op} {product["name"]} ¥{b.money(amount)}，未连接真实理财产品。'}
 if kind=='card_apply':c.execute('INSERT INTO card_applications VALUES(?,?,?)',(uuid.uuid4().hex,b.NOW(),'planned'));return {'message':'已记录模拟卡片申请，不会真实开卡。'}
 if kind=='card_unlock':
  card=c.execute('SELECT status FROM cards WHERE id=1').fetchone()
  if not card or card['status']!='locked':raise ValueError('卡片当前未锁定')
  c.execute("UPDATE cards SET status='active' WHERE id=1");return {'message':'已模拟解锁银行卡。'}
 if kind=='card_limit':
  amount=p['amount_fen']
  if type(amount)!=int or not 0<amount<=5000000:raise ValueError('限额无效')
  c.execute('UPDATE cards SET daily_limit=? WHERE id=1',(amount,));return {'message':f'模拟卡片日限额已调整为 ¥{b.money(amount)}；不会影响真实交易。'}
 if kind=='mock_order':
  c.execute('INSERT INTO orders VALUES(?,?,?,?,?)',(uuid.uuid4().hex,'鲜花和蛋糕',p['amount_fen'],p['date'],'planned'));return {'message':'已保存模拟鲜花蛋糕订购计划；没有实际下单或支付。'}
 raise ValueError('未知操作')
