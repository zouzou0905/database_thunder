# 后端 API 说明

这是关键词趋势与关键词机会筛选工作台的 FastAPI 后端。

## 作用

后端负责给未来的 React Web 前端提供 API。

它会连接 PostgreSQL，提供：

```text
账号密码登录
关键词候选词筛选
关键词详情
运营状态
收藏
备注
品牌/禁用词维护
Excel 导出
```

前端不直接连接 PostgreSQL，所有业务操作都通过后端 API 完成。

Metabase 只保留为辅助分析工具，不作为运营主入口。

## 安装依赖

当前开发机示例：

```powershell
cd F:\database
python -m pip install -r requirements.txt
```

迁移到真正中心服务器时，把 `F:\database` 替换为中心服务器上的实际部署目录。

## 启动后端

当前开发机启动：

```powershell
cd F:\database
.\backend\start_api.ps1
```

等价原始命令：

```powershell
cd F:\database
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001 --reload
```

启动后，本机访问：

```text
http://127.0.0.1:8001
```

迁移到真正中心服务器后，运营前端会访问：

```text
http://真正中心服务器IP:8001
```

## 开发测试账号

开发机可以通过脚本创建临时测试账号。账号密码以本地实际创建结果为准，不写入仓库。

```text
账号：本地创建的账号
密码：本地创建的密码
角色：admin
```

注意：测试账号只用于开发验证。迁移到真正中心服务器时必须重新设置管理员账号和密码。

## 已有接口

```text
GET   /api/health

POST  /api/auth/login
GET   /api/auth/me

GET   /api/meta/months
GET   /api/meta/categories

GET   /api/product-selection/candidates
GET   /api/product-selection/candidates/{keyword_id}
PATCH /api/product-selection/candidates/{keyword_id}/state
POST  /api/product-selection/candidates/{keyword_id}/notes

GET   /api/keyword-compare/keywords

GET   /api/exclusions
POST  /api/exclusions
PATCH /api/exclusions/{id}

GET   /api/users
POST  /api/users
PATCH /api/users/{id}

GET   /api/exports/product-selection
```

## 性能策略

后端数据库连接通过 `psycopg_pool.ConnectionPool` 复用，当前连接池上限为 30，覆盖 10 个运营同时使用的常规场景。普通接口连接会设置 `statement_timeout = 30s`，避免慢查询长期占用连接。

关键词机会池接口采用“缓存表优先，实时视图兜底”：

```text
keyword_selection_candidates_monthly   # 主查询来源，适合多人高频使用
v_mb_product_selection_candidates       # 指定月份/站点没有缓存时兜底
```

后端响应会返回 `cached` 字段：

```text
cached=true   使用预计算缓存表，查询速度稳定
cached=false  回退实时视图，页面会提示“实时计算，查询较慢”
```

导入新月份或重新执行趋势计算后，应确保该月份已经生成缓存。`scripts\calculate_trends.py` 默认会刷新关键词机会缓存表和横向对比快照；只有传入 `--skip-cache-refresh` 时才会跳过。

手动补某个月缓存时运行：

```powershell
cd F:\database
python scripts\refresh_product_selection_cache.py --analysis-month 2026-04 --marketplace UK
```

当前性能重点：

```text
PostgreSQL 组合索引支撑筛选和排序
后端强制分页，避免一次性返回全量数据
前端 5 分钟内存缓存减少重复查询
缓存表覆盖所有活跃月份，避免多人使用时回退实时视图
```

FastAPI 启动时不会自动重建缓存。缓存刷新是离线任务，应通过 `calculate_trends.py` 或 `refresh_product_selection_cache.py` 手动执行，避免服务启动时突然触发大规模数据库写入。

## 示例

登录：

```json
{
  "account": "admin",
  "password": "your-password"
}
```

查询关键词候选词：

```text
GET /api/product-selection/candidates?page=1&page_size=50&score_min=85
```

请求需要在 Header 中带上登录返回的 token：

```text
Authorization: Bearer <access_token>
```

## 当前已完成

```text
健康检查
账号密码登录
当前用户
月份元数据
类目元数据
关键词候选词列表
关键词候选词详情
运营状态
收藏
备注
品牌/禁用词维护
用户管理 API
Excel 导出
```

## 下一步

```text
任务触发 API
```
