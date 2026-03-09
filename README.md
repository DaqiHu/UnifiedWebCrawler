# Unified Web Crawler

一个以 `Streamlit + Python` 为入口的个人爬虫工作台。  
当前已接入 `miHoYo 校园招聘` 连接器，用于抓取岗位详情、相似岗位、原始 JSON，并在同一个 Web 页面里完成表格查看、对比分析和导出。

## 当前能力

- 通过岗位 URL 或岗位 ID 抓取 miHoYo 校招岗位
- 自动抓取相似岗位并写入 SQLite
- 保存每次抓取的原始接口快照到 `data/raw/`
- 在 Streamlit 页面中查看：
  - 岗位列表
  - 岗位详情
  - 相似岗位
  - 技能关键词覆盖图
  - 原始 JSON
  - 抓取运行记录
- 支持开发时热重载：修改 Python 文件后，Streamlit 会自动刷新

## 项目结构

```text
.
├─ app.py
├─ requirements.txt
├─ crawler_app/
│  ├─ analysis.py
│  ├─ bootstrap.py
│  ├─ config.py
│  ├─ models.py
│  ├─ service.py
│  ├─ storage.py
│  └─ connectors/
│     ├─ base.py
│     └─ mihoyo_jobs.py
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

### 3. 启动 Web 工作台

```powershell
python -m streamlit run app.py
```

默认地址通常是：

- `http://localhost:8501`

## 页面说明

### 概览

- 总岗位数、城市数、类别数、实习岗位数
- 技能关键词覆盖图
- 城市分布图
- 最近抓取的岗位表格

### 岗位表格

- 查看结构化后的岗位数据

### 岗位详情与对比

- 查看单个岗位的职责、要求、加分项
- 查看该岗位关联的相似岗位
- 多岗位技能矩阵对比

### 原始数据

- 查看岗位原始接口 JSON

### 运行记录

- 查看每次抓取的执行情况和快照路径

## 后续扩展方式

这个项目不强行抽象“通用语义爬虫框架”，只抽象工具层和工作台层。  
如果后续要接入别的企业招聘页或文档站点，建议保持下面的方式：

1. 在 `crawler_app/connectors/` 下新增一个站点专属连接器
2. 返回统一的 `JobRecord` 或站点自己的结构化模型
3. 复用 `storage.py`、`analysis.py` 和 `app.py` 的展示入口

也就是说：

- 站点抓取逻辑按站点定制
- 存储、展示、导出、运行记录统一复用

## 当前默认数据源

- `miHoYo 校园招聘`
- 接口优先：`/v1/job/info`、`/v1/job/list`
- Playwright 兜底：当接口抓取失败时，尝试从页面网络请求中恢复数据
