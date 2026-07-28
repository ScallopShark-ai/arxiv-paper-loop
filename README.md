# ArXiv Paper Loop

自动化论文收集与分析系统，每日从 arXiv 筛选相关论文并生成分析报告。

## 功能

- **自动筛选**: 基于关键词和类别从 arXiv 筛选相关论文
- **多维分析**: 三视角深度分析（综合评价、理论推导、实验分析）
- **自动发布**: 整合报告并发布到 Notion

## 架构

```
┌─────────────┐     ┌─────────────┐
│  analyze_pri │────▶│  papers/    │
│  (论文筛选)   │     │  (PDF文件)  │
└─────────────┘     └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ analyze_acc │ │ theory_deri │ │ experiment  │
    │  (综合评价)  │ │ (理论推导)  │ │   (实验)    │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                   ┌─────────────────┐
                   │ summarize_and   │
                   │    publish      │
                   │ (整合发布Notion)│
                   └─────────────────┘
```

## Agents

| Agent | 功能 | 模型 |
|-------|------|------|
| `analyze_pri` | 搜索并筛选论文，下载PDF | gpt-5.5 |
| `analyze_acc` | 综合评价论文质量、方法论 | gpt-5.6-sol |
| `theory_deri` | 提取理论推导、定理、证明 | claude-opus-5 |
| `experiment_analyze` | 分析实验设置、数据集、结果 | claude-opus-5 |
| `summarize_and_publish` | 整合报告并发布到Notion | claude-opus-5 |

## 筛选关键词

- Reinforcement Learning
- RLHF / Preference Learning
- LLM Agent / Autonomous Agent
- Game AI / Self-play
- Reward Learning / Reward Model

## 类别范围

- cs.LG (Machine Learning)
- cs.AI (Artificial Intelligence)
- cs.CL (Computation and Language)
- cs.NE (Neural and Evolutionary Computing)

## 使用方法

### 自动运行

每天北京时间 16:00 自动运行（周二至周六）

### 手动触发

```bash
# 标准模式：搜索昨天的论文
gh workflow run arxiv_paper_loop.yml

# 指定日期范围
gh workflow run arxiv_paper_loop.yml \
  -f start_date=2026-07-16 \
  -f end_date=2026-07-24

# 直接下载指定论文（测试用）
gh workflow run arxiv_paper_loop.yml \
  -f paper_ids="2607.12345,2607.12346"

# 保存中间文件（调试用）
gh workflow run arxiv_paper_loop.yml \
  -f save_temp=true
```

## 配置

### GitHub Secrets

| Secret | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API密钥 |
| `ANTHROPIC_BASE_URL` | API代理地址（可选） |
| `NOTION_API_KEY` | Notion API密钥 |
| `NOTION_PAGE_ID` | 目标页面ID |

### Agent配置

Agent配置文件位于 `.claude/agents/*.toml`，可调整：
- 模型选择
- 筛选标准
- 输出格式

## Skills

| Skill | 功能 |
|-------|------|
| `arxiv-connect` | arXiv API搜索与下载 |
| `pdf-reader` | PDF解析（文本、公式、图表） |
| `notion-connector` | Notion API发布 |

## 输出

- **Notion日报**: 每日论文分析报告
- **GitHub Artifacts**: 中间文件（可选保存）

## 目录结构

```
arxiv_paper_loop/
├── .claude/
│   ├── agents/           # Agent配置
│   └── skills/           # Skills模块
├── .github/
│   └── workflows/        # GitHub Actions工作流
├── scripts/
│   └── run_agent.py      # 主运行脚本
└── temp/                 # 临时文件（调试）
```

## 状态

🧪 **试验阶段** - 稳定运行测试中

## Roadmap

### v1.1 - 成本优化
- [ ] 根据预算自动配置大模型组合
- [ ] 动态选择模型（复杂任务用强模型，简单任务用快模型）
- [ ] 成本统计与预算预警

### v1.2 - 自动修复
- [ ] Doctor Agent：自动检测并修复workflow错误
- [ ] 失败重试机制优化
- [ ] 自动补齐缺失的分析结果

### v1.3 - 功能增强
- [ ] 支持更多论文来源（OpenReview, PMLR等）
- [ ] 论文去重与追踪（避免重复分析）
- [ ] 历史论文库管理与检索
- [ ] 自定义筛选条件配置界面

### v1.4 - 输出渠道
- [ ] 静态网站（GitHub Pages）展示论文报告
- [ ] 支持搜索、分类、日期筛选
- [ ] 保留Notion作为备选/备份渠道

### v2.0 - 智能化
- [ ] 根据用户反馈优化筛选标准
- [ ] 论文推荐系统（基于阅读历史）
- [ ] 多语言报告支持

### v3.0 - 配置中心
- [ ] 可交互配置界面
  - 自定义运行时间（cron表达式）
  - 自定义筛选关键词
  - 模型选择与推荐组合（基于任务复杂度/预算）
  - API网关配置与延迟测试
- [ ] 配置预览与效果预估
- [ ] 多配置方案管理

## License

MIT