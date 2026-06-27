# 关键词选品工作台前端

这是给运营使用的 Web 前端，当前阶段用于连接本机开发后端。真正迁移到中心服务器时，只需要把 API 地址改成中心服务器地址即可。

## 技术栈

- React
- TypeScript
- Vite
- lucide-react 图标
- 原生 CSS，遵守项目内 Apple-Class 设计规范

## 本地启动

先启动后端：

```powershell
cd F:\database
.\backend\start_api.ps1
```

再启动前端：

```powershell
cd F:\database\frontend
npm.cmd run dev
```

打开：

```text
http://127.0.0.1:8000
```

开发环境账号：

```text
账号：本地创建的账号
密码：本地创建的密码
```

## API 地址

默认 API 地址是：

```text
http://127.0.0.1:8001/api
```

如需改成中心服务器地址，在 `frontend` 目录新建 `.env`：

```text
VITE_API_BASE_URL=http://中心服务器IP:8001/api
```

修改后重新运行：

```powershell
npm.cmd run dev
```

## 构建

```powershell
cd F:\database\frontend
npm.cmd run build
```

构建产物在：

```text
F:\database\frontend\dist
```

## 当前页面

- 登录页：账号密码登录，不依赖邮箱。
- 关键词机会池：支持 `全量词库`、`候选词库`、`核心选品机会`、`上升趋势机会`、`稳定需求机会`、`新词观察`、`低竞争机会`、`高需求谨慎池`、`待人工判断` 九种数据范围。
- 筛选条件：月份、关键词、类目、趋势、候选等级、选品分、搜索量、PPC、SPR。
- 候选清单：表格展示关键词、中文翻译、类目、搜索量、趋势、关键词机会分、PPC、SPR、运营状态。
- 详情抽屉：展示关键词多月变化、核心指标和备注。
- 我的收藏：左侧菜单进入收藏清单，也可以在表格或详情中收藏/取消收藏。
- 横向对比：左侧菜单进入独立模块，按相同关键词跨月份对比搜索量、排名、出现连续性和历史排名参考。
- 禁用词管理：左侧菜单维护品牌词、无关词、风险词、当前业务不适合的词，支持包含匹配/完全匹配和启用/停用。
- 快速禁用：表格行和详情抽屉都可以把当前关键词加入禁用词。
- 运营动作：收藏、状态变更、备注、禁用词维护、导出 Excel。

## 性能策略

- 前端会对相同筛选条件的关键词清单做 5 分钟内存缓存。
- 点击左侧菜单返回已看过的清单时，会优先复用浏览器缓存。
- 点击顶部“刷新”会清除前端缓存并重新请求后端。
- 收藏、状态变更、备注、禁用词新增/启停会自动清除前端缓存。
- 后端优先读取 `keyword_selection_candidates_monthly` 缓存表；如果指定月份/站点没有缓存，才回退实时关键词机会候选视图 `v_mb_product_selection_candidates`。
- 后端返回 `cached` 字段。`cached=false` 时，前端会显示“实时计算，查询较慢”的提示，提醒需要补该月份缓存。

导入新月份或重新计算趋势后，推荐流程是先完成趋势计算和缓存刷新，再让运营使用页面：

```powershell
cd F:\database
python scripts\calculate_trends.py --analysis-month 2026-04 --marketplace UK
```

如果只需要补关键词机会缓存，可以运行：

```powershell
cd F:\database
python scripts\refresh_product_selection_cache.py --analysis-month 2026-04 --marketplace UK
```

## 设计约束

前端必须遵守：

```text
F:\database\docs\12-前端Apple-Class设计规范.md
```

重点是运营效率，不做营销式首页；表格和筛选优先，视觉保持克制、清晰、稳定。
