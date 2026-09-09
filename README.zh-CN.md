# DoneGate

[English README](README.md)

DoneGate 是一个面向 AI 辅助研发场景的、本地优先的交付控制层。

它解决的问题不是“怎么写代码”，而是“什么时候这项工作才真的算完成”。

## 0.4.1：多项目隔离与精简上下文

共享 MCP 不绑定默认项目，每次调用传目标工作区的绝对 `repo_root`。
仓库和数据目录归属不一致时直接报错，`init` 不再重置已有任务。
常规工作用 `project_context` 获取当前任务与阻塞摘要；变更工具支持
`compact: true`，无需反复读取完整 dashboard 和任务列表。

验证记录绑定 Git 工作区的代码、spec 和验收条件；相关内容改变后必须
重新验证。自测在目标项目运行，未变化的审查结果可复用。建议性审查
保持非阻塞，纯讨论和只读审查不自动创建交付任务。

CLI：`donegate-mcp --repo-root /绝对/项目路径 --json context`。
详见 [变更记录](CHANGELOG.md) 和 [操作说明](skills/donegate/references/operations.md)。

## 项目背景

AI 编码工具让代码产出变快了，但交付纪律并不会自动出现。真实仓库里最常见的问题通常是：
- 任务在验证没有完成前就被宣布 done
- 文档是否同步只停留在口头假设
- 规格变了，但历史完成任务没有被可靠 reopen
- 本地 hook、CI、agent 各自维护一套不一致的规则

DoneGate 的目标就是给这些流程加上一层轻量、明确、可复用的“交付门禁”。

## 核心目标

DoneGate 主要想做到：
- 用显式任务状态代替模糊的沟通状态
- 把 verification、doc sync、spec drift 放进同一套模型
- 让人类和 AI agent 使用同一套 done 规则
- 保持本地优先，不依赖托管控制平面
- 能从 CLI、git hooks、CI、Hermes MCP、Codex plugin 一起接入
- 用建议型架构审查记录“验收通过但没有真正满足用户需求”的缺口
- 把有价值的审查发现直接拆成可跟踪的后续任务

## DoneGate 的核心规则

一个任务不能被标记为 `done`，除非这些条件同时满足：
- verification status = `passed`
- doc sync status = `synced`
- 所有 `required_doc_ref` 都存在
- 所有 `required_artifact` 都存在
- 任务没有被标记成 `needs_revalidation`

## 给人类的快速上手

### 多项目可视化看板

安装 DoneGate 后，在任意目录启动一个本地服务：

```bash
donegate-mcp ui
# 启动时登记当前仓库，或一次添加多个项目：
donegate-mcp --repo-root /绝对/项目路径 ui
donegate-mcp ui --project /绝对/项目A --project /绝对/项目B --no-open
```

默认打开 `http://127.0.0.1:8765`。也可在页面点击“添加项目”，填写服务所在机器上
已经初始化 DoneGate 的仓库绝对路径；自定义数据目录可一并填写。
登记一次后会保留在用户目录的 `~/.config/donegate/projects.json`（遵循 `XDG_CONFIG_HOME`），
使用 `--registry /路径/projects.json` 可指定独立索引。`--port 8899` 更改端口，
`--no-open` 仅启动服务，Ctrl+C 停止。端口被占用时会明确报错，不启动重复服务。

- 总览同时展示所有已登记项目，点击项目进入进度、功能清单和需求变更页面；详情地址可收藏。
- 功能按需求文档分组，可按状态和文字筛选，展开查看验收协议、证据引用和任务事件。
- 完成率是 **当前已完成任务数 / 纳管任务总数**，不是工时或排期进度；没有任务时不显示百分比。
  验收证据已失效的任务会在页面标注并排除出完成数，读取页面本身不改写任务状态。
- 需求变更显示时间、原因、受影响任务及正文差异。新建任务引用已有需求时保存初始快照，
  `spec refresh --spec-ref /绝对/spec.md --reason '变更原因'` 保存后续版本并使受影响任务进入重验。
  相同正文重复刷新不新增版本；恢复旧正文仍产生新版本。旧版未保存的正文无法追溯，页面明确标注。
  仅修改文件但未执行刷新，不会伪造为已记录的需求变更。
