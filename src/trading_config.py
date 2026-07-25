from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarketConfig:
    symbol: str
    timeframe: str


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    long_rsi_min: float
    long_rsi_max: float
    short_rsi_min: float
    short_rsi_max: float


@dataclass(frozen=True)
class RiskConfig:
    max_spread: float
    max_daily_loss_jpy: float
    max_consecutive_losses: int
    max_trades_per_day: int


@dataclass(frozen=True)
class ExecutionConfig:
    take_profit_pips: float
    stop_loss_pips: float
    unit_jpy_per_pip: float


@dataclass(frozen=True)
class TradingConfig:
    version: int
    market: MarketConfig
    strategy: StrategyConfig
    risk: RiskConfig
    execution: ExecutionConfig

    def to_run_metadata(self) -> dict[str, object]:
        return {
            "config_version": self.version,
            "configured_symbol": self.market.symbol,
            "configured_timeframe": self.market.timeframe,
            "strategy_name": self.strategy.name,
            "long_rsi_min": self.strategy.long_rsi_min,
            "long_rsi_max": self.strategy.long_rsi_max,
            "short_rsi_min": self.strategy.short_rsi_min,
            "short_rsi_max": self.strategy.short_rsi_max,
            "max_spread": self.risk.max_spread,
            "max_daily_loss_jpy": self.risk.max_daily_loss_jpy,
            "max_consecutive_losses": self.risk.max_consecutive_losses,
            "max_trades_per_day": self.risk.max_trades_per_day,
        }


def _validate_range(name: str, minimum: float, maximum: float) -> None:
    if not 0 <= minimum <= 100:
        raise ValueError(f"{name}_min は0〜100で指定してください。")
    if not 0 <= maximum <= 100:
        raise ValueError(f"{name}_max は0〜100で指定してください。")
    if minimum > maximum:
        raise ValueError(f"{name}_min は {name}_max 以下にしてください。")


def validate_trading_config(config: TradingConfig) -> None:
    if config.version < 1:
        raise ValueError("version は1以上で指定してください。")
    if not config.market.symbol.strip():
        raise ValueError("market.symbol は必須です。")
    if not config.market.timeframe.strip():
        raise ValueError("market.timeframe は必須です。")
    if not config.strategy.name.strip():
        raise ValueError("strategy.name は必須です。")

    _validate_range(
        "long_rsi",
        config.strategy.long_rsi_min,
        config.strategy.long_rsi_max,
    )
    _validate_range(
        "short_rsi",
        config.strategy.short_rsi_min,
        config.strategy.short_rsi_max,
    )

    if config.risk.max_spread <= 0:
        raise ValueError("risk.max_spread は0より大きくしてください。")
    if config.risk.max_daily_loss_jpy <= 0:
        raise ValueError("risk.max_daily_loss_jpy は正の値で指定してください。")
    if config.risk.max_consecutive_losses < 1:
        raise ValueError("risk.max_consecutive_losses は1以上で指定してください。")
    if config.risk.max_trades_per_day < 1:
        raise ValueError("risk.max_trades_per_day は1以上で指定してください。")

    if config.execution.take_profit_pips <= 0:
        raise ValueError("execution.take_profit_pips は0より大きくしてください。")
    if config.execution.stop_loss_pips <= 0:
        raise ValueError("execution.stop_loss_pips は0より大きくしてください。")
    if config.execution.unit_jpy_per_pip <= 0:
        raise ValueError("execution.unit_jpy_per_pip は0より大きくしてください。")


def load_trading_config(path: str | Path | None = None) -> TradingConfig:
    config_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[1] / "config" / "trading_config.json"
    )

    if not config_path.exists():
        raise FileNotFoundError(f"売買設定ファイルが見つかりません: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    try:
        config = TradingConfig(
            version=int(raw["version"]),
            market=MarketConfig(
                symbol=str(raw["market"]["symbol"]),
                timeframe=str(raw["market"]["timeframe"]),
            ),
            strategy=StrategyConfig(
                name=str(raw["strategy"]["name"]),
                long_rsi_min=float(raw["strategy"]["long_rsi_min"]),
                long_rsi_max=float(raw["strategy"]["long_rsi_max"]),
                short_rsi_min=float(raw["strategy"]["short_rsi_min"]),
                short_rsi_max=float(raw["strategy"]["short_rsi_max"]),
            ),
            risk=RiskConfig(
                max_spread=float(raw["risk"]["max_spread"]),
                max_daily_loss_jpy=float(raw["risk"]["max_daily_loss_jpy"]),
                max_consecutive_losses=int(raw["risk"]["max_consecutive_losses"]),
                max_trades_per_day=int(raw["risk"]["max_trades_per_day"]),
            ),
            execution=ExecutionConfig(
                take_profit_pips=float(raw["execution"]["take_profit_pips"]),
                stop_loss_pips=float(raw["execution"]["stop_loss_pips"]),
                unit_jpy_per_pip=float(raw["execution"]["unit_jpy_per_pip"]),
            ),
        )
    except KeyError as exc:
        raise ValueError(f"売買設定に必須項目がありません: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"売買設定の値が不正です: {exc}") from exc

    validate_trading_config(config)
    return config
