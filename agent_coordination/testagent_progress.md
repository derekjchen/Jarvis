# TestAgent 进度

> 最后更新：2026-03-08 12:32 CST (主 Agent 记录)

## 当前任务

**任务**: A/B 测试准备工作

## 进度

| 准备项 | 状态 | 备注 |
|--------|------|------|
| 测试用例集确认 | ✅ 已完成 | 5个JSON文件，22+测试用例 |
| OLD ECHO 方案 | ✅ 已明确 | 见下方方案 |
| 并行测试方案 | ⏸️ 待设计 | |
| 结果报告格式 | ⏸️ 待设计 | |

## 测试用例详情

已确认的测试用例文件（位于 `/root/copaw/tests/e2e/memory_v2/test_cases/`）：
1. `entity_extraction.json` - 实体提取（人名、地点、项目、技术、日期、概念、组织）
2. `memory_type.json` - 记忆类型测试
3. `relation_extraction.json` - 关系提取测试
4. `cross_session.json` - 跨会话测试
5. `edge_cases.json` - 边界情况测试

## OLD ECHO 方案（禁用 Memory V2）

**方法**：修改 MemoryManager 初始化参数

在 `/root/copaw/src/copaw/app/runner/runner.py` 中：
```python
self.memory_manager = MemoryManager(
    ...
    enable_v2=False,  # 添加此参数禁用 Memory V2
)
```

**或**通过配置文件控制（需添加配置项支持）

## 待决策事项

- 准备完成后，等待 Derek 决定何时开始执行测试

## 阻塞

- 无

## 历史记录

- 2026-03-08 11:25: 开始准备工作
- 2026-03-08 12:29: 测试用例集已确认
- 2026-03-08 12:32: OLD ECHO 方案已明确