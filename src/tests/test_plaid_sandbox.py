import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations'))
import plaid_sandbox as p
class PlaidTests(unittest.TestCase):
 def test_blocks_other_endpoint(self):
  with self.assertRaises(p.SandboxError): p.call('/transfer/create',{},'id','secret')
 def test_mocked_full_flow(self):
  calls=[]
  def fake(path,data,c,s):
   calls.append(path)
   if path=='/sandbox/public_token/create': return {'public_token':'public'}
   if path=='/item/public_token/exchange': return {'access_token':'access'}
   if path=='/accounts/get': return {'accounts':[{'name':'Test','type':'depository','balances':{'iso_currency_code':'USD'}}]}
   if path=='/transactions/sync': return {'added':[{'amount':1}], 'has_more':False}
  with patch.object(p,'call',side_effect=fake): result=p.run('id','secret')
  self.assertEqual(result['account_count'],1); self.assertEqual(result['transactions_added_count'],1); self.assertEqual(len(calls),4); self.assertNotIn('access',str(result))
