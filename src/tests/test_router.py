import unittest,os
from unittest.mock import patch
import provider_router,agent_tools
class RouterTests(unittest.TestCase):
 def setUp(self): provider_router._cooldown.clear()
 def test_explicit_optin_only(self):
  with patch.dict(os.environ,{'BANKMATE_PROVIDERS':'ovh,groq','BANKMATE_ALLOW_ANONYMOUS':'0'},clear=True): self.assertEqual(provider_router.configured(),[])
 def test_second_provider_after_failure(self):
  env={'BANKMATE_PROVIDERS':'groq,ovh','GROQ_API_KEY':'secret','GROQ_MODEL':'example','BANKMATE_ALLOW_ANONYMOUS':'1'}
  def run(text,base,key,model,bank):
   if 'groq' in base: raise agent_tools.AgentUnavailable('synthetic')
   return {'message':'demo'},[{'tool':'test'}]
  with patch.dict(os.environ,env,clear=True):
   result,trace,attempts=provider_router.run('测试',None,runner=run);self.assertEqual([x['status'] for x in attempts],['failed','success']);self.assertNotIn('secret',str(attempts))
 def test_failure_and_cooldown(self):
  with patch.dict(os.environ,{'BANKMATE_PROVIDERS':'ovh','BANKMATE_ALLOW_ANONYMOUS':'1'},clear=True):
   def bad(*args):raise agent_tools.AgentUnavailable('x')
   with self.assertRaises(provider_router.RoutingUnavailable):provider_router.run('x',None,runner=bad)
   with self.assertRaises(provider_router.RoutingUnavailable) as ex:provider_router.run('x',None,runner=bad)
   self.assertEqual(ex.exception.attempts[0]['status'],'cooldown')
 def test_negative_amount_is_not_accepted(self):
  import app
  app.init(True)
  r=app.chat('给王晨转-200元');self.assertNotIn('action',r)
