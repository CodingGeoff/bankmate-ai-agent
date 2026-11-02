import os,sys,tempfile,unittest,json,atexit
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
_testdir=tempfile.TemporaryDirectory(); atexit.register(_testdir.cleanup); os.environ['BANKMATE_DB']=str(Path(_testdir.name)/'all-tests.db'); os.environ.pop('OPENAI_API_KEY',None)
import app,agent_tools
class ToolAgentTests(unittest.TestCase):
 def setUp(self): app.init(True)
 def request_with(self,name,args):
  count=[0]
  def req(base,key,model,messages):
   count[0]+=1
   return {'tool_calls':[{'id':'t1','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]} if count[0]==1 else {'content':'finished'}
  return req
 def test_report_tool(self):
  r,t=agent_tools.run('分析上月账单','https://example.test','key','model',app,self.request_with('get_monthly_report',{})); self.assertEqual(r['report']['count'],13); self.assertEqual(t[0]['tool'],'get_monthly_report')
 def test_prepare_then_confirm(self):
  r,t=agent_tools.run('给王晨转200元','x','k','m',app,self.request_with('prepare_transfer',{'payee_id':3,'amount_fen':20000}));self.assertIn('action',r);self.assertEqual(app.get_state()['account']['balance'],860000);app.execute(r['action']['id'],r['action']['token']);self.assertEqual(app.get_state()['account']['balance'],840000)
 def test_hallucinated_amount_blocked(self):
  r,t=agent_tools.run('给王晨转200元','x','k','m',app,self.request_with('prepare_transfer',{'payee_id':3,'amount_fen':200000}));self.assertNotIn('action',r);self.assertEqual(app.get_state()['account']['balance'],860000)
 def test_ambiguous_payee_blocked(self):
  r,t=agent_tools.run('给林晓转200元','x','k','m',app,self.request_with('prepare_transfer',{'payee_id':1,'amount_fen':20000}));self.assertNotIn('action',r)
 def test_unknown_tool_blocked(self):
  r,t=agent_tools.run('直接转账','x','k','m',app,self.request_with('execute_transfer',{}));self.assertNotIn('action',r);self.assertEqual(app.get_state()['account']['balance'],860000)
 def test_token_generated_for_confirmation(self):
  def req(base,key,model,messages):
   return {'tool_calls':[{'id':'1','type':'function','function':{'name':'prepare_transfer','arguments':'{"payee_id":3,"amount_fen":20000}'}}]}
  r,t=agent_tools.run('给王晨转200元','x','k','m',app,req);self.assertIn('token',r['action'])
