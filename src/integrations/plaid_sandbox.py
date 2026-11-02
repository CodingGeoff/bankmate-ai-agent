#!/usr/bin/env python3
"""Plaid Sandbox-only read-only integration probe; credentials never printed or persisted."""
import os,sys,json,urllib.request,urllib.error
BASE='https://sandbox.plaid.com'
ALLOWED={'/sandbox/public_token/create','/item/public_token/exchange','/accounts/get','/transactions/sync'}
class SandboxError(Exception): pass
def call(path,data,client_id,secret):
 if path not in ALLOWED: raise SandboxError('仅允许预设的沙箱只读接口')
 payload={'client_id':client_id,'secret':secret,**data}
 req=urllib.request.Request(BASE+path,json.dumps(payload).encode(),{'Content-Type':'application/json','Plaid-Version':'2020-09-14'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=20) as response: return json.load(response)
 except urllib.error.HTTPError as e:
  try: d=json.load(e); code=d.get('error_code','HTTP_ERROR'); rid=d.get('request_id','')
  except Exception: code='HTTP_ERROR';rid=''
  raise SandboxError(f'Plaid 请求失败: {code}, request_id={rid}') from None
 except (urllib.error.URLError,TimeoutError) as e: raise SandboxError('网络请求失败，请检查网络后重试') from None
def run(client_id,secret):
 create=call('/sandbox/public_token/create',{'institution_id':'ins_109508','initial_products':['transactions']},client_id,secret)
 exchange=call('/item/public_token/exchange',{'public_token':create['public_token']},client_id,secret); token=exchange['access_token']
 accounts=call('/accounts/get',{'access_token':token},client_id,secret)
 cursor=None; rows=[]; pages=0
 while True:
  payload={'access_token':token,'count':100}
  if cursor: payload['cursor']=cursor
  data=call('/transactions/sync',payload,client_id,secret); rows+=data.get('added',[]); pages+=1
  if not data.get('has_more') or pages>=10: break
  cursor=data['next_cursor']
 return {'environment':'Plaid Sandbox（第三方测试环境，模拟账户）','account_count':len(accounts.get('accounts',[])),'accounts':[{'name':x.get('name'),'type':x.get('type'),'currency':x.get('balances',{}).get('iso_currency_code')} for x in accounts.get('accounts',[])], 'transactions_added_count':len(rows),'sync_pages':pages,'note':'仅统计测试账户和流水；不显示或保存凭证、访问令牌、账户号码或明细。若流水为空，可能尚未初始化。'}
def main():
 client_id=os.getenv('PLAID_CLIENT_ID'); secret=os.getenv('PLAID_SANDBOX_SECRET')
 if not client_id or not secret:
  print('请在服务端环境变量中设置 PLAID_CLIENT_ID 和 PLAID_SANDBOX_SECRET；请勿粘贴到聊天中。',file=sys.stderr); return 2
 try: print(json.dumps(run(client_id,secret),ensure_ascii=False,indent=2)); return 0
 except (SandboxError,KeyError,ValueError): print('沙箱调用未完成。请核对密钥、产品权限和网络；程序不会切换生产环境。',file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
