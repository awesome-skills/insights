<div align="center">

**中文** · **[English](README.en.md)**

```
  ██╗███╗   ██╗███████╗██╗ ██████╗ ██╗  ██╗████████╗███████╗
  ██║████╗  ██║██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝██╔════╝
  ██║██╔██╗ ██║███████╗██║██║  ███╗███████║   ██║   ███████╗
  ██║██║╚██╗██║╚════██║██║██║   ██║██╔══██║   ██║   ╚════██║
  ██║██║ ╚████║███████║██║╚██████╔╝██║  ██║   ██║   ███████║
  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
```

### **一个 `/insights` 命令，4 个 coding agent 通用**

读本地 **Claude Code · Codex · Gemini CLI · OpenCode** 的 session 记录 →
生成一份可分享的离线 HTML 使用洞察报告。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)
[![Agents](https://img.shields.io/badge/agents-4-purple.svg)](#-支持的-agent)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-success.svg)](#-依赖)

[**安装**](#-安装) · [**工作原理**](#-工作原理) · [**报告内容**](#-报告里有什么) · [**接入新 agent**](#-扩展接入新-agent)

</div>

---

## ✨ 为什么做这个

不同 coding agent 都留下了大量本地会话记录，但它们的格式、token 语义、
工具事件和命令入口都不一样。直接看原始日志很难回答几个更有用的问题：
我最近主要让 agent 做什么？哪些工作流真的跑通了？哪些失败反复出现？
哪些 repo 指令或 prompt 模式值得固化？

**`insights`** 把这些本地记录统一成同一套离线报告。报告维度采用
Codex-native 的执行视角：指令上下文、工具执行、验证证据、交接质量；
字段命名保持 agent-neutral，所以 **Claude Code / Codex / Gemini CLI / OpenCode**
都能产出同一种报告。

```
┌─────────────────────────────────────────────────────────────┐
│  ~/.claude/projects/    ─┐                                   │
│  ~/.codex/sessions/     ─┤                                   │
│  ~/.gemini/tmp/         ─┼─►  insights  ─►  report.html      │
│  ~/.local/.../          ─┘                  （自包含、离线）  │
│  opencode.db                                                  │
└─────────────────────────────────────────────────────────────┘
```

## ⚡ 快速开始

```bash
git clone https://github.com/awesome-skills/insights.git ~/.claude/skills/insights
bash ~/.claude/skills/insights/install/install.sh
```

安装脚本会自动检测你装了哪几个 agent，然后给每个都放一个 `/insights` 命令。
然后在任意 agent 里输入：

```
/insights
```

跑完后它会告诉你 HTML 文件路径，浏览器打开即可。

常用参数：

```bash
/insights --days 30 --limit 50 --out ~/Desktop/insights.html
```

也可以不用 agent，直接跑 CLI：

```bash
python3 scripts/insights.py metadata --agent codex --days 30 --limit 50
python3 scripts/insights.py render --data report.json --out report.html
```

## 🧭 支持的 agent

| Agent | Session 路径 | 格式 |
|---|---|---|
| 🟪 **Claude Code** | `~/.claude/projects/<encoded-cwd>/*.jsonl` | JSONL |
| 🟦 **Codex** | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | JSONL |
| 🟩 **Gemini CLI** | `~/.gemini/tmp/<project>/chats/session-*.json` | JSON |
| 🟧 **OpenCode** | `~/.local/share/opencode/opencode.db` | SQLite |

4 个 agent 共用一个 `/insights` 命令。Skill 通过环境变量和最近活跃度自动检测
当前是哪个 agent 在调用它。

## 📊 报告里有什么

<table>
<tr>
<td width="50%" valign="top">

### 🔭 At a glance（一句话观察）
四段精简观察：什么在 work、什么在拖你后腿、可以立即做的速赢、未来值得尝试的工作流。

### 🗺️ Project areas（项目领域聚类）
按会话内容聚类成 4-6 个领域 —— 后端重构、多 agent 评审、写文档，每个带 session 数。

### 🎭 Operating style（操作风格）
2-3 段叙述：你如何设定目标、约束范围、监督 agent 执行？先评审再改，还是直接授权实现？

### ⭐ Impressive things you did（亮点）
做得漂亮的工作流，引用具体证据。

</td>
<td width="50%" valign="top">

### 🧱 Where things go wrong（摩擦点）
反复出现的摩擦模式，引用具体 session 例子。诚实写出 agent 哪里做得不好。

### 💡 Suggestions（建议）
可直接复制到 `AGENTS.md` / `CLAUDE.md` / command 文件的 guidance 段落、当前 agent 可尝试的能力、可粘贴的 prompt 模式。

### 🚀 On the horizon（未来工作流）
基于你使用模式推断出的雄心工作流 —— 全自动审查闭环、晨报机器人、spec 驱动开发等。

### 📈 Charts（统计图）
top tools / languages / goal categories / friction patterns 的横向条形图。

</td>
</tr>
</table>

## 🧠 工作原理

机械活给 Python 干（快、确定性、跨 agent 一致），叙述活给 LLM 干
（要上下文、要创造）。中间用 JSON 衔接。

```
   ┌──────────────────────┐
   │  1. discover         │  ←─ adapter 用 glob/sqlite 找 session 文件
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  2. metadata         │  ←─ 提取每个 session 的工具调用次数、token、
   │     （mtime 缓存）    │     commits、first_prompt、错误率等量化指标
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  3. transcript       │  ←─ Markdown 化 + head_tail 截断模式
   │     + facet (LLM)    │     默认保留开头 30% + 结尾 70%，让 LLM 看到结局
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  4. aggregate (LLM)  │  ←─ LLM 综合所有 facet 写叙述性 section
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  5. render           │  ←─ 输出单文件 HTML（CSS 内嵌、无 JS、可离线分享）
   └──────────────────────┘
```

主持的 LLM（你正在用的那个 Claude / GPT / Gemini）负责定性判断：
归纳工作领域、判断指令是否被遵守、评价工具执行和验证证据、写出可执行建议。
skill 的 Python 层负责把 4 个 agent 的机械数据统一到同一套 metadata / facet / report schema。

## 🛠 安装选项

```bash
bash install/install.sh             # 默认：装到所有检测到的 agent
bash install/install.sh --status    # 看当前装在哪
bash install/install.sh --uninstall # 卸载（仅移除本工具管理的入口）
bash install/install.sh --force     # 覆盖已存在的命令文件
bash install/install.sh --dry-run   # 试跑（只打印操作不执行）
```

装完后每个 agent 都会有一个入口指向本 skill（Claude/Gemini 用软链，OpenCode/Codex 用渲染后的命令文件）：

```
~/.claude/skills/insights/                     ← Claude Code（自动发现）
~/.gemini/commands/insights.toml               ← Gemini CLI
~/.config/opencode/commands/insights.md        ← OpenCode
~/.codex/prompts/insights.md                   ← Codex（或 $CODEX_HOME/prompts/insights.md）
```

安装脚本会拒绝写入 **软链父目录**（防被引导写入到 `/etc/` 之类），
也不会覆盖已存在的命令文件，除非你加 `--force`。

## 🟦 Codex 适配

Codex 不是只作为一个 JSONL 数据源接入。`insights` 会解析 Codex rollout 中的
`function_call`、`custom_tool_call`（例如 `apply_patch`）、`web_search_call`、
`event_msg`、MCP tool event、`turn_context` 和 `session_meta`，让报告能看到
模型/推理强度、approval/sandbox、web search、subagent 使用、compaction/rollback、
补丁文件、验证命令和工具错误。Codex 的 reasoning summary 会被当作内部执行上下文，
不会混进用户可见 transcript。

Codex 报告会优先给出这些改进建议：

- 适合写进项目 `AGENTS.md` 的规则：读代码边界、dirty worktree 保护、验证要求、交接格式。
- 适合 Codex 的能力：subagents、本地 code review、web search、MCP、approval modes、`codex exec` 自动化。
- 适合复盘的证据：改了哪些文件、跑了哪些测试、有没有浏览器 smoke、哪些风险没验证。

## 🟨 OpenCode 适配

OpenCode 的会话在本地 SQLite 里，不是 JSONL 文件。`insights` 会只读打开
`~/.local/share/opencode/opencode.db`，解析 message / part 表里的 `text`、`tool`、
`file`、`subtask` 和 `patch` part。这样报告能看到工具调用、失败状态、子任务、
附件图片、触达文件和语言分布。

OpenCode 的 token 统计也单独处理：input 取 `input + cache.read + cache.write` 的峰值，
避免多轮上下文被重复相加；output 按 turn 累加。`metadata` 模式会跳过大块
tool output / file content，只保留统计需要的字段。

安装上，OpenCode 用渲染后的 `~/.config/opencode/commands/insights.md`，里面写入当前
skill 的绝对路径。旧版模板软链会在重新安装时自动迁移成渲染文件。

## 📦 依赖

- **Python 3.8+** —— 仅标准库，零第三方包
- **`sqlite3` 模块** —— CPython 自带，OpenCode 用
- **`pytest`** —— 仅跑测试套件需要

## 🏗 架构

<details>
<summary><b>点开看目录结构</b></summary>

```
insights/
├── SKILL.md                    # LLM 跟着走的 5 步工作流
├── README.md                   # ← 你正在看的（中文）
├── README.en.md                # English version
├── LICENSE                     # MIT
│
├── scripts/
│   ├── insights.py             # CLI：detect / list-agents / discover / metadata / transcript / render
│   ├── common.py               # 共享类型、system-injection 过滤器、tool-input 提取、
│   │                           #   Bash 路径抓取、防 OOM 的 DiscardList
│   ├── render.py               # report.json → 自包含 HTML（CSS 内嵌、无 JS、
│   │                           #   XSS 安全、含打印样式）
│   └── adapters/
│       ├── claude_code.py      # 跳过 subagents/ 目录 + isSidechain 事件、
│       │                       #   恢复 <command-args> 真实输入
│       ├── codex.py            # 跳过 sub-agent rollouts（payload.source.subagent）、
│       │                       #   解析 turn_context/event_msg/MCP/patch/web search
│       ├── gemini.py           # 50MB 文件上限、非 dict 防御、id 一致性
│       └── opencode.py         # 只读 SQLite、tool/file/subtask/patch、peak context tokens
│
├── references/
│   ├── facet_schema.md         # 每个 session 的 facet JSON schema
│   └── report_schema.md        # 最终聚合 report.json 的 schema
│
├── install/
│   ├── install.sh              # 幂等安装/卸载/试跑/状态查询
│   ├── gemini-command.toml     # Gemini CLI 命令（TOML）
│   ├── opencode-command.md     # OpenCode 命令（Markdown frontmatter）
│   └── codex-prompt.md         # Codex prompt（Markdown frontmatter）
│
└── tests/                      # pytest 回归测试，~0.1s 全跑完
    ├── conftest.py             # 路径设置
    ├── test_common.py          # 系统注入过滤、Bash 路径、git 动作
    ├── test_adapters.py        # 每个 agent 一份 fixture + 回归 pin
    └── test_render.py          # XSS、空 section、schema 兼容、TOC 精确性
```

</details>

<details>
<summary><b>本 skill 不做什么</b></summary>

- **不做跨 agent 横向对比。** 4 个 agent 的 token 计数语义不一样（Codex 累计、
  OpenCode 每轮新输入、Claude Code 每条消息累加），所以 `header.tokens`
  只是单 agent 报告里的一个数字，**不构成 leaderboard**。
- **不上传任何数据。** 全程本地。生成的 HTML 不引用任何外部资源（无 CDN、
  无字体、无追踪），所以**离线可读**、可以放进 zip 归档。
- **不做后台调度。** 你想要报告就跑 `/insights`，不主动运行。
- **没有云账号、telemetry、analytics。** 纯标准库 Python，只读你自己的文件。

> ⚠️ **分享前请自查**：HTML 是离线的，但**内容不等于安全**。报告里会嵌入真实
> 的 `first_prompt`、session 摘要、文件路径、工具输出片段，可能包含 API key、
> 客户信息、内部代码片段、私有路径等敏感内容。发给同事 / 发邮件 / 截图发推
> 之前请自己过一遍。需要分享时可考虑先用搜索/替换脱敏。

</details>

## 🔌 扩展接入新 agent

每个 adapter 暴露两个函数：

```python
def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]: ...
def parse_session(path: str, metadata_only: bool = False) -> ParsedSession: ...
```

接入新 agent：

1. 在 `scripts/adapters/your_agent.py` 新建模块
2. 实现这两个函数，返回 `ParsedSession(metadata, messages)`
3. 在 `scripts/insights.py:ADAPTER_MODULES` 注册
4. （可选）在 `common.detect_agent_from_env` 加一个 env-var 探测分支

每个 adapter 大约 150-250 行。4 个现有 adapter 涵盖 JSONL 流式读、
单 JSON 文件、SQLite 三种存储模式，可直接参考。

## 🧪 测试

```bash
pip install pytest
pytest tests/
```

测试覆盖修过的 critical bug：

- Sub-agent rollouts 过滤（Claude Code subagents/ + Codex `payload.source.subagent`）
- 系统注入过滤 —— 严到不放过 wrapper，又不会误吞 `<system> 帮我重构` 这种真用户输入
- Slash command `<command-args>` 内容恢复
- 各 agent token 语义差异（累计 / 每轮 / max-of-cumulative）
- HTML 转义 / XSS 安全
- 空 section / schema shape 兼容
- 损坏 JSON、缺失 DB、非 dict 顶层等边界情况

## 🤝 贡献

欢迎 PR。开 PR 前知道这几点：

- **运行时零第三方依赖**。测试可以用 `pytest`。
- **4 个 adapter 应保持并行能力** —— 加新特性请同步到所有 4 个 + schema 文档。
- **修 bug 时补一个 pytest case**，防止后续 4 个 adapter 行为漂移。

## 📜 License

MIT —— 见 [LICENSE](LICENSE)。

## 🙏 致谢

- **Claude Code** 内置的 `/insights` 命令 —— 给了想法、给了 section 结构、给了视觉标杆。
- 4 种 session 格式分别来自 Anthropic / OpenAI / Google / SST，本 skill
  只是把它们适配到一处。

---

<div align="center">

**如果 `/insights` 帮你看出了一个想改的习惯，给个 ⭐ 支持下。**

</div>
