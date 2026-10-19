# Fluvius Three-Year Quarter-Hour Summary — 2023-10 to 2026-09

## Classification

`VERIFIED_READ_ONLY_EXPORT_SUMMARY`

## Scope

The owner supplied a Fluvius quarter-hour export spanning local boundaries
`2023-10-01T00:00:00+02:00` through `2026-10-02T00:00:00+02:00`.
The final day, 2026-10-01, contained 96 intervals with unavailable blank
volumes at analysis time and is excluded from the canonical comparison base.

The canonical half-open comparison period is therefore:

`2023-10-01T00:00:00+02:00` through `2026-10-01T00:00:00+02:00`.

## Result

| Period | Intervals | Read | Estimated | Unavailable | Import | Export |
|---|---:|---:|---:|---:|---:|---:|
| 2023-10-01 to 2024-10-01 | 35.136 | 34.932 | 198 | 6 | 7.820,473 kWh | 1.471,811 kWh |
| 2024-10-01 to 2025-10-01 | 35.040 | 34.939 | 101 | 0 | 8.411,868 kWh | 1.268,425 kWh |
| 2025-10-01 to 2026-10-01 | 35.040 | 35.035 | 5 | 0 | 9.510,180 kWh | 989,269 kWh |
| **Total** | **105.216** | **104.906** | **304** | **6** | **25.742,521 kWh** | **3.729,505 kWh** |

The first period contains 35.136 quarters because it includes 29 February
2024. The complete local timestamp sequence, including all daylight-saving
transitions, canonicalizes without missing interval positions.

## Quality finding

The six unavailable historical intervals occur on 2024-04-25 and retain blank
volume values with status `Geen verbruik`. They are not silently interpreted as
zero. Estimated intervals remain separately classified.

The analyzer was updated with a regression test so blank volume values are
reported as unavailable rather than causing a crash or being converted to
zero.

## Use for comparison

This dataset supports three independent annual energy profiles instead of one:

1. 2023-10 through 2024-09;
2. 2024-10 through 2025-09;
3. 2025-10 through 2026-09.

It can materially improve:

- dynamic-contract sensitivity across several consumption years;
- winter-versus-summer load comparison;
- negative-price and injection exposure analysis;
- battery-arbitrage simulations over multiple winters;
- robustness checks against conclusions from the single invoice year.

A multi-year financial backtest still requires an exactly aligned Belgian
Day-Ahead price series for the same three local periods and explicit tariff
versions or a controlled constant-tariff sensitivity model.

## Privacy

The raw export remains under Git-ignored `docs/information/`. This committed
summary contains no EAN, meter identifier, address or raw interval series.
