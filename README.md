# HallSpan 考场间距排座

在考室网格上按最小曼哈顿距离排座，同试卷套不得四邻相邻，并输出违规与统计。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4900 |
| API | http://localhost:9900 |
| API 文档 | http://localhost:9900/docs |
| Postgres | localhost:5450 |

健康检查：`GET http://localhost:9900/api/health`

## 使用说明

1. 在「考室」「考生」「试卷套」确认基础数据，并在「考室」选择缺考占格策略（占格保留 / 释放）。
2. 在「考生名册」或排座图夹板登记缺考；打开「排座图」点击执行排座（只读页面不会代为生成方案）。
3. 在「违规」查看间距或同卷相邻问题。
4. 在「统计」查看已到 / 缺考 / 未排 / 占格与违规汇总。
5. 在「缺考核对册」（只读）核对已到、缺考、未排；与排座图、违规、统计同属当前有效方案。
6. 在排座图的方案列表中作废旧方案；作废后当前有效指针落到次新方案，各页随之跟新。

缺考占格口径（08 策略，全系统统一）：

- 占格保留（retain）：缺考保留一个空桌、计入占格，不再记入未排；
- 释放（release）：缺考不占格，空出的桌位可继续安排到场考生。


## 开发与测试

```bash
docker compose exec api pytest -q
```
