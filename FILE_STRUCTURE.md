# 文件目录说明

- README.md：项目介绍、架构、启动、测试及安全边界。
- .gitignore：排除数据库、缓存及本地密钥配置。
- src/app.py：HTTP API、SQLite 模拟账户及操作确认。
- src/agent_tools.py：可选大模型工具调用及约束。
- src/provider_router.py：可选多供应商路由。
- src/expansion.py：模拟理财、卡片、订阅和账单扩展。
- src/workflow.py：固定生日任务及状态管理。
- src/static/：HTML、CSS、JavaScript 前端。
- src/tests/：自动化测试。
- src/integrations/plaid_sandbox.py：独立 Plaid 沙箱探针，不连接主账本。
- src/scripts/live_model_probe.py：可选真实模型只读工具探针。
- src/.env.example：环境变量示例，不含真实密钥。
- evidence/：架构图、测试报告和已记录的模型联调证据。

模拟资金和用户数据，不可用于真实金融业务。
