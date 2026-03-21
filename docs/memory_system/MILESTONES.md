# Memory 系统里程碑详细设计

> 版本: 1.0
> 更新时间: 2026-03-21

---

## 里程碑依赖关系

```
M2.1 关键信息保护 ✅
       │
       │ 提供 KeyInfo 提取能力
       ▼
M3.0 偏好演化 + 事件追踪 ✅
       │
       │ 提供 Preference/Event 提取能力
       ▼
M3.5 动态检索注入 ⚠️
       │
       │ 提供统一存储和检索注入能力
       ▼
M4.0 LLM 语义提取 ⚠️
       │
       │ 提供复杂语义提取能力
       ▼
完整 Memory 系统
```

---

## M2.1 关键信息保护

### 设计目标

确保关键信息在对话压缩时不丢失。

### 核心问题

```
对话压缩流程:
  长对话 → 摘要 → 继续对话

问题:
  - 摘要可能遗漏关键信息
  - 用户说的"我对花生过敏"可能在摘要中丢失
  - 后续对话中 Agent 不知道这个约束
```

### 解决方案: 两层保护

```
┌─────────────────────────────────────────────────────────────────┐
│                    两层保护机制                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  第1层: 注入关键信息到压缩 prompt                               │
│  ─────────────────────────────                                  │
│  压缩 prompt = 原始 prompt + "\n关键信息:\n" + key_infos        │
│                                                                 │
│  第2层: 验证摘要，缺失时自动增强                                │
│  ─────────────────────────────                                  │
│  if 关键信息 not in 摘要:                                       │
│      摘要 += "\n重要: " + 关键信息                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 提取模式

```python
KEY_INFO_PATTERNS = [
    # 安全相关（最高优先级）
    (r"对(.{1,8}?)过敏", "safety", "allergy"),
    (r"不能吃(.{1,15})", "safety", "constraint"),
    (r"患有(.{1,15})", "safety", "disease"),
    
    # 偏好相关
    (r"我喜欢(.{1,15})", "preference", "like"),
    (r"我不喜欢(.{1,15})", "preference", "dislike"),
    
    # 决策相关
    (r"决定(.{1,30})", "decision", "decision"),
    (r"确定了(.{1,30})", "decision", "decision"),
    
    # 联系方式
    (r"电话[号码]?[是为]?(\d{11})", "contact", "phone"),
    (r"邮箱[是为]?([\w\.]+@[\w\.]+)", "contact", "email"),
]
```

### 实现位置

- `src/copaw/agents/hooks/key_info_extractor.py` - 提取器
- `src/copaw/agents/hooks/memory_compaction.py` - 集成点

### 当前状态

✅ **已完成，已集成**

---

## M3.0 偏好演化 + 事件追踪

### 设计目标

1. 记录偏好变化历史，处理偏好冲突
2. 追踪重要事件和里程碑

### 核心问题

```
场景1: 偏好改变
  Day 1: "我喜欢蓝色的杯子"
  Day 30: "我现在喜欢绿色的杯子"
  
  问题: 系统只记住最新的，丢失了变化历史

场景2: 偏好冲突
  Day 1: "我不喜欢吃辣"
  Day 15: "川菜真好吃"
  
  问题: 两条偏好矛盾，系统不知道如何处理

场景3: 重要事件
  用户: "明天下午3点开会"
  
  问题: 系统没有追踪这个事件
```

### 解决方案

#### 偏好演化

```
┌─────────────────────────────────────────────────────────────────┐
│                    偏好演化系统                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Preference 数据模型:                                           │
│  ───────────────────                                            │
│  - id: 唯一标识                                                 │
│  - topic: 偏好主题（食物、颜色、音乐...）                        │
│  - content: 偏好内容                                            │
│  - sentiment: 情感倾向（like/dislike/neutral）                  │
│  - confidence: 置信度 (0.0-1.0)                                 │
│  - status: 状态（ACTIVE/SUPERSEDED/CONFLICT/DECAYED）           │
│  - previous_values: 历史值变化                                  │
│  - conflicts: 冲突记录                                          │
│                                                                 │
│  更新算法:                                                      │
│  ─────────                                                      │
│  1. 查找同主题的现有偏好                                        │
│  2. 检测是否冲突                                                │
│  3. 根据冲突类型处理:                                           │
│     - 增强: 相同情感 + 相似内容 → 增加置信度                    │
│     - 覆盖: 相同情感 + 不同内容 → 创建新版本，标记旧版本        │
│     - 矛盾: 不同情感 → 记录冲突，等待澄清                       │
│                                                                 │
│  置信度衰减:                                                    │
│  ────────────                                                   │
│  confidence = base_confidence * exp(-decay_rate * days_since)  │
│  衰减率: 每30天衰减10%                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 事件追踪

