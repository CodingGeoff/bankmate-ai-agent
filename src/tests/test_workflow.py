import unittest,datetime
import app,workflow
class WorkflowTests(unittest.TestCase):
 def setUp(self): app.init(True); workflow.init(app); self.day=(datetime.date.today()+datetime.timedelta(days=100)).isoformat()
 def test_completion_idempotent_and_dependencies(self):
  d=workflow.create(app,100000,self.day);self.assertEqual(d['workflow']['status'],'waiting_confirmation');self.assertEqual([x['status'] for x in d['workflow']['steps']],['done','done','waiting_confirmation']);self.assertEqual(app.get_state()['account']['reserved'],0)
  a=d['action'];r=workflow.finish(app,d['workflow_id'],a['id'],a['token']);self.assertEqual(r['workflow']['status'],'completed');workflow.finish(app,d['workflow_id'],a['id'],a['token']);self.assertEqual(app.get_state()['account']['reserved'],100000);self.assertEqual(len(app.get_state()['reminders']),1)
 def test_cancel_no_reserve(self):
  d=workflow.create(app,100000,self.day);a=d['action'];r=workflow.finish(app,d['workflow_id'],a['id'],a['token'],cancel=True);self.assertEqual(r['workflow']['status'],'cancelled');self.assertEqual(app.get_state()['account']['reserved'],0)
 def test_invalid_plan_and_mismatch(self):
  with self.assertRaises(ValueError):workflow.create(app,0,self.day)
  with self.assertRaises(ValueError):workflow.create(app,900000,self.day)
  d=workflow.create(app,100000,self.day)
  with self.assertRaises(ValueError):workflow.finish(app,d['workflow_id'],'wrong',d['action']['token'])
 def test_persisted_across_get(self):
  d=workflow.create(app,100000,self.day);p=workflow.get(app,d['workflow_id']);self.assertEqual(p['steps'][2]['depends_on'],['balance','report']);self.assertNotIn('token',str(p))
 def test_wrong_token_no_side_effect(self):
  d=workflow.create(app,100000,self.day);a=d['action']
  with self.assertRaises(ValueError):workflow.finish(app,d['workflow_id'],a['id'],'wrong')
  self.assertEqual(app.get_state()['account']['reserved'],0);self.assertEqual(workflow.get(app,d['workflow_id'])['status'],'waiting_confirmation')
 def test_expired_action_does_not_advance(self):
  d=workflow.create(app,100000,self.day);a=d['action']
  with app.conn() as c:c.execute("UPDATE actions SET expires='2000-01-01T00:00:00' WHERE id=?",(a['id'],))
  with self.assertRaises(ValueError):workflow.finish(app,d['workflow_id'],a['id'],a['token'])
  self.assertEqual(workflow.get(app,d['workflow_id'])['status'],'waiting_confirmation');self.assertEqual(app.get_state()['account']['reserved'],0)
 def test_atomic_crash_rollback(self):
  from unittest.mock import patch
  d=workflow.create(app,100000,self.day);a=d['action']
  with patch.object(workflow,'sync_action',side_effect=RuntimeError('injected failure')):
   with self.assertRaises(RuntimeError):workflow.finish(app,d['workflow_id'],a['id'],a['token'])
  self.assertEqual(app.get_state()['account']['reserved'],0);self.assertEqual(workflow.get(app,d['workflow_id'])['status'],'waiting_confirmation')
  workflow.finish(app,d['workflow_id'],a['id'],a['token']);self.assertEqual(app.get_state()['account']['reserved'],100000)
 def test_direct_action_updates_workflow(self):
  d=workflow.create(app,100000,self.day);a=d['action'];app.execute(a['id'],a['token']);self.assertEqual(workflow.get(app,d['workflow_id'])['status'],'completed')
