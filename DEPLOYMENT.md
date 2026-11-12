# 内网部署说明

## 环境要求

- Python 3.10+
- Windows / Linux 均可
- **无需外网连接**（Ollama 本地推理）
- 内存建议 8GB+（7B 模型约需 5GB）

## 步骤一：安装 Ollama

### Windows
1. 从 https://ollama.com/download 下载安装包（需提前在有网的机器上下载）
2. 安装后打开命令行验证：`ollama --version`

### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## 步骤二：拉取模型

```bash
# 在有网的机器上执行一次，之后可离线使用
ollama pull qwen2.5:7b

# 验证模型可用
ollama run qwen2.5:7b "你好"
```

模型文件存储在：
- Windows: `C:\Users\<用户名>\.ollama\models`
- Linux: `/usr/share/ollama/models`

可在内网机器间拷贝此目录实现离线分发。

## 步骤三：安装 Python 依赖

```bash
cd audit-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> 提示：在有网的机器上先 `pip download -r requirements.txt -d ./wheels`，
> 再把 wheels 目录拷到内网机器，用 `pip install --no-index --find-links=./wheels -r requirements.txt` 离线安装。

## 步骤四：配置

```bash
copy .env.example .env
# 编辑 .env，确认 OLLAMA_MODEL 和数据路径正确
```

## 步骤五：启动

```bash
# 确保 Ollama 服务在运行
ollama serve  # 如果还没启动

# 启动应用
python run.py
```

浏览器打开 http://localhost:8501

## 验证离线运行

```bash
# 断开网络后测试
python -c "
import ollama
resp = ollama.chat(model='qwen2.5:7b', messages=[{'role':'user','content':'你好'}])
print(resp['message']['content'][:50])
print('✅ 本地推理正常')
"
```

## 故障排查

| 问题 | 解决 |
|------|------|
| Ollama 连接拒绝 | 确认 `ollama serve` 正在运行 |
| 模型加载慢 | 首次加载需要从磁盘读入内存，后续会快 |
| SQL 生成质量差 | 尝试换 `qwen2.5-coder:7b` 或增大 `temperature=0` |
| 内存不足 | 换 `qwen2.5:3b` 小模型 |

## 性能参考

在 Intel i5-12400 (6核12线程) 上实测：

| 模型 | 加载时间 | 单次生成(约200 token) | Agent 完整循环 |
|------|---------|---------------------|--------------|
| qwen2.5:3b | ~3s | ~15s | ~30s |
| qwen2.5:7b | ~8s | ~40s | ~90s |

建议演示时先用小模型快速跑通，正式展示再切大模型。
