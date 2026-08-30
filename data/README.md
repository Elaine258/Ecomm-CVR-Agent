# TheLook eCommerce 数据集

**来源**: Google BigQuery 公开数据集 `bigquery-public-data.thelook_ecommerce`
**数据性质**: TheLook 是 Looker 团队开发的虚拟服装电商网站，所有数据均为**合成数据**（非真实交易），用于产品探索、测试和评估。
**时间范围**: 2019 年 - 2024 年
**下载日期**: 2026-08-12
**获取渠道**: Kaggle 镜像（chiraggivan82/ecommerce-bigquery，与 BigQuery 原版一致）

## 文件清单

| 文件 | 行数 | 大小 | 说明 |
|------|------|------|------|
| users_old.csv | 100,001 | 16MB | 用户注册信息（姓名、年龄、性别、城市、国家、流量来源等） |
| orders.csv | 125,084 | 9.3MB | 订单（订单 ID、用户、状态、时间戳、商品数量） |
| order_items.csv | 181,756 | 19MB | 订单明细（产品、库存项、状态、售价） |
| products_old.csv | 29,121 | 4.2MB | 产品目录（品类、品牌、成本、零售价、SKU） |
| inventory_items_old.csv | 490,408 | 89MB | 库存记录（产品、成本、品类、配送中心） |
| distribution_centers.csv | 10 | 368B | 美国 10 个配送中心 |
| events_old.csv | 2,432,813 | 369MB | 网站事件日志（浏览、加购、购买等） |
| start to end purchase events.csv | 181,756 | 19MB | 购买会话数据（从首次访问到完成购买的完整路径） |

## 表结构（ER 关系）

```
users ────< orders ────< order_items >──── products
              │                │
              │                └─────── inventory_items >──── distribution_centers
              │
events（用户浏览行为，独立事件流）
```

## 7 张核心表字段说明

### users（用户）
id, first_name, last_name, email, age, gender, state, street_address, postal_code, city, country, latitude, longitude, traffic_source, created_at

### orders（订单）
order_id, user_id, status, gender, created_at, returned_at, shipped_at, delivered_at, num_of_item

### order_items（订单明细）
id, order_id, user_id, product_id, inventory_item_id, status, created_at, shipped_at, delivered_at, returned_at, sale_price

### products（产品）
id, cost, category, name, brand, retail_price, department, sku, distribution_center_id

### inventory_items（库存）
id, product_id, created_at, sold_at, cost, product_category, product_name, product_brand, product_retail_price, product_department, product_sku, product_distribution_center_id

### distribution_centers（配送中心）
id, name, latitude, longitude

### events（事件日志）
id, user_id, sequence_number, session_id, created_at, ip_address, city, state, postal_code, browser, traffic_source, uri, event_type

## 备注

- 文件中的 `*_old` 后缀是 Kaggle 上传者的命名方式，数据本身即为 BigQuery 原版快照
- 客户主要分布在美国、中国和巴西
- 销售品类包括服装、配饰等，覆盖所有年龄段
