# ADR 0006: Initial domain skeletons

## Status

Accepted.

## Decision

The first domain entities remain deliberately small while preserving module ownership:

- staff owns EmployeeProfile and links employment data one-to-one with accounts.User.
- bookings owns Booking and its lifecycle status.
- orders owns Order and OrderItem, including price snapshots and the ongoing/serving/served lifecycle.
- inventory owns InventoryItem and append-oriented StockMovement records.

Shared timestamps live in core.TimeStampedModel. Shared monetary precision lives in core.money. Cross-module workflows are not implemented in model save methods.

## Data integrity

The database rejects zero booking party sizes, zero order quantities, negative order-item prices, and zero-quantity stock movements.

## Why

Keeping ownership explicit prevents the modular monolith from becoming one coupled model graph. Database constraints protect invariants regardless of whether writes later come from forms, APIs, background jobs, or MCP tools.

## Deferred

- booking table allocation and double-booking prevention
- recipe-based inventory deduction from orders
- order totals, taxes, discounts, and payments
- stock balance projections and reorder logic
- attendance, schedule overlap rules, employee requests, and payroll calculation rules
