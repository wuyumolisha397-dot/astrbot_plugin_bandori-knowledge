# AstrBot BanG Dream! 知识库爬虫

自动递归爬取 [萌娘百科](https://zh.moegirl.org.cn) 所有 **BanG Dream!（邦邦）** 相关页面，导出为 Markdown 文件，可直接导入 [AstrBot](https://github.com/Soulter/AstrBot) 知识库。

---

## 功能特性

- ✅ 基于 MediaWiki API，**无浏览器依赖**（不依赖 Selenium / Playwright）
- ✅ 自动递归遍历分类树（从 `Category:BanG Dream!` 开始）
- ✅ Wiki Markup → Markdown 自动转换（表格、列表、标题、粗斜体等）
- ✅ 自动识别并跟随重定向页面
- ✅ 断点续爬（Ctrl+C 安全中断，下次运行继续）
- ✅ 请求限速（每秒最多 2 次）+ 指数退避重试
- ✅ 大字量页面自动按章节拆分（>5000 字）
- ✅ Windows 文件名非法字符自动处理
- ✅ 自动去重，避免重复下载
- ✅ UTF-8 编码，完整类型注解，PEP 8 规范

## 爬取范围

从 `Category:BanG Dream!` 开始，自动发现以下内容：

- 角色（如 千早爱音、高松灯、户山香澄 等）
- 乐队（MyGO!!!!!、Poppin'Party、Roselia、RAISE A SUILEN 等）
- 歌曲、专辑、Live
- 动画、漫画、游戏
- 世界观、学校
- 所有子分类

## 环境要求

- **Python 3.11+**
- 网络连接（访问 `zh.moegirl.org.cn`）

## 安装

```bash
# 1. 克隆项目（或直接进入项目目录）
cd bandori-knowledge

# 2. 创建虚拟环境（推荐）
python -m venv venv

# 3. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

## 运行

```bash
python crawler.py
```

程序会自动：
1. 从 `Category:BanG Dream!` 开始遍历分类树
2. 获取每个页面的 MediaWiki 源码
3. 转换为干净可读的 Markdown
4. 输出到 `output/` 目录

### 运行示例输出

```
22:15:01  INFO    ============================================================
22:15:01  INFO      AstrBot BanG Dream! 知识库爬虫
22:15:01  INFO      数据源: 萌娘百科 (zh.moegirl.org.cn)
22:15:01  INFO      起始分类: Category:BanG Dream!
22:15:01  INFO    ============================================================
22:15:02  INFO    加载缓存: 0 个已完成页面, 0 个已访问分类
22:15:02  INFO    开始爬取...
22:15:03  INFO    📁 正在探索分类: Category:BanG Dream!
22:15:04  INFO      ├─ 发现 12 个子分类
22:15:04  INFO      ├─ 发现 35 个页面
22:15:05  INFO      正在抓取: 千早爱音
22:15:06  INFO      ✓ 成功: 千早爱音 (1 文件)
...
```

### 中断与续爬

按 `Ctrl+C` 安全中断，进度自动保存到 `cache/` 目录。再次运行 `python crawler.py` 即可从中断处继续。

## 项目结构

```
bandori-knowledge/
├── crawler.py          # 主入口，爬取调度逻辑
├── parser.py           # Wiki Markup → Markdown 转换器
├── exporter.py         # Markdown 文件导出（含章节拆分）
├── utils.py            # 工具函数（日志、HTTP、限速、统计）
├── config.py           # 全局配置
├── requirements.txt    # Python 依赖
├── README.md           # 本文件
├── output/             # 生成的 Markdown 文件
│   ├── 千早爱音.md
│   ├── 高松灯.md
│   ├── MyGO!!!!!.md
│   └── ...
└── cache/              # 断点续爬缓存
    ├── completed_pages.txt
    ├── visited_categories.txt
    └── progress.log
```

## 导入 AstrBot

1. 将 `output/` 目录下的所有 `.md` 文件复制到 AstrBot 的知识库目录
2. 在 AstrBot 中启用知识库功能
3. 之后在对话中向 Bot 询问 BanG Dream! 相关内容即可自动检索

```bash
# 示例：复制到 AstrBot 知识库
cp output/*.md /path/to/astrbot/data/knowledge/
```

## 更新知识库

当萌娘百科上的 BanG Dream! 内容更新后，重新运行爬虫即可：

```bash
# 增量更新（利用缓存，只爬取新页面）
python crawler.py

# 完全重新爬取
rm -rf cache/ output/
python crawler.py
```

## 配置说明

编辑 `config.py` 可调整以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ROOT_CATEGORY` | `Category:BanG Dream!` | 起始分类 |
| `REQUESTS_PER_SECOND` | `2.0` | 请求频率限制 |
| `MAX_RETRIES` | `5` | 最大重试次数 |
| `BACKOFF_MAX` | `120.0` | 退避最大等待秒数 |
| `MAX_WORDS_PER_FILE` | `5000` | 单文件最大字数（超过则拆分） |
| `API_LIMIT` | `500` | 每次 API 返回的最大条目数 |
| `MOEGIRL_COOKIE` | 空 | 萌娘百科登录会话 Cookie；匿名 API 被拒绝时必须设置 |

## 技术栈

- **HTTP**: `requests` + `urllib3`（连接复用、自动重试）
- **解析**: 纯正则表达式 Wiki Markup → Markdown 转换
- **并发**: 单线程顺序请求（遵守 API 限速 + 断点续爬友好）
- **数据源**: [MediaWiki API](https://zh.moegirl.org.cn/api.php)

## 注意事项

- 请遵守萌娘百科的 API 使用规范，默认限速为 2 req/s
- 若日志出现 `action-notallowed - Unauthorized API call`，请先登录萌娘百科，复制该站请求头中的完整 `Cookie`，然后运行：

  ```powershell
  $env:MOEGIRL_COOKIE = '你的 Cookie'
  python crawler.py
  ```

  Cookie 属于敏感凭据，不要写入代码、日志或提交到 GitHub。修复后的爬虫会在未授权时返回非零退出码，也不会再把失败分类缓存为“已完成”。
- 生成的内容仅供个人学习和 AstrBot 知识库使用
- 图片不会被下载
- 部分复杂模板可能无法完美解析，但正文内容会被保留

## License

MIT
