# Unified Web Crawler

一个以 `Streamlit + Python` 为入口的个人爬虫工作台。  
现在采用“首页路由 + 独立需求页”的结构：`miHoYo 校园招聘`、`ARC Raiders 武器资料` 和 `ARC Raiders 怪物资料` 各自独立页面、独立模型和独立展示逻辑。

## 当前能力

- 首页作为主路由，通过按钮进入独立需求页
- 通过岗位 URL 或岗位 ID 抓取 miHoYo 校招岗位
- 自动抓取相似岗位并写入 SQLite
- 抓取 ARC Raiders wiki 武器页的基础属性、来源和资源循环表
- 抓取 ARC Raiders wiki ARC 敌人页的基础属性、战斗提示、掉落和图鉴条目
- 保存每次抓取的原始接口快照到 `data/raw/`
- 在 Streamlit 页面中查看岗位或武器页的结构化结果、原始 JSON 和运行记录
- 支持开发时热重载：修改 Python 文件后，Streamlit 会自动刷新

## 项目结构

```text
.
├─ app.py
├─ pages/
│  ├─ 1_mihoyo_jobs.py
│  └─ 2_arc_raiders_weapons.py
├─ requirements.txt
├─ crawler_app/
│  ├─ analysis.py
│  ├─ bootstrap.py
│  ├─ sync_arc_raiders_arc.py
│  ├─ sync_arc_raiders_weapons.py
│  ├─ config.py
│  ├─ models.py
│  ├─ pages/
│  │  ├─ home/
│  │  ├─ arc_raiders_arc/
│  │  ├─ mihoyo_jobs/
│  │  └─ arc_raiders_weapons/
│  ├─ service.py
│  ├─ storage.py
│  └─ connectors/
│     ├─ base.py
│     ├─ arc_raiders_arc.py
│     ├─ mihoyo_jobs.py
│     └─ arc_raiders_weapons.py
└─ data/
   ├─ raw/
   └─ exports/
```

## 运行方式

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 预抓取默认样例

```powershell
python -m crawler_app.bootstrap
```

默认样例是：

- `https://jobs.mihoyo.com/#/campus/position/8123`
- `https://arcraiders.wiki/wiki/Kettle`（在 ARC Raiders 页面首次进入时会自动抓取）

### 3. 批量同步 ARC Raiders 全部武器页

```powershell
python -m crawler_app.sync_arc_raiders_weapons
```

默认只抓取缺失页面。若需要强制重抓全部页面：

```powershell
python -m crawler_app.sync_arc_raiders_weapons --include-existing
```

### 4. 启动 Web 工作台

```powershell
python -m streamlit run app.py
```

### 5. 批量同步 ARC Raiders 怪物页

```powershell
python -m crawler_app.sync_arc_raiders_arc
```

默认会从 `ARC` 总览页的 `Variants` 表中发现怪物标题，并只抓取缺失页面。若需要强制重抓已存在页面：

```powershell
python -m crawler_app.sync_arc_raiders_arc --include-existing
```

默认地址通常是：

- `http://localhost:8501`

## 页面说明

### 首页

- 作为主路由，点击按钮进入各个独立需求页

### miHoYo 页面

- 保留岗位概览、关注分析、岗位表格、岗位详情与对比、原始数据、运行记录

### ARC Raiders 武器页面

- 查看武器基础属性
- 支持一键同步 `Category:Weapons` 下的全部武器页，并可选择只抓缺失页面
- 查看来源、Crafting、Upgrading、Repairing、Recycling、价格对比和版本历史
- 查看原始解析 JSON 和运行记录

### ARC Raiders 怪物页面

- 查看怪物威胁等级、护甲、主攻击、弱点与生命值
- 支持一键同步 `ARC` 总览页 `Variants` 表里的全部怪物页，并可选择只抓缺失页面
- 查看战斗提示、掉落、地点、图鉴条目与历史/改动记录
- 查看原始解析 JSON 和运行记录

## 后续扩展方式

这个项目不强行抽象“通用语义爬虫框架”，只抽象工具层和工作台层。  
如果后续要接入别的企业招聘页或文档站点，建议保持下面的方式：

1. 在 `crawler_app/connectors/` 下新增一个站点专属连接器
2. 给该需求建立自己的页面目录，例如 `crawler_app/pages/<feature>/`
3. 如有必要，返回站点自己的结构化模型和存储表，而不是硬塞进已有模型
4. 在首页 `app.py` 和 `pages/` 下新增入口文件，把该需求接入主路由

也就是说：

- 独立需求拆独立页面
- 页面逻辑放在自己的文件夹里管理
- 站点抓取逻辑按站点定制
- 存储、展示、导出、运行记录在壳层统一复用

## 当前默认数据源

- `miHoYo 校园招聘`
- 接口优先：`/v1/job/info`、`/v1/job/list`
- Playwright 兜底：当接口抓取失败时，尝试从页面网络请求中恢复数据

## ARC Raiders 抓取说明

- 页面入口：`https://arcraiders.wiki/wiki/<WeaponName>`
- 当前最佳抓取路径：`https://arcraiders.wiki/w/api.php?action=parse&page=<WeaponName>&prop=text&format=json&formatversion=2`
- 选择 parse API 的原因：只返回正文 HTML，比抓整站壳层稳定，也更贴近 `temp/target.html` 的内容结构
- 已记录限制：站点的 Cargo API 会返回 `permissiondenied`，不能依赖 arbitrary cargo query 直接取表

## ARC Raiders 怪物抓取说明

- 默认样例页面：`https://arcraiders.wiki/wiki/Snitch`
- 标题发现入口：`https://arcraiders.wiki/wiki/ARC` 的 `Variants` 表
- 详情抓取路径：`https://arcraiders.wiki/w/api.php?action=parse&page=<EnemyName>&prop=text&format=json&formatversion=2`
- 之所以不依赖 `Category:ARC` 的 `categorymembers`，是因为该站点当前返回空结果，稳定性不如直接解析 `ARC` 总览页
