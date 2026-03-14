# 开发环境架构

## 资源配置

| 环境 | 位置 | 端口 | 资源 |
|------|------|------|------|
| 生产 | ECS 宿主机 | 8088 | 共享 |
| 开发 | Docker 容器 | 8089 | 1CPU/1GB |
| 测试目标 | Docker 容器 | 8090 | 1CPU/1GB |
| TestAgent | Docker 容器 | 8091 | 1CPU/1GB |
| Wiki | Docker 容器 | 8082 | 0.5CPU/512MB |

## Git 仓库布局

```
/root/copaw/                    # Git 仓库（宿主机）
├── .git/                       # Git 目录
├── src/                        # 源代码
│   └── copaw/
│       └── app/runner/session.py  # Session 继承功能
├── tests/                      # 测试代码
└── ...                         # 其他文件

挂载到 DevAgent 容器：
/root/copaw → /app/repo
```

## 分支策略

```
Fork 仓库 (derekjchen/CoPaw)
├── main              # 与官方同步
├── derek/main        # Derek 的主分支（含自定义改动）
├── derek/session     # Session 继承功能
├── derek/memory      # 记忆系统增强
└── feature/xxx       # 新功能分支
```

## 仓库同步流程

```
1. DevAgent 每小时检查官方仓库更新
   git fetch origin

2. 检查是否有新提交
   git log HEAD..origin/main --oneline

3. 如果有更新，执行 rebase
   git checkout main
   git rebase origin/main
   git checkout derek/main
   git rebase main

4. 解决冲突（如有）
   - 通知 Co
   - Co 请 Derek 决策

5. 推送到 Fork
   git push fork derek/main
```

---

*最后更新: 2025-03-06*
