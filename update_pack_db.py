#!/usr/bin/env python3
"""
Script to update domain pack in database from the JSON file.
Run inside the Docker container.
"""
import json
import hashlib
import psycopg2

# Database connection
conn = psycopg2.connect(
    host="postgres",
    database="sentinai",
    user="sentinai",
    password="sentinai"
)

# Load the JSON file
with open("/app/runtime/domainpacks/ACME_CAPITAL/CapitalMarketsTrading/1.0.0.json") as f:
    pack_data = json.load(f)

print(f"Loaded pack with {len(pack_data.get('playbooks', []))} playbooks")

# Compute checksum
checksum = hashlib.sha256(json.dumps(pack_data, sort_keys=True).encode()).hexdigest()[:16]

# Update the database
cur = conn.cursor()

# Update existing record
cur.execute(
    """UPDATE domain_packs 
       SET content_json = %s, checksum = %s 
       WHERE domain = 'CapitalMarketsTrading' AND version = '1.0'
       RETURNING id""",
    (json.dumps(pack_data), checksum)
)
result = cur.fetchone()

if result:
    print(f"Updated domain pack id={result[0]}")
else:
    print("No record found to update")

conn.commit()

# Verify
cur.execute(
    """SELECT jsonb_array_length(content_json->'playbooks') 
       FROM domain_packs 
       WHERE domain = 'CapitalMarketsTrading'"""
)
count = cur.fetchone()[0]
print(f"Database now has {count} playbooks")

cur.close()
conn.close()
print("Done!")
