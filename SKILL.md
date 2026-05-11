---
name: insights
description: 分析当前 agent（Claude Code / Codex / Gemini CLI / OpenCode）的本地会话记录，生成一份 HTML 使用洞察报告，包含项目领域、互动风格、亮点、摩擦点、改进建议、机会展望。当用户说 "看下我最近用 agent 的情况"、"生成 insights"、"分析我的会话历史"、"我的使用模式"、"agent usage report"、"/insights"、"analyze my sessions"、"使用洞察"、"复盘最近用 AI 的情况" 时使用本 skill。即使用户没明说 "insights" 也要触发：只要请求涉及总结/复盘/分析本机 agent 历史、对话记录、commit 模式、工具使用频率，就用这个。
---

# Insights

> **依赖**：Python 3.8+（内置库即可，无第三方包）。OpenCode 需要 `sqlite3` 模块（标准库自带）。
>
> **首次安装**：在所有 4 个 agent 启用 `/insights` 命令，运行：
> `bash ~/.claude/skills/insights/install/install.sh`
> 这会在 `~/.gemini/commands/`、`~/.config/opencode/commands/`、`~/.codex/prompts/` 各放一个软链。Claude Code 走 `~/.claude/skills/insights/` 自动发现。

生成一份多维度 HTML 使用报告，覆盖：

- **At a glance**：4 个高层观察（亮点 / 摩擦 / 速赢 / 长远）
- **Project areas**：会话按主题聚类
- **Interaction style**：用户如何驱动 agent 的叙述性分析
- **Impressive things**：做得漂亮的工作流
- **Where things go wrong**：反复出现的摩擦模式
- **Suggestions**：CLAUDE.md / AGENTS.md 改进项、可试功能、使用模式
- **On the horizon**：可演进的雄心工作流
- **Charts**：tool / 语言 / friction 分布
- **Fun ending**：一个有趣的尴尬瞬间

## 工作流（5 步）

> **关键原则**：mechanical 部分用 `scripts/insights.py`（确定性、跨 agent 统一），narrative 部分由你（LLM）完成（这是 skill 的核心价值）。不要让脚本去硬编码 narrative。

### Step 1 — 检测 agent + 范围确认

```bash
python3 ~/.claude/skills/insights/scripts/insights.py detect
python3 ~/.claude/skills/insights/scripts/insights.py list-agents
```

`detect` 优先看环境变量（CLAUDECODE / CODEX_HOME / GEMINI_HOME / OPENCODE），否则回退到 "最近活跃的 agent"。如果用户没指定，直接用 `detect` 的结果。

询问用户（或假定合理默认）：
- 时间窗口（默认 60 天）
- 采样数量（默认 ≤ 80 个 session）
- 输出路径（默认 `~/.insights-workspace/<agent>/report.html`）

### Step 2 — 收集 quantitative metadata

```bash
python3 ~/.claude/skills/insights/scripts/insights.py metadata \
  --agent <agent> --days <N> --limit <K> \
  --workdir ~/.insights-workspace/<agent>
```

会把每个 session 的 metadata 写到 `<workdir>/metadata/<session_id>.json`。每个 metadata 包含：`tool_counts`、`languages`、`git_commits`、`input_tokens`、`output_tokens`、`first_prompt`、`duration_minutes`、`user_interruptions`、`tool_errors`、`files_modified` 等。这部分纯机械，瞬间完成。

### Step 3 — 每个 session 提炼 facet（LLM 的工作）

对每个 session，读 transcript：

```bash
python3 ~/.claude/skills/insights/scripts/insights.py transcript \
  --agent <agent> --session <session_id> --max-chars 18000
```

默认 `--mode head_tail` 保留开头 30% + 结尾 70% 的内容，因为**最后几条消息最能反映 outcome 和 satisfaction**。需要全头部时用 `--mode head`，只看结尾用 `--mode tail`。`--max-chars` 是软上限，每个 block 不会被切断（典型超出 < 5%）。

基于 transcript + 该 session 的 metadata，提取一个 facet JSON：

```json
{
  "session_id": "...",
  "underlying_goal": "一句话：用户真正想做什么",
  "goal_categories": {"code_review": 1, "feature_implementation": 1},
  "evidence_quote": "transcript 中一句直接引用，最好是最后一条 assistant 或 user 消息，证明你读了 transcript",
  "outcome": "fully_achieved | mostly_achieved | partially_achieved | not_achieved | unclear_from_transcript",
  "user_satisfaction_counts": {"satisfied": 0, "likely_satisfied": 0, "dissatisfied": 0, "frustrated": 0},
  "claude_helpfulness": "very_helpful | moderately_helpful | unhelpful | mixed",
  "session_type": "single_task | iterative_refinement | exploration | debugging | release_pipeline | review | discussion_consultation | other",
  "friction_counts": {"wrong_approach": 0, "misunderstood_request": 0, "excessive_changes": 0, "buggy_code": 0, "needed_pushback": 0, "ignored_instructions": 0},
  "friction_detail": "一句话描述这次最显著的摩擦（若有）",
  "primary_success": "good_explanations | multi_file_changes | bug_fix | release_ship | refactoring | documentation | none | other",
  "brief_summary": "≤ 2 句话，描述用户要做什么、Claude/agent 做了什么、最终结局"
}
```

保存到 `<workdir>/facets/<session_id>.json`。

**`goal_categories` canonical 集**（只能用这些 label，否则破坏聚合）：`code_review`、`feature_implementation`、`bug_fix`、`refactor`、`documentation_editing`、`architecture_review`、`release_engineering`、`discussion_consultation`、`multi_agent_orchestration`、`debugging`、`exploration`、`skill_creation`、`infra_devops`、`data_analysis`、`ui_design`、`testing`、`migration`、`meeting_minutes`、`email_drafting`、`other`。用 `other` 时再加 `other_label` 写自由文本。

