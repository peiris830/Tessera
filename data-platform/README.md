# Data platform (Phase 3)

EventBridge → Kinesis Data Firehose → S3 data lake (raw zone, date-partitioned Parquet) →
Glue Data Catalog → Athena → dbt (dbt-athena) staging and mart models → organiser dashboard.

*Not started.* Will contain Firehose/Glue infrastructure, the dbt project and the dashboard.