```
┌─────────────────────────────────────────────────────────────────┐
│                    事件追踪系统                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  KeyEvent 数据模型:                                             │
│  ─────────────────                                              │
│  - id: 唯一标识                                                 │
│  - title: 事件标题                                              │
│  - description: 事件描述                                        │
│  - event_type: 事件类型（MILESTONE/DEADLINE/REMINDER/...）      │
│  - importance: 重要性（CRITICAL/HIGH/MEDIUM/LOW）               │
│  - event_date: 事件日期                                         │
│  - recurrence: 重复类型（NONE/DAILY/WEEKLY/MONTHLY/YEARLY）     │
│                                                                 │
│  日期解析:                                                      │
│  ─────────                                                      │
│  "明天" → 今天 + 1天                                            │
│  "下周三" → 计算下周三的日期                                    │
│  "3月25号" → 解析为具体日期                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 实现位置

```
src/copaw/agents/memory/
├── preference/
│   ├── models.py      # Preference 数据模型
│   ├── manager.py     # PreferenceManager
│   └── decay.py       # 置信度衰减算法
├── events/
│   ├── models.py      # KeyEvent 数据模型
│   └── tracker.py     # EventTracker
└── memory_v3.py       # 统一接口
```

### 当前状态

✅ **已完成，独立模块存在，未与 M3.5 集成**

---

## M3.5 动态检索注入

### 设计目标

修复三层断链，实现完整的 信息提取→存储→检索→注入 链路。

### 核心问题: 三层断链

```
┌─────────────────────────────────────────────────────────────────┐
│                    三层断链问题                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  断链1: 存储层断链                                              │
│  ─────────────────                                              │
│  KeyInfoExtractor 提取的信息 → 摘要文本 → Session 结束后丢失   │
│                                                                 │
│  断链2: 检索层断链                                              │
│  ─────────────────                                              │
│  memory_search 工具 → 搜索 MEMORY.md                           │
│  关键信息在摘要中，不在 MEMORY.md 中！                          │
│                                                                 │
│  断链3: 注入层断链                                              │
│  ─────────────────                                              │
│  Entity-Relation-Scene 模型 → 存在代码 → 未注入 System Prompt  │
│  Agent 看不到实体！                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 解决方案

```
┌─────────────────────────────────────────────────────────────────┐
│                    完整链路                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  提取层                    存储层                    注入层    │
│  ─────────                 ─────────                 ─────────  │
│  KeyInfoExtractor    ───▶  UnifiedStore       ───▶  Injector   │
│  PreferenceManager         entities.json            检索相关   │
│  EventTracker              relations.json           实体注入   │
│         │                       │                     │        │
│         └───────────────────────┴─────────────────────┘        │
│                           │                                     │
│                           ▼                                     │
│                    System Prompt                                │
│                    += 注入内容                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 统一数据模型: Entity

```python
class EntityType(Enum):
    # 安全相关 (最高优先级)
    ALLERGY = "allergy"           # 过敏
    CONSTRAINT = "constraint"     # 禁忌
    
    # 偏好相关
    PREFERENCE = "preference"     # 偏好
    DISLIKE = "dislike"           # 不喜欢
    
    # 决策相关
    DECISION = "decision"         # 决策
    
    # 人际关系
    PERSON = "person"             # 人物
    RELATION = "relation"         # 关系
    
    # 项目相关
    PROJECT = "project"           # 项目
    
    # 事件相关
    EVENT = "event"               # 事件
    MILESTONE = "milestone"       # 里程碑
    
    # 其他
    FACT = "fact"                 # 事实
    OTHER = "other"               # 其他


@dataclass
class Entity:
    id: str                       # 唯一标识
    type: EntityType              # 实体类型
    name: str                     # 实体名称
    content: str                  # 实体内容
    priority: int                 # 优先级 (0-100)
    source: EntitySource          # 来源（REGEX/LLM/MANUAL）
    confidence: float             # 置信度
    attributes: dict              # 额外属性
    created_at: datetime          # 创建时间
    # ...