**关键提示**：
- 用 `git_commits > 0` 推断 `release_engineering` 倾向
- 用 `user_interruptions > 0` + transcript 中的 "stop"/"wait" 推断 `wrong_approach` 或 `needed_pushback`
- 用 `tool_errors` + transcript 中的 "fix" 反复 推断 `buggy_code`
- transcript 的最后几条消息最能反映 outcome 和 satisfaction（这就是 `head_tail` 模式存在的理由）
- friction_counts 是**这个 session 经历的摩擦次数**，不是布尔值
- 如果 transcript 看不到 session 结局（被 async agent 切断、context overflow 等），`outcome` 必须填 `unclear_from_transcript`，不要猜
- `evidence_quote` 必填——facet 没有 quote 意味着 LLM 没真读 transcript

**Anti-example**：所有 friction_counts 全为 0 + 空 friction_detail 的 facet 几乎都是 LLM 偷懒。例外：`user_message_count <= 2` 的 warmup session，或 `outcome == fully_achieved` 且 `tool_errors == 0` 且 `user_interruptions == 0` 的顺畅 session。

**并行优化**（仅 Claude Code）：如果你支持 subagent，把每个 session 的 facet 提炼派发给一个 Sonnet subagent 并行处理，能大幅加速。在其他 agent 里串行处理即可。

详细 schema 见 `references/facet_schema.md`。

### Step 4 — 汇总成 report.json（LLM 的核心工作）

读完所有 facets + metadata，合成一个 `report.json`，schema 见 `references/report_schema.md`。建议步骤：

1. **统计 header**：`total_sessions`、`analyzed_sessions`、合计 `messages`、`commits`、`tokens`、`hours`（duration_minutes 总和 / 60）、`date_range`
2. **聚合 stats**：`tool_counts`、`language_counts`、`goal_categories`、`friction_counts` —— 直接把所有 facet/metadata 求和
3. **写 narrative 部分**：基于读到的 facets，写出
   - `at_a_glance`（4 段）
   - `project_areas`（4-6 个领域聚类，每个 session 数 + 一句说明）
   - `interaction_style.narrative`（2-3 段叙述）+ `key_pattern`（一句话核心模式）
   - `what_works.impressive_workflows`（3-4 项）
   - `friction_analysis.categories`（2-3 类，每类带 examples，引用具体 session 的事件）
   - `suggestions.claude_md_additions`（2-4 条具体可粘贴）
   - `suggestions.features_to_try`（2-3 个该 agent 支持的特性，比如 Claude Code 的 Skills/Hooks/MCP；Codex 的 AGENTS.md；Gemini 的 commands；OpenCode 的 plugins）
   - `suggestions.usage_patterns`（2-3 个 prompt 化的工作改进）
   - `on_the_horizon.opportunities`（2-3 个雄心工作流）
   - `fun_ending`（找一个让你 / 用户笑出声的瞬间）

**质量准则**：
- 用具体证据，**不要泛泛而谈**：好的发现引用具体 session 的 first_prompt 或 friction_detail。差的发现是 "user seems efficient"
- 摩擦点要诚实写出 agent 的问题，不要为它开脱
- 建议要可执行：CLAUDE.md 加内容要给原文；features 给安装/启用命令；prompts 给可直接复制粘贴的版本
- 中英都行，但保持一致。如果用户用中文交流，输出中文报告

### Step 5 — 渲染 HTML

```bash
python3 ~/.claude/skills/insights/scripts/insights.py render \
  --data <workdir>/report.json \
  --out <workdir>/report.html
```

最后告诉用户 HTML 路径，并问要不要深入某个 section。

## 支持的 agent

| Agent | 检测 | Session 路径 |
|---|---|---|
| `claude-code` | `CLAUDECODE`/`CLAUDE_CODE_ENTRYPOINT` | `~/.claude/projects/<cwd>/*.jsonl` |
| `codex` | `CODEX_HOME` | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` |
| `gemini` | `GEMINI_CLI`/`GEMINI_HOME` | `~/.gemini/tmp/<proj>/chats/session-*.json` |
| `opencode` | `OPENCODE_HOME` | `~/.local/share/opencode/opencode.db` (SQLite) |

若 detect 错了，让用户用 `--agent <name>` 显式指定。

## 何时**不**用本 skill

- 单次会话总结：直接读会话内容回复就行，不用走 5 步
- 跨用户对比：本 skill 只看本机的本 agent
- 实时监控：本 skill 是离线快照

## 文件结构

```
insights/
├── SKILL.md
├── scripts/
│   ├── insights.py          # CLI 入口
│   ├── common.py            # 共享数据类型 & 工具函数
│   ├── render.py            # HTML 渲染
│   └── adapters/
│       ├── claude_code.py
│       ├── codex.py
│       ├── gemini.py
│       └── opencode.py
└── references/
    ├── facet_schema.md      # 每个 session 的 facet schema
    └── report_schema.md     # 最终 report.json schema
```

## 一些坑

- **不要直接读 OpenCode 的 sqlite**：用 adapter 的 `parse_session`，它会处理 `data` 字段里的 JSON
- **token 计数在不同 agent 含义不同**：Codex 的 `total_token_usage` 是累计，Claude Code 是每条 message 累加。直接相信 adapter 输出即可
- **Gemini session 大部分很短**（很多是 info-only 或 single-prompt）：用 `metadata.user_message_count >= 2` 过滤掉空 session 再做 facet 提炼
- **OpenCode 单库有上千 session**：默认加 `--limit` 防止过载
- **transcript 是 Markdown**：给 LLM 读时不要再 escape；它已经包含截断逻辑
