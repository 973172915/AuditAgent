# AuditAgent · 审计数据分析 Agent

> 自然语言查询银行流水与财务账簿，支持勾稽核对、对手方分析、异常检测。
> 基于 **Ollama (本地推理) + DuckDB (数据计算) + LangGraph (Agent 编排) + Streamlit (界面)**。

## ✨ 核心功能

- 💬 **自然语言查询**：用中文描述审计需求，Agent 自动生成 SQL 并执行
- 🔧 **自动修复**：SQL 执行失败时，Agent 分析错误并自动重试（最多 3 次）
- 🔗 **勾稽核对**：比对银行流水与账簿差异，发现漏记/虚记
- 👤 **对手方分析**：一键统计任意往来单位的交易汇总
- 📋 **全链路审计留痕**：所有操作记录在 audit_log.jsonl，支持完整追溯
- 🔒 **安全护栏**：只允许 SELECT、表名白名单、强制 LIMIT、超时控制
- 📊 **评测体系**：10 个测试用例，自动统计准确率和性能指标

## 🏗️ 架构

```
用户问题 → generate_sql → execute_sql → [成功] → summarize
                              ↓ [失败]
                         fix_sql → execute_sql（循环，最多3次）
```

技术栈：
| 层级 | 技术 |
|------|------|
| LLM 推理 | Ollama + qwen2.5:7b（本地 CPU） |
| 数据计算 | DuckDB（内存级列式数据库） |
| Agent 编排 | LangGraph（状态机 + 条件路由） |
| 数据清洗 | Pandas + Decimal 精度处理 |
| 前端 | Streamlit |
| API | FastAPI |

## 🚀 快速开始

```bash
# 1. 安装 Ollama 并拉取模型
ollama pull qwen2.5:7b

# 2. 安装 Python 依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. 配置
copy .env.example .env

# 4. 启动
python run.py
```

详见 [DEPLOYMENT.md](./DEPLOYMENT.md) 了解内网离线部署方案。

## 📡 API

```bash
# 自然语言查询
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "查9月份金额大于10万的支出"}'

# 勾稽核对
curl -X POST "http://localhost:8000/api/reconciliation?date_start=2024-09-01&date_end=2024-09-30"

# 对手方分析
curl http://localhost:8000/api/counterparty/深圳
```

## 🧪 评测

```bash
python eval/run_eval.py
```

输出示例：
```
▶ TC01: 查9月份所有金额大于10万的支出交易
  ✅ PASS | 5 行 | 重试=0 | 42.3s
...
汇总
  总用例: 10
  通过:   8 (80%)
  平均重试: 0.4
  平均耗时: 51.2s
```

## 📁 目录结构

```
audit-agent/
├── agent/
│   ├── config.py             # 配置管理
│   ├── pipeline/
│   │   ├── graph.py          # LangGraph 状态机
│   │   ├── nodes.py          # 4 个节点（生成/执行/修复/总结）
│   │   └── state.py
│   └── tools/
│       ├── sql_executor.py   # DuckDB 执行器（含安全护栏）
│       ├── data_cleaner.py   # 数据清洗（日期/金额/去重）
│       └── reconciliation.py # 勾稽核对 + 对手方分析
├── app/
│   ├── api/main.py           # FastAPI 接口
│   └── ui/streamlit_app.py   # Web 界面
├── data/
│   ├── bank_statement.csv    # 模拟银行流水（含脏数据）
│   ├── ledger.csv            # 模拟财务账簿
│   └── schema.yaml           # 表结构定义（供 LLM 参考）
├── eval/
│   ├── test_queries.yaml     # 10 个测试用例
│   └── run_eval.py           # 评测脚本
├── logs/
│   └── audit_log.jsonl       # 审计日志（自动生成）
├── config.py
├── requirements.txt
├── Dockerfile
├── DEPLOYMENT.md             # 内网部署说明
├── run.py
└── README.md
```

## 🔒 安全设计

| 措施 | 实现 |
|------|------|
| 只读查询 | 正则拦截非 SELECT 语句 |
| 表名白名单 | 只允许访问预定义视图 |
| 结果限制 | 强制注入 LIMIT，防止全表扫描 |
| 超时控制 | DuckDB query_timeout 设置 |
| 审计日志 | 每步操作写入 JSONL，含时间戳和 session_id |

## 🧩 面试亮点

1. **Text-to-SQL + 自动修复**：展示完整的 Agent 自愈能力
2. **勾稽核对工具**：直接命中审计业务场景，不是纯技术 demo
3. **安全护栏设计**：体现对"执行范围控制"的理解
4. **全链路可追溯**：审计日志满足合规要求
5. **本地离线运行**：完全满足内网部署约束
6. **评测驱动**：用数据说话，不靠嘴说"效果不错"
