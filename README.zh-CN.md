# DoneGate MCP

[English README](README.md)

DoneGate MCP 是一个面向 AI 辅助研发场景的、本地优先的交付控制层。

它解决的问题不是“怎么写代码”，而是“什么时候这项工作才真的算完成”。

## 项目背景

AI 编码工具让代码产出变快了，但交付纪律并不会自动出现。真实仓库里最常见的问题通常是：
- 任务在验证没有完成前就被宣布 done
- 文档是否同步只停留在口头假设
- 规格变了，但历史完成任务没有被可靠 reopen
- 本地 hook、CI、agent 各自维护一套不一致的规则

DoneGate MCP 的目标就是给这些流程加上一层轻量、明确、可复用的“交付门禁”。

## 核心目标

DoneGate MCP 主要想做到：
- 用显式任务状态代替模糊的沟通状态
- 把 verification、doc sync、spec drift 放进同一套模型
- 让人类和 AI agent 使用同一套 done 规则
- 保持本地优先，不依赖托管控制平面
- 能从 CLI、git hooks、CI、Hermes MCP、Codex plugin 一起接入

## DoneGate 的核心规则

一个任务不能被标记为 `done`，除非这些条件同时满足：
- verification status = `passed`
- doc sync status = `synced`
- 所有 `required_doc_ref` 都存在
- 所有 `required_artifact` 都存在
- 任务没有被标记成 `needs_revalidation`

## 给人类的快速上手

### 1. 安装 DoneGate MCP

```bash
git clone https://github.com/thtwz/DoneGate-MCP.git
cd DoneGate-MCP
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[mcp,test]"
```

### 2. 在目标仓库里 bootstrap

进入你想纳管的目标仓库后执行：

```bash
donegate-mcp bootstrap --project-name my-project --repo-root .
```

它会自动完成：
- 初始化 `.donegate-mcp`
- 安装 `pre-commit` / `pre-push`
- 在 linked git worktree 下解析正确的 hooks 路径
- 生成 repo-local onboarding 文件

生成的关键文件包括：
- `.donegate-mcp/env.sh`
- `.donegate-mcp/onboarding/codex.md`
- `.donegate-mcp/onboarding/hermes-mcp.yaml`

### 3. 创建并激活任务

```bash
donegate-mcp --data-root .donegate-mcp --json task create \
  --title "实现当前需求" \
  --spec-ref docs/spec.md

donegate-mcp --data-root .donegate-mcp task activate TASK-0001 --repo-root .
```

### 4. 开发期间使用门禁

```bash
donegate-mcp --data-root .donegate-mcp task start TASK-0001
donegate-mcp --data-root .donegate-mcp task submit TASK-0001
donegate-mcp --data-root .donegate-mcp --json task self-test TASK-0001 --workdir .
donegate-mcp --data-root .donegate-mcp task doc-sync TASK-0001 --result synced --ref docs/plan.md
donegate-mcp --data-root .donegate-mcp --json task done TASK-0001
```

## 给 LLM / Agent 的零上下文接入说明

如果你只把这个仓库的 git 地址给一个大模型，推荐它按下面顺序操作：

### 1. clone 并安装 DoneGate MCP

```bash
git clone https://github.com/thtwz/DoneGate-MCP.git
cd DoneGate-MCP
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[mcp,test]"
```

### 2. 在目标仓库里启用 DoneGate

```bash
donegate-mcp bootstrap --project-name my-project --repo-root .
source .donegate-mcp/env.sh
donegate-mcp --data-root .donegate-mcp --json onboarding --repo-root . --agent codex
```

### 3. 确保当前分支有 active task

如果当前分支还没有任务绑定：

```bash
donegate-mcp --data-root .donegate-mcp --json task list --limit 10
donegate-mcp --data-root .donegate-mcp --json task create \
  --title "Describe the current work" \
  --spec-ref docs/spec.md
donegate-mcp --data-root .donegate-mcp task activate TASK-0001 --repo-root .
```

### 4. 使用所有主要功能

只靠这个仓库地址和 README，大模型就应该能顺着文档接通这些能力：
- CLI
- bootstrap + managed hooks
- branch-scoped active task
- supervision / onboarding JSON
- Hermes MCP
- Codex plugin

推荐模型遵循的操作顺序是：
1. 安装 DoneGate MCP
2. 在目标仓库里运行 `bootstrap`
3. 读取 `onboarding`
4. 确认当前分支有 active task
5. 在 commit / push 前读取 `supervision`
6. 在 `done` 之前记录 verification 和 doc sync

## 主要集成方式

### CLI

最稳定的本地接口还是 CLI：

```bash
donegate-mcp --data-root .donegate-mcp --json dashboard --include-tasks --limit 20
donegate-mcp --data-root .donegate-mcp --json supervision --repo-root .
donegate-mcp --data-root .donegate-mcp --json onboarding --repo-root . --agent codex
```

### Hooks

`pre-commit` 和 `pre-push` 会使用同一套 supervision 状态：
- `pre-commit` 会 block `needs_task`、`task_mismatch`、`needs_revalidation`
- `pre-commit` 会 warn `stale_verification`、`stale_docs`
- `pre-push` 会 block 所有比 `tracked` 更严重的状态

### Hermes MCP

优先使用 bootstrap 后生成的：
- `.donegate-mcp/onboarding/hermes-mcp.yaml`

也可以参考：
- `examples/hermes-mcp-config.yaml`

### Codex Plugin

Codex 接入建议看：
- `.donegate-mcp/onboarding/codex.md`
- `docs/startup-guide.md`

## Supervision 状态

```bash
donegate-mcp --data-root .donegate-mcp --json supervision --repo-root .
```

当前可能看到的状态包括：
- `clean`
- `needs_task`
- `task_mismatch`
- `needs_revalidation`
- `stale_verification`
- `stale_docs`
- `tracked`

如果任务配置了 scope，还会返回：
- `covered_files`
- `uncovered_files`
- `policy.pre_commit`
- `policy.pre_push`

## 建议阅读顺序

如果是人类开发者：
1. 本文档
2. [README.md](README.md)
3. [docs/startup-guide.md](docs/startup-guide.md)

如果是 LLM / agent：
1. [README.md](README.md)
2. `donegate-mcp --json onboarding --repo-root . --agent codex`
3. [docs/startup-guide.md](docs/startup-guide.md)
4. `.donegate-mcp/onboarding/codex.md` 或 `.donegate-mcp/onboarding/hermes-mcp.yaml`

## 其他文档

- [启动指南](docs/startup-guide.md)
- [端到端演示](docs/end-to-end-demo.md)
- [贡献指南](CONTRIBUTING.md)
- [发布检查表](docs/release-checklist.md)

## 许可证

DoneGate MCP 使用 [Apache-2.0](LICENSE) 许可证。