```

### 核心组件

#### UnifiedEntityStore

```python
class UnifiedEntityStore:
    """统一实体存储"""
    
    def add_entity(entity: Entity) -> str
    def get_entity(entity_id: str) -> Entity
    def get_all_entities() -> list[Entity]
    def get_entities_by_type(entity_type: EntityType) -> list[Entity]
    def get_entities_by_priority(min_priority: int) -> list[Entity]
    def save()  # 持久化到 JSON
```

#### EntityRetriever

```python
class EntityRetriever:
    """实体检索器"""
    
    async def search(query: str, top_k: int) -> list[Entity]
    def get_by_type(entity_type: EntityType) -> list[Entity]
    def get_safety_entities() -> list[Entity]  # 过敏、禁忌等
    def get_important_entities() -> list[Entity]
```

#### DynamicInjector

```python
class DynamicInjector:
    """动态注入器"""
    
    async def inject_to_prompt(
        current_prompt: str,
        query: str = "",
        max_entities: int = 20,
        max_tokens: int = 2000
    ) -> str
```

### 实现位置

```
src/copaw/agents/memory/unified/
├── models.py         # Entity 数据模型
├── store.py          # UnifiedEntityStore
├── retriever.py      # EntityRetriever
├── injector.py       # DynamicInjector
└── integration.py    # MemoryIntegration (统一入口)
```

### 当前状态

⚠️ **已开发，未与 M3.0 集成，未接入 react_agent**

---

## M4.0 LLM 语义提取

### 设计目标

突破正则模式限制，实现复杂语义理解。

### 核心问题: 正则的局限

```
正则能做:
  ✅ 匹配固定模式: "对花生过敏"
  ✅ 提取简单信息: "我喜欢蓝色的杯子"
  ✅ 结构化明确的信息

正则不能做:
  ❌ 理解语义: "我老板叫张三"
  ❌ 处理复杂上下文: "我们用Python做后端"
  ❌ 提取隐含信息: "后端开发完成了80%"
```

### 解决方案: 分层提取

```
┌─────────────────────────────────────────────────────────────────┐
│                    分层提取管道                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  第1层: 快速正则匹配（无成本）                                  │
│  ──────────────────────────────                                 │
│  - 过敏、禁忌、疾病                                             │
│  - 喜欢/不喜欢                                                  │
│  - 决策、日期                                                   │
│  - 电话、邮箱                                                   │
│                                                                 │
│  第2层: LLM 语义提取（有成本，按需触发）                        │
│  ──────────────────────────────                                 │
│  - 项目信息: "我正在做卫星计算项目"                             │
│  - 技术决策: "我们用Python做后端"                               │
│  - 人际关系: "我老板叫张三"                                     │
│  - 复杂偏好: "加班时我喜欢喝咖啡"                               │
│  - 项目进度: "后端开发完成了80%"                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 智能触发策略

```python
class TriggerStrategy:
    """LLM 提取触发策略"""
    
    def should_trigger(message: str) -> tuple[bool, str]:
        """
        触发条件:
        1. 显式标记: "记住..."、"别忘了..."、"重要的..."
        2. 关键词检测: 项目、老板、团队、决定...
        3. 消息长度: 超过阈值（可能包含复杂信息）
        4. 批量触发: 积累 N 条消息后批量处理
        """
```

### LLM 提取类型

```python
class LLMEntityType(Enum):
    PROJECT = "project"              # 项目背景
    TECH_DECISION = "tech_decision"  # 技术决策
    PERSON = "person"                # 人物
    RELATION = "relation"            # 关系
    PREFERENCE = "preference"        # 偏好（含条件偏好）
    EVENT = "event"                  # 事件
    MILESTONE = "milestone"          # 里程碑
    FACT = "fact"                    # 事实
    OTHER = "other"                  # 其他
```

### 实现位置

```
src/copaw/agents/memory/unified/
├── llm_extractor.py   # LLMExtractor
└── v4_integration.py  # V4IntegratedExtractor
```

### 当前状态

⚠️ **已开发，未与 M3.5 的 UnifiedStore 集成**

---

## 整合待办事项

### 必须完成的集成

1. **M3.0 → M3.5**: Preference/Event 转换为 Entity 并存入 Store
2. **M3.5 → react_agent**: MemoryIntegration 接入 react_agent
3. **M4.0 → M3.5**: LLMExtractedEntity 转换为 Entity 并存入 Store
4. **统一入口**: 创建 UnifiedExtractor 整合所有提取器

---

*文档版本: 1.0*
*最后更新: 2026-03-21*