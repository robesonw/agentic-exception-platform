# Colon Prefix Issue - Analysis

## Problem
Exceptions still have colon prefixes (`: fin_settlement_fail`) despite:
- Catalog file being clean (no colons)
- Normalization code in multiple places
- Container rebuilds

## Hypothesis
The catalog cache might be holding stale data with colons, OR the normalization code is not being executed.

## Fixes Attempted
1. Added normalization in `_weighted_choice`
2. Added normalization after selection
3. Added normalization before raw_payload
4. Added cache clearing in `_get_catalog`

## Status
Still investigating root cause.

