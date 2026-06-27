CREATE DATABASE IF NOT EXISTS fx_ai_trader;

CREATE EXTERNAL TABLE IF NOT EXISTS fx_ai_trader.trades (
  trade_id string,
  symbol string,
  strategy_name string,
  side string,
  entry_time timestamp,
  entry_price double,
  entry_reason string,
  ai_decision_id string,
  exit_time timestamp,
  exit_price double,
  pips double,
  pnl_jpy double,
  result string,
  exit_reason string
)
STORED AS PARQUET
LOCATION 's3://fx-ai-trader-lake-okazimaru-20260627/curated/trades/';

CREATE EXTERNAL TABLE IF NOT EXISTS fx_ai_trader.ai_decisions (
  decision_id string,
  timestamp_jst timestamp,
  symbol string,
  model_name string,
  model_version string,
  market_regime string,
  suggested_side string,
  confidence double,
  risk_level string,
  entry_permission boolean,
  signal_reason string,
  risk_reason string,
  rsi double,
  ma_short double,
  ma_long double,
  final_decision string
)
STORED AS PARQUET
LOCATION 's3://fx-ai-trader-lake-okazimaru-20260627/curated/ai_decisions/';

CREATE EXTERNAL TABLE IF NOT EXISTS fx_ai_trader.daily_summary (
  trade_date date,
  trade_count bigint,
  total_pnl double,
  win_count bigint,
  lose_count bigint,
  avg_pnl double,
  win_rate double
)
STORED AS PARQUET
LOCATION 's3://fx-ai-trader-lake-okazimaru-20260627/curated/daily_summary/';

CREATE EXTERNAL TABLE IF NOT EXISTS fx_ai_trader.macro_events (
  event_id string,
  event_time_jst string,
  country string,
  currency string,
  category string,
  event_name string,
  speaker string,
  importance string,
  forecast string,
  previous string,
  actual string,
  status string,
  no_trade_before_min int,
  no_trade_after_min int
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
  "separatorChar" = ",",
  "quoteChar" = "\""
)
LOCATION 's3://fx-ai-trader-lake-okazimaru-20260627/curated/macro_events/'
TBLPROPERTIES (
  "skip.header.line.count"="1"
);
