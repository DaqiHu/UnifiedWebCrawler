# Unified Web Crawler

一个以 `Streamlit + Python` 为入口的个人爬虫工作台。  
现在采用“首页路由 + 独立需求页”的结构：`miHoYo 校园招聘` 和 `ARC Raiders 武器资料` 各自独立页面、独立模型和独立展示逻辑。

## 当前能力

- 首页作为主路由，通过按钮进入独立需求页
- 通过岗位 URL 或岗位 ID 抓取 miHoYo 校招岗位
- 自动抓取相似岗位并写入 SQLite
- 抓取 ARC Raiders wiki 武器页的基础属性、来源和资源循环表
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
│  ├─ config.py
│  ├─ models.py
│  ├─ pages/
│  │  ├─ home/
│  │  ├─ mihoyo_jobs/
│  │  └─ arc_raiders_weapons/
│  ├─ service.py
│  ├─ storage.py
│  └─ connectors/
│     ├─ base.py
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

### 3. 启动 Web 工作台

```powershell
python -m streamlit run app.py
```

默认地址通常是：

- `http://localhost:8501`

## 页面说明

### 首页

- 作为主路由，点击按钮进入各个独立需求页

### miHoYo 页面

- 保留岗位概览、关注分析、岗位表格、岗位详情与对比、原始数据、运行记录

### ARC Raiders 页面

- 查看武器基础属性
- 查看来源、Crafting、Upgrading、Repairing、Recycling、价格对比和版本历史
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
