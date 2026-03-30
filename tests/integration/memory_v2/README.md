# Memory V2 测试套件

## 目录结构

```
tests/
├── integration/              # 集成测试
│   └── memory_v2/            # Memory V2 集成测试
│       ├── test_entity_extractor.py    # 实体提取测试
│       ├── test_semantic_analyzer.py   # 语义分析测试
│       ├── test_memory_synthesizer.py  # 记忆合成测试
│       ├── test_semantic_store.py      # 存储测试
│       └── test_memory_v2_e2e.py       # 端到端测试
│
├── e2e/                      # 端到端测试（API级别）
│   └── memory_v2/
│       ├── test_cases/       # 测试用例定义（JSON/YAML）
│       │   ├── entity_extraction.json    # 实体提取用例
│       │   ├── memory_type.json          # 记忆类型用例
│       │   ├── relation_extraction.json  # 关系提取用例
│       │   ├── cross_session.json        # 跨会话用例
│       │   └── edge_cases.json           # 边界情况用例
│       ├── run_tests.py      # 测试执行脚本
│       └── ab_test.py        # A/B 对比测试
│
├── fixtures/                 # 测试数据
│   └── memory_v2/
│       ├── sample_memories.json    # 示例记忆数据
│       └── expected_entities.json  # 预期实体数据
│
└── unit/                     # 单元测试（已存在）
    └── ...
```

## 测试类型说明

### 1. 单元测试 (Unit Tests)
- 测试单个函数/方法
- 快速执行，无外部依赖
- 位置：`tests/unit/` 或 `tests/` 根目录

### 2. 集成测试 (Integration Tests)
- 测试模块间交互
- 可能需要数据库/LLM mock
- 位置：`tests/integration/memory_v2/`

### 3. 端到端测试 (E2E Tests)
- 测试完整 API 流程
- 需要运行的服务实例
- 测试用例数据驱动
- 位置：`tests/e2e/memory_v2/`

## 测试用例管理

### 测试用例格式 (JSON)
```json
{
  "test_id": "T01_PERSON_LOC",
  "category": "entity_extraction",
  "description": "测试人名和地点提取",
  "input": "张伟是我的同事，他在北京工作",
  "expected_entities": [
    {"name": "张伟", "type": "person"},
    {"name": "北京", "type": "location"}
  ],
  "expected_memory_type": null,
  "timeout": 60
}
```

### 运行测试
```bash
# 运行所有 Memory V2 测试
pytest tests/integration/memory_v2/ tests/e2e/memory_v2/ -v

# 运行特定类别测试
pytest tests/integration/memory_v2/test_entity_extractor.py -v

# 运行 E2E 测试
python tests/e2e/memory_v2/run_tests.py --target echo

# A/B 对比测试
python tests/e2e/memory_v2/ab_test.py --agent-a echo --agent-b old_echo
```

## CI/CD 集成

在 `push` 前自动运行测试：
```bash
# pre-commit hook 或 CI pipeline
pytest tests/ -v --tb=short
```