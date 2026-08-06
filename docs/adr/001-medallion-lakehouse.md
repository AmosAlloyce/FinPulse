# ADR 001: Use a medallion lakehouse beside the warehouse

Status: accepted

## Decision

Retain immutable source records in bronze, publish validated event facts in silver, and place consumer-owned aggregates in gold. Use object storage as the replay authority and the warehouse as a serving system.

## Consequences

Compute and warehouse tables can be rebuilt, incidents remain auditable, and new consumers can reinterpret history. The cost is duplicated storage and an explicit catalog/retention responsibility.

