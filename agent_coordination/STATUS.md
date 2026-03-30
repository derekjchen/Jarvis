# Agent 协调中心

> 最后更新：2026-03-08 14:52 CST
> 主 Agent 负责维护，所有子 Agent 可读取
> 路径: /root/copaw/agent_coordination/

## 当前任务看板

| 任务 | 负责人 | 状态 | 优先级 | 更新时间 |
|------|--------|------|--------|----------|
| A/B 测试环境准备 | 主 Agent | ✅ 完成 | P0 | 14:52 |
| LLM 调用问题诊断 | DevAgent | 🔄 进行中 | P1 | 11:25 |
| A/B 测试执行 | TestAgent | ⏳ 待命 | P1 | 14:52 |
| 仓库同步 + CI | DevOpsAgent | 🔄 进行中 | P2 | 11:25 |

## 关键决策记录

### 2026-03-08

1. **OLD ECHO API Key 修复**: 直接修改容器内包路径的 providers.json
   - 原因: copaw 包 `get_providers_json_path()` 返回包内置路径，而非 `/root/.copaw.secret/`
   - 解决: 修改 `/app/venv/lib/python3.11/site-packages/copaw/providers/providers.json`
2. **A/B 测试 baseline 确认**: OLD ECHO (v0.0.4) 不含 Memory V2 代码，天然是 baseline
3. **实体提取问题**: 待确认是 LLM 问题还是调用问题

## 阻塞项

| 阻塞 | 影响 | 等待 | 更新时间 |
|------|------|------|----------|
| 无 | - | - | 14:52 |

## 协作规则

1. 子 Agent 完成阶段性工作后，更新自己的进度文件
2. 主 Agent 定期汇总更新 STATUS.md
3. 有阻塞或需要决策时，在"阻塞项"中登记
4. 做出决策后，记录到"关键决策记录"

---

## 子 Agent 进度文件

- [DevAgent 进度](./devagent_progress.md)
- [TestAgent 进度](./testagent_progress.md)
- [DevOpsAgent 进度](./devopsagent_progress.md)