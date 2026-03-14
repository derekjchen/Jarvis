# Bug 排查计划：主 Agent 卡死问题

> 创建时间：2025-03-07
> 关联 Issue：#859

## 问题描述

**症状**：
- 运行一段时间后突然卡死
- CPU 占用 100%
- 前端无响应
- 重启后继续之前的对话会再次卡死

**环境**：
- 主 Agent Co：ECS 宿主机，端口 8088
- 子 Agent：Docker 容器（copaw-dev, copaw-test, copaw-devops）

## 我（Co）需要具备的能力

### 1. 系统诊断能力
- 查看进程状态（ps, top, htop）
- 分析 CPU 使用（top, pidstat）
- 分析内存使用（free, vmstat）
- 查看系统日志（journalctl, dmesg）

### 2. 应用诊断能力
- 查看 CoPaw 日志
- 分析 Python 进程状态
- 使用 py-spy 或类似工具分析 Python 调用栈
- 理解 CoPaw 内部架构

### 3. 协调能力
- 指导 DevAgent 分析代码
- 指导 TestAgent 设计复现方案
- 汇总信息，形成诊断报告

## 子 Agent 任务分配

### DevAgent 任务：代码分析

**目标**：分析可能导致 CPU 100% 的代码路径

**具体任务**：
1. 研究 CoPaw 的消息处理流程
2. 查找可能的死循环或阻塞点
3. 分析 session 加载逻辑（重启后继续对话会卡死）
4. 检查 memory manager 相关代码

**需要的能力**：
- Python 代码阅读
- 理解异步编程
- 理解 LLM 调用流程

### TestAgent 任务：复现方案

**目标**：设计可复现的测试用例

**具体任务**：
1. 分析卡死前的操作模式
2. 设计压力测试脚本
3. 尝试在测试环境复现
4. 记录复现步骤

**需要的能力**：
- 测试设计
- 压力测试
- 日志分析

## 诊断步骤

### 第一步：收集现场信息

当卡死发生时，立即收集：

```bash
# 1. 进程状态
ps aux | grep copaw
top -b -n 1 -p $(pgrep -f copaw)

# 2. 线程状态
cat /proc/$(pgrep -f copaw)/status
cat /proc/$(pgrep -f copaw)/stack

# 3. Python 调用栈（如果安装了 py-spy）
py-spy dump --pid $(pgrep -f copaw)

# 4. 内存状态
cat /proc/$(pgrep -f copaw)/maps | wc -l
```

### 第二步：分析日志

```bash
# 查看最近的日志
tail -100 ~/.copaw/logs/copaw.log

# 查找错误
grep -i error ~/.copaw/logs/*.log
grep -i exception ~/.copaw/logs/*.log
```

### 第三步：Session 分析

```bash
# 检查 session 文件大小
ls -lh ~/.copaw/sessions/

# 检查是否有异常大的 session
find ~/.copaw/sessions -size +1M -ls
```

## 可能的原因假设

1. **Session 文件过大**：加载时内存/处理问题
2. **死循环**：某个条件判断错误
3. **锁竞争**：多线程/异步问题
4. **LLM 调用卡住**：API 超时或响应异常
5. **Memory manager 问题**：Issue #846 提到 "not attached"

## 下一步行动

1. [ ] 安装 py-spy 用于诊断
2. [ ] 配置详细日志级别
3. [ ] DevAgent 分析代码
4. [ ] TestAgent 设计复现方案
5. [ ] 等待下次卡死时收集现场信息

---

*此文档将在排查过程中持续更新*