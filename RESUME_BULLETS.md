# Resume-ready project description

**QuoteGuard — Crypto Market Microstructure Research | Python, asyncio, pandas, NumPy**

- Built a tested public-market-data pipeline capturing 205,370 BTCUSDT quote/trade events across two sessions, with raw replay, receipt clocks, reconnect isolation, recorder telemetry and 77 automated tests.
- Evaluated order-flow features and 1s/5s adverse-selection markouts using purged chronological validation, frozen later-session inference, seven baseline/model comparisons, time-block uncertainty and independent scoring audits; documented negative generalization results.

The later recording uses a model frozen before capture and contains 60,582 events;
it is a separate same-day session, not independent-day or production-trading validation.
The combined model did not improve on zero-return RMSE in that session. Avoid claims
of durable alpha, maker fills, profitability or low-latency deployment. Add a repository
link only after actually publishing the project.
