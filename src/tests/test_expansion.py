import unittest,datetime
import app,workflow
class ScenarioCoverage(unittest.TestCase):
 def setUp(self):app.init(True)
 def test_wealth_full_flow_and_replay(self):
  a=app.chat('申购稳健示例100元')['action'];self.assertEqual(a['risk'],'red');before=app.get_state()['account']['balance']
  with self.assertRaises(ValueError):app.execute(a['id'],a['token'])
  app.execute(a['id'],a['token'],'246810');app.execute(a['id'],a['token'],'246810');self.assertEqual(app.get_state()['account']['balance'],before-10000)
  b=app.chat('赎回稳健示例50元')['action'];app.execute(b['id'],b['token'],'246810');self.assertIn('50.00',app.chat('查看理财持仓')['message'])
 def test_wealth_reject_insufficient_holding(self):
  a=app.chat('赎回稳健示例100元')['action']
  with self.assertRaisesRegex(ValueError,'持仓不足'):app.execute(a['id'],a['token'],'246810')
 def test_card_application_and_limit(self):
  a=app.chat('申请银行卡')['action'];app.execute(a['id'],a['token']);b=app.chat('银行卡限额调整为100元')['action'];app.execute(b['id'],b['token'])
  a=app.chat('给王晨转200元')['action']
  with self.assertRaisesRegex(ValueError,'限额'):app.execute(a['id'],a['token'])
 def test_unlock_requires_code(self):
  a=app.chat('挂失我的银行卡')['action'];app.execute(a['id'],a['token'],'246810');b=app.chat('解锁银行卡')['action'];app.execute(b['id'],b['token'],'246810');self.assertEqual(app.get_state()['cards'][0]['status'],'active')
 def test_workflow_records_order_atomically(self):
  day=(datetime.date.today()+datetime.timedelta(days=100)).isoformat();w=workflow.create(app,10000,day);a=w['action'];workflow.finish(app,w['workflow_id'],a['id'],a['token'])
  with app.conn() as c:self.assertEqual(c.execute('SELECT count(*) FROM orders').fetchone()[0],1)
 def test_annual_bill(self):self.assertIn('模拟账单',app.chat('年度账单')['message'])
 def test_negative_wealth_rejected(self):self.assertNotIn('action',app.chat('申购稳健示例-100元'))
 def test_subscription_detection_is_read_only(self):self.assertIn('视频会员',app.chat('自动识别订阅')['message'])
 def test_card_locked_prevents_transfer(self):
  a=app.chat('挂失我的银行卡')['action'];app.execute(a['id'],a['token'],'246810');t=app.chat('给王晨转100元')['action']
  with self.assertRaisesRegex(ValueError,'卡片不可用'):app.execute(t['id'],t['token'])
