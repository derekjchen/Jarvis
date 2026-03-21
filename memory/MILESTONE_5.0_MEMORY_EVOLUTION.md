# Milestone 5.0: 记忆演化系统设计

## 概述

M5.0 是 Memory System 的下一个里程碑，聚焦于记忆的**动态演化**能力。

### 目标

1. **记忆质量评估** - 自动评估记忆的重要性和准确性
2. **遗忘机制** - 自动清理过时或低价值记忆
3. **记忆整合** - 合并相似记忆，消除冲突
4. **记忆演化** - 随时间推移自动更新记忆状态

---

## 设计原则

### 1. 记忆生命周期

```
创建 → 活跃 → 衰退 → 归档/遗忘
  │       │       │        │
  └─ 提取 └─ 检索 └─ 衰减 └─ 清理
```

### 2. 记忆重要性评分

| 因素 | 权重 | 说明 |
|------|------|------|
| 访问频率 | 0.3 | 被检索次数 |
| 时间衰减 | 0.2 | 距离上次访问时间 |
| 安全标记 | 0.3 | 是否包含过敏/禁忌等关键信息 |
| 用户确认 | 0.2 | 用户是否明确确认 |

### 3. 遗忘策略

```python
class ForgetStrategy:
    """遗忘策略配置"""
    
    # 安全信息永不遗忘
    NEVER_FORGET_TYPES = [EntityType.ALLERGY, EntityType.TABOO]
    
    # 事件类记忆保留时间 (天)
    EVENT_RETENTION_DAYS = 365
    
    # 偏好类记忆衰减半衰期 (天)
    PREFERENCE_HALF_LIFE = 90
    
    # 记忆质量阈值
    QUALITY_THRESHOLD = 0.3
```

---

## 核心组件

### 1. MemoryQualityEvaluator (记忆质量评估器)

```python
class MemoryQualityEvaluator:
    """评估记忆质量和重要性"""
    
    def evaluate(self, entity: Entity) -> float:
        """返回 0.0-1.0 的质量分数"""
        score = 0.0
        
        # 安全信息高分
        if entity.type in [EntityType.ALLERGY, EntityType.TABOO]:
            return 1.0
        
        # 访问频率
        score += self._access_score(entity) * 0.3
        
        # 时间衰减
        score += self._time_decay_score(entity) * 0.2
        
        # 来源可信度
        score += self._source_credibility(entity) * 0.2
        
        # 内容完整性
        score += self._content_integrity(entity) * 0.3
        
        return score
```

### 2. MemoryForgetter (记忆遗忘器)

```python
class MemoryForgetter:
    """管理记忆遗忘流程"""
    
    async def should_forget(self, entity: Entity) -> bool:
        """判断是否应该遗忘"""
        # 安全信息永不遗忘
        if entity.type in NEVER_FORGET_TYPES:
            return False
        
        # 质量低于阈值
        quality = await self.evaluator.evaluate(entity)
        if quality < QUALITY_THRESHOLD:
            return True
        
        # 超过保留时间
        age_days = (datetime.now() - entity.created_at).days
        retention = self._get_retention_days(entity.type)
        if age_days > retention:
            return True
        
        return False
```

### 3. MemoryIntegrator (记忆整合器)

```python
class MemoryIntegrator:
    """整合相似记忆，消除冲突"""
    
    async def integrate(self, entities: List[Entity]) -> List[Entity]:
        """整合记忆列表"""
        # 1. 检测相似记忆
        clusters = await self._cluster_similar(entities)
        
        # 2. 合并每个簇
        merged = []
        for cluster in clusters:
            if len(cluster) > 1:
                merged.append(await self._merge_cluster(cluster))
            else:
                merged.append(cluster[0])
        
        # 3. 检测冲突
        conflicts = await self._detect_conflicts(merged)
        
        # 4. 解决冲突
        resolved = await self._resolve_conflicts(merged, conflicts)
        
        return resolved
```

### 4. MemoryEvolver (记忆演化器)

```python
class MemoryEvolver:
    """管理记忆的整体演化流程"""
    
    async def evolve(self) -> EvolutionReport:
        """执行一次记忆演化周期"""
        report = EvolutionReport()
        
        # 1. 加载所有记忆
        entities = await self.store.get_all()
        report.total = len(entities)
        
        # 2. 评估质量
        quality_map = {}
        for entity in entities:
            quality_map[entity.id] = await self.evaluator.evaluate(entity)
        
        # 3. 识别待遗忘
        to_forget = [e for e in entities if await self.forgetter.should_forget(e)]
        report.forgotten = len(to_forget)
        
        # 4. 整合记忆
        remaining = [e for e in entities if e not in to_forget]
        integrated = await self.integrator.integrate(remaining)
        report.integrated = len(remaining) - len(integrated)
        
        # 5. 持久化
        await self.store.replace_all(integrated)
        
        return report
```

---

## 触发机制

### 1. 定时触发

```python
# 每周日凌晨 3 点执行
CRON_SCHEDULE = "0 3 * * 0"

# 或在 Agent 启动时检查
@app.on_event("startup")
async def schedule_evolution():
    scheduler.add_job(evolver.evolve, CronTrigger.from_crontab(CRON_SCHEDULE))
```

### 2. 事件触发

- 记忆数量超过阈值时
- 检索性能下降时
- 用户手动触发时

---

## 数据模型扩展

```python
class Entity(BaseModel):
    # 现有字段...
    
    # M5.0 新增字段
    access_count: int = 0  # 访问次数
    last_accessed_at: Optional[datetime] = None  # 最后访问时间
    quality_score: float = 1.0  # 质量分数
    evolution_history: List[EvolutionEvent] = []  # 演化历史
```

---

## 实现计划

### Phase 1: 质量评估 (1 周)

- [ ] 实现 MemoryQualityEvaluator
- [ ] 添加 access_count 追踪
- [ ] 单元测试

### Phase 2: 遗忘机制 (1 周)

- [ ] 实现 MemoryForgetter
- [ ] 实现遗忘策略配置
- [ ] 安全信息保护测试

### Phase 3: 记忆整合 (1 周)

- [ ] 实现 MemoryIntegrator
- [ ] 相似度计算
- [ ] 冲突检测与解决

### Phase 4: 演化调度 (0.5 周)

- [ ] 实现 MemoryEvolver
- [ ] 定时任务集成
- [ ] 演化报告

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 误删重要记忆 | 安全信息白名单 + 用户确认 |
| 性能影响 | 后台异步执行 + 批量处理 |
| 记忆冲突 | 多数优先 + 最近优先策略 |

---

## 更新日志

- 2026-03-21: 初始设计文档
