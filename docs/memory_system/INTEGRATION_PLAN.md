# Memory 系统整合计划

> 版本: 1.0
> 更新时间: 2026-03-21

## 一、整合目标

将 M2.1、M3.0、M3.5、M4.0 四个里程碑的功能整合为一个完整可用的记忆系统。

## 二、当前问题诊断

### 2.1 代码结构问题

```
当前状态:
├── memory/
│   ├── memory_manager.py       ← M2.1，被 react_agent 使用
│   ├── preference/             ← M3.0，独立存在，输出未接入
│   ├── events/                 ← M3.0，独立存在，输出未接入
│   ├── memory_v3.py            ← M3.0 接口，未被使用
│   └── unified/                ← M3.5/M4.0，独立存在
│       ├── store.py            ← 未接收其他提取器的输出
│       ├── injector.py         ← 未接入 react_agent
│       └── integration.py      ← 未被调用
```

### 2.2 数据流断链

| 断链位置 | 问题 | 解决方案 |
|---------|------|----------|
| **提取→存储** | preference/events 输出未存入 unified store | 统一提取管道 |
| **存储→检索** | store 空置，无数据可检索 | 确保提取结果存入 |
| **检索→注入** | injector 未接入 react_agent | 集成到 prompt 构建 |
| **LLM提取→存储** | llm_extractor 输出未存入 store | 统一输出管道 |

## 三、整合方案

### 3.1 统一提取管道

```python
class UnifiedExtractor:
    """统一提取入口，整合所有提取器"""
    
    def extract(self, message: str) -> list[Entity]:
        entities = []
        
        # 1. 正则提取（M2.1 + M3.0）
        entities.extend(self._extract_key_info(message))
        entities.extend(self._extract_preferences(message))
        entities.extend(self._extract_events(message))
        
        # 2. LLM 提取（M4.0）- 按需触发
        if self._should_trigger_llm(message):
            entities.extend(await self._extract_with_llm(message))
        
        return entities
```

### 3.2 数据流整合

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedExtractor                             │
│                                                                 │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         │
│   │ KeyInfo     │   │ Preference  │   │ Event       │         │
│   │ Extractor   │   │ Manager     │   │ Tracker     │         │
│   │ (M2.1 正则) │   │ (M3.0)      │   │ (M3.0)      │         │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘         │
│          │                 │                 │                 │
│          └─────────────────┼─────────────────┘                 │
│                            │                                   │
│                            ▼ Entity 列表                        │
│                    ┌─────────────┐                             │
│                    │ LLM         │  ← 按需触发                  │
│                    │ Extractor   │                             │
│                    │ (M4.0)      │                             │
│                    └──────┬──────┘                             │
│                           │                                    │
└───────────────────────────┼────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedEntityStore (M3.5)                    │
│                                                                 │
│   entities.json ─── 持久化所有 Entity                           │
│   relations.json ─── 实体间关系                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DynamicInjector (M3.5)                       │
│                                                                 │
│   检索相关实体 → 格式化 → 注入 System Prompt                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      ReactAgent
```

### 3.3 ReactAgent 集成点

```python
class CoPawAgent:
    def __init__(self, ...):
        # 新增：初始化 MemoryIntegration
        self._setup_memory_integration()
    
    def _setup_memory_integration(self):
        """初始化统一记忆系统"""
        from copaw.agents.memory.unified.integration import MemoryIntegration
        self.memory_integration = MemoryIntegration(WORKING_DIR)
    
    def _build_sys_prompt(self) -> str:
        """构建系统提示，注入记忆"""
        prompt = build_system_prompt_from_working_dir()
        
        # 注入记忆实体
        if self.memory_integration:
            prompt = self.memory_integration.inject_to_prompt_sync(prompt)
        
        return prompt
    
    async def reply(self, msg):
        """处理消息，提取并存储记忆"""
        # 提取并存储记忆
        if self.memory_integration and msg:
            text = msg.get_text_content() if hasattr(msg, 'get_text_content') else str(msg)
            await self.memory_integration.process_message(text)
        
        # 正常处理
        return await super().reply(msg)
```

## 四、实施步骤

### Step 1: 创建统一提取器 (unified/extractor.py)

- [x] 创建 UnifiedExtractor 类
- [x] 整合 KeyInfo、Preference、Event 提取
- [x] 支持 LLM 提取按需触发
- [x] 所有输出转为 Entity 格式

### Step 2: 更新 MemoryIntegration (unified/integration.py)

- [x] 使用 UnifiedExtractor
- [x] 确保所有提取结果存入 Store
- [x] 提供同步/异步接口

### Step 3: 集成到 ReactAgent

- [ ] 更新 react_agent.py 初始化
- [ ] 更新 _build_sys_prompt 注入记忆
- [ ] 更新 reply 方法提取记忆

### Step 4: 端到端测试

- [ ] 测试安全信息提取和注入
- [ ] 测试偏好演化
- [ ] 测试事件追踪
- [ ] 测试跨 Session 记忆

## 五、验收标准

### 5.1 功能验收

| 测试场景 | 输入 | 期望输出 |
|---------|------|----------|
| 安全信息 | "我对花生过敏" | 后续对话 System Prompt 包含此信息 |
| 偏好记录 | "我喜欢蓝色的杯子" | 存储为 Entity，可检索 |
| 偏好变化 | "我现在喜欢绿色的杯子" | 更新偏好，保留历史 |
| 事件追踪 | "明天下午3点开会" | 存储为 Event Entity |
| 项目信息 | "我正在做卫星计算项目" | LLM 提取为 Project Entity |
| 跨对话记忆 | Session A 说偏好，Session B 询问 | 能正确回忆 |

### 5.2 架构验收

- [ ] 所有提取器输出都存入 UnifiedEntityStore
- [ ] DynamicInjector 正确注入到 System Prompt
- [ ] 数据持久化到 JSON 文件
- [ ] 代码架构清晰，模块职责明确

---

*最后更新: 2026-03-21*