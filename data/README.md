# TheLook eCommerce 数据集
## 数据来源与许可说明
本项目使用 Google BigQuery Public Datasets 中的 TheLook Ecommerce
虚构电商数据集进行学习、分析和功能验证。

- 官方数据表：[`bigquery-public-data.thelook_ecommerce`](https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=thelook_ecommerce&page=dataset)
- 本地数据获取渠道：[Kaggle 镜像](https://www.kaggle.com/datasets/chiraggivan82/ecommerce-bigquery)
- 数据性质：用于演示与分析的虚构电商数据
- 数据时间范围：2019—2024年

本仓库不包含或重新分发完整原始数据文件。
使用者需从原始数据来源自行获取数据。

## 核心应用所需文件

将以下文件放入项目的 `data/` 目录：

```text
data/
├── events_old.csv
├── products_old.csv
└── industry_benchmark_comparison.xlsx
```

其中 `industry_benchmark_comparison.xlsx` 已包含在仓库中；
完整的 `events_old.csv` 与 `products_old.csv` 需自行获取。

如果数据存放在其他目录，可在 `.env` 中设置：

```text
ECOMM_DATA_DIR=E:\agent\data
```

## 数据许可边界

第三方数据集适用其原始来源的使用条款，不因本代码仓库的许可方式而改变。
