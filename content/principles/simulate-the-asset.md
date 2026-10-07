---
title: Simulate the asset; don't assume it.
description: Business plans should rest on how the asset actually behaves, not on its nameplate.
number: 2
version: "1.0"
figures:
  - file: simulate-the-asset.svg
    caption: "Today the plan reads the nameplate. The asset's actual behaviour reaches Level 3, where people carry it between islands of context, and stops there."
  - file: record-to-report.svg
    caption: "Plans flow down as static artifacts and are executed on the asset. Records climb back up, slowing at every step. The longer the climb from record to report, the longer a plan that no longer matches the asset goes unnoticed."
lineage: ISA-95 Part 3, Manufacturing Operations Management, as the vocabulary for the missing layer.
history:
  - "1.0 · 2026-10-07 · First written."
---

Energy operators are mature at the bottom of the ISA-95 stack: field devices, control systems, and SCADA are well built. The operations layer above them exists as functions, such as scheduling, measurement, and maintenance, but not as a coherent system. Its context lives in separate tools, spreadsheets, and the heads of experienced people.

So the business layer is bolted almost directly to the bottom. The ERP and the plans built on it consume what the asset is rated to do, not what it does. Commercial strategies built that way model an imagined asset. Business-side AI added on top doesn't fix this; it produces a more fluent forecast from the same assumptions, automating the wrong model faster.