- 页面约每 5 秒读取一次数据，保留筛选和展开状态；单个项目不可用不影响其他项目。
  移除项目仅移除看板索引，任务数据仍在各自 `.donegate-mcp` 中；独立 worktree 单独登记。

页面资源随 Python 包安装，无需 Node 或前端构建。Web 服务与 MCP 是独立进程，
共用 DoneGate 的领域规则和项目数据，关闭 AI 工具后仍可查看。
当前仅监听本机回环地址，用于同一机器的多项目展示，不提供跨电脑数据同步、团队登录或远程托管。

### 1. 安装 DoneGate

```bash
git clone https://github.com/thtwz/DoneGate.git
cd DoneGate
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

## 建议型架构审查

v0.4 新增了 advisory review 层，用来兜住传统 verification 很难发现的问题：功能虽然通过验收，但仍然没有满足真实用户意图。

这一层默认是建议型，不是硬门禁：
- 不阻断 `done`
- 不替代 verification 或 doc sync
- 把架构师视角的发现记录成结构化状态
- 支持把发现一键转成 follow-up task

任务首次进入 `submit` 和 `done` 前会自动留下 advisory review request；重复执行同一个生命周期命令不会产生重复的 pending request：

```bash
donegate-mcp --data-root .donegate-mcp task submit TASK-0001
donegate-mcp --data-root .donegate-mcp --json review list --task-id TASK-0001 --include-findings
```

人类或宿主 LLM 可以把审查结论写回 DoneGate：

```bash
donegate-mcp --data-root .donegate-mcp --json task review TASK-0001 \
  --checkpoint manual \
  --provider manual \
  --summary "流程验收通过了，但高频用户仍然缺少快速路径。" \
  --recommendation proceed_with_followups \
  --finding-json '{"dimension":"outcome_gap","severity":"medium","title":"缺少快速路径","details":"已验收流程对重复使用者来说步骤仍然过多。","recommended_action":"增加快捷流程。","suggested_task_title":"增加快速路径","suggested_task_summary":"减少高频用户完成任务所需步骤。"}'
```

如果这个发现值得落地，就直接拆成任务：

```bash
donegate-mcp --data-root .donegate-mcp --json task create-from-finding FINDING-1234abcd
donegate-mcp --data-root .donegate-mcp --json dashboard --include-tasks
```

已经拆成 follow-up task 的 finding 会从 open advisory 计数里移出，并单独作为 spawned follow-up 统计。

Dashboard 也会列出仍有 pending advisory review 的任务，方便 agent 和人类看到哪些请求还需要宿主侧审查。插件 `Stop` hook 在仍有 pending review 或 open advisory finding 时只输出轻量提醒。

Review run 会同时保留 requested provider 和 completed provider。兼容字段 `provider_id` 仍表示实际完成审查的 provider，`requested_provider_id` 表示最初请求的审查方。

MCP 宿主可以使用同等能力：`task_review`、`review_list`、`review_disposition`、`task_create_from_finding`。在 Codex 里，推荐让 DoneGate skill 读取 pending advisory request，在宿主侧执行架构师视角审查，再把标准化 findings 写回 MCP。

## 给 LLM / Agent 的零上下文接入说明

如果你只把这个仓库的 git 地址给一个大模型，推荐它按下面顺序操作：

### 1. clone 并安装 DoneGate

```bash
git clone https://github.com/thtwz/DoneGate.git
cd DoneGate
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
1. 安装 DoneGate
2. 在目标仓库里运行 `bootstrap`
3. 读取 `onboarding`
4. 确认当前分支有 active task
5. 在 commit / push 前读取 `supervision`
6. 在 `done` 之前记录 verification 和 doc sync
7. 对重要任务检查 advisory review，把已接受的真实需求缺口拆成 follow-up task

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

如果 DoneGate 是以“共享插件”的方式被 Codex 启动，最好让 Codex 进程继承 `.donegate-mcp/env.sh` 导出的环境变量。这个文件会提供 `DONEGATE_MCP_ROOT` 和 `DONEGATE_MCP_REPO_ROOT`，这样共享 MCP 会话才能默认指向被纳管的目标仓库，而不是插件安装目录。

如果宿主进程不能继承这些环境变量，MCP 工具调用时就应该显式传 `repo_root`。

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
- [v0.4.0 发布说明](docs/release-notes-v0.4.0.md)

## 许可证

DoneGate 使用 [Apache-2.0](LICENSE) 许可证。
