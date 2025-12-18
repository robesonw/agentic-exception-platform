# Event Partitioning and Ordering

## Overview

Phase 9 implements event partitioning to ensure ordering guarantees while allowing parallel processing. Events are partitioned by `(tenant_id, exception_id)` to ensure that events for the same exception are processed in order.

## Ordering Guarantees

### Per-Exception Ordering

**Ordering is guaranteed per `(tenant_id, exception_id)` only.**

This means:
- ✅ Events for the same exception are processed **in order**
- ✅ Events for different exceptions can be processed **in parallel**
- ✅ Events for the same tenant but different exceptions can be processed **in parallel**

### No Global Ordering

**Global ordering is NOT guaranteed.**

This means:
- ❌ Events for different exceptions may be processed out of order
- ❌ Events for different tenants may be processed out of order
- ❌ Events with the same tenant_id but different exception_id may be processed out of order

## Partition Key Generation

### Format

Partition keys are generated using the `get_partition_key()` function:

```python
from src.messaging.partitioning import get_partition_key

# With both tenant_id and exception_id
partition_key = get_partition_key("tenant_001", "exc_001")
# Result: "tenant_001:exc_001"

# With only tenant_id
partition_key = get_partition_key("tenant_001")
# Result: "tenant_001"
```

### Implementation

The partition key is a simple concatenation:
- `"{tenant_id}:{exception_id}"` when both are available
- `"{tenant_id}"` when only tenant_id is available

This ensures:
1. **Consistency**: Same inputs always produce the same partition key
2. **Determinism**: Partition key is deterministic and stable
3. **Ordering**: Events with the same partition key are processed in order

## Kafka Partition Assignment

When using Kafka, the partition key determines which Kafka partition the event is published to. Kafka guarantees ordering within a partition, so:

- Events with the same partition key → same Kafka partition → processed in order
- Events with different partition keys → different Kafka partitions → may be processed in parallel

### Partition Number Calculation

For systems that need to map to a fixed number of partitions, use `get_partition_number()`:

```python
from src.messaging.partitioning import get_partition_number

partition_num = get_partition_number("tenant_001", "exc_001", num_partitions=10)
# Result: integer between 0 and 9
```

This uses consistent hashing (MD5) to map partition keys to partition numbers.

## Usage in EventPublisherService

The `EventPublisherService` automatically generates partition keys when publishing events:

```python
from src.messaging.event_publisher import EventPublisherService

event = {
    "event_type": "ExceptionIngested",
    "tenant_id": "tenant_001",
    "exception_id": "exc_001",
    "payload": {...},
}

# Partition key is automatically generated: "tenant_001:exc_001"
event_id = await publisher.publish_event("exceptions", event)
```

## Best Practices

1. **Always provide exception_id when available**: This ensures proper ordering per exception
2. **Use tenant_id as minimum**: Even without exception_id, tenant_id ensures tenant isolation
3. **Don't rely on global ordering**: Design handlers to be order-independent across exceptions
4. **Ensure handlers are idempotent**: Use idempotency checks (P9-12) to handle duplicate events

## Limitations

1. **No cross-exception ordering**: Events for different exceptions may be processed in any order
2. **No cross-tenant ordering**: Events for different tenants may be processed in any order
3. **Partition key collisions**: Different (tenant_id, exception_id) pairs may map to the same partition (acceptable for parallel processing)

## Examples

### Example 1: Same Exception, Ordered Processing

```python
# Event 1 for exception exc_001
event1 = {"tenant_id": "tenant_001", "exception_id": "exc_001", ...}
# Partition key: "tenant_001:exc_001"

# Event 2 for same exception exc_001
event2 = {"tenant_id": "tenant_001", "exception_id": "exc_001", ...}
# Partition key: "tenant_001:exc_001"

# Result: Events 1 and 2 are processed IN ORDER
```

### Example 2: Different Exceptions, Parallel Processing

```python
# Event 1 for exception exc_001
event1 = {"tenant_id": "tenant_001", "exception_id": "exc_001", ...}
# Partition key: "tenant_001:exc_001"

# Event 2 for different exception exc_002
event2 = {"tenant_id": "tenant_001", "exception_id": "exc_002", ...}
# Partition key: "tenant_001:exc_002"

# Result: Events 1 and 2 may be processed IN PARALLEL or in any order
```

### Example 3: No Exception ID

```python
# Event without exception_id
event = {"tenant_id": "tenant_001", ...}
# Partition key: "tenant_001"

# Result: All events for tenant_001 (without exception_id) are processed in order
```



