# astrbot_plugin_bandori

AstrBot 插件 — BanG Dream! 知识库检索。

## 功能

| 命令 | 说明 | 示例 |
|------|------|------|
| `/角色 <名称>` | 查询角色信息 | `/角色 丰川祥子` |
| `/歌曲 <名称>` | 查询歌曲信息 | `/歌曲 -N-E-M-E-S-I-S-` |
| `/乐队 <名称>` | 查询乐队信息 | `/乐队 Ave Mujica` |
| `/随机角色` | 随机一位角色 | `/随机角色` |
| `/随机歌曲` | 随机一首歌曲 | `/随机歌曲` |
| `/萌百搜索 <关键词>` | 全站搜索 | `/萌百搜索 Roselia` |
| `/bandori` | 显示帮助 | `/bandori` |

## 安装

```bash
# 1. 复制插件到 AstrBot 插件目录
cp -r astrbot_plugin_bandori/ <astrbot_root>/data/plugins/

# 2. 将知识库 output/ 目录放到插件可访问的位置
#    方式 A — 环境变量（推荐）
export BANDORI_KB_PATH=/path/to/bandori-knowledge/output

#    方式 B — 放在 AstrBot 项目根目录
cp -r output/ <astrbot_root>/

# 3. 重启 AstrBot 或使用插件管理面板加载
```

## 目录结构

```
astrbot_plugin_bandori/
├── main.py                  # 插件入口，Star 类 & 命令注册
├── metadata.yaml            # 插件元数据
├── README.md                # 本文档
└── services/
    ├── __init__.py
    ├── kb_index.py          # 知识库索引 & 检索引擎
    ├── character.py         # 角色服务
    ├── song.py              # 歌曲服务
    ├── band.py              # 乐队服务
    ├── search.py            # 全局搜索服务
    └── formatter.py         # Markdown 响应格式化
```

## 检索策略

```
用户输入 → 本地知识库（模糊匹配）
              ├── 高置信度 → 详情页
              ├── 中等置信度 → 结果列表
              └── 无结果 → RAG 回退（预留接口）
```

- **本地知识库**: 启动时扫描 `output/` 下所有 `.md` 文件构建索引，毫秒级响应
- **RAG 回退**: `services/*.py` 中各 `_rag_fallback()` 方法预留了 RAG 接入点

## 知识库准备

本插件依赖 [bandori-knowledge](https://github.com/bandori-knowledge) 爬虫构建的知识库。

```bash
# 克隆并爬取
git clone https://github.com/bandori-knowledge/bandori-knowledge.git
cd bandori-knowledge
pip install -r requirements.txt
python crawler.py
```

爬取完成后，`output/` 目录即知识库根目录。

## 配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `BANDORI_KB_PATH` | 知识库 `output/` 目录的绝对路径 | 自动探测 |

## 依赖

- `pyyaml` — YAML frontmatter 解析
- AstrBot 框架（`astrbot.api`）

如果 AstrBot 环境缺少 `pyyaml`，请在 `requirements.txt` 中添加：

```
pyyaml>=6.0
```

## License

MIT
