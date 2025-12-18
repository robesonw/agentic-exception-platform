#!/bin/bash
# Kafka Topic Initialization Script for Phase 9
# Creates all required topics for event-driven architecture

set -e

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
MAX_WAIT=60
WAIT_INTERVAL=5

echo "Waiting for Kafka to be ready at ${KAFKA_BOOTSTRAP_SERVERS}..."

# Wait for Kafka to be ready
MAX_ITERATIONS=$((MAX_WAIT / WAIT_INTERVAL))
for i in $(seq 1 $MAX_ITERATIONS); do
  if /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" > /dev/null 2>&1; then
    echo "Kafka is ready!"
    break
  fi
  if [ $i -eq $MAX_ITERATIONS ]; then
    echo "Kafka did not become ready within ${MAX_WAIT} seconds"
    exit 1
  fi
  echo "Waiting for Kafka... (${i}/${MAX_ITERATIONS})"
  sleep $WAIT_INTERVAL
done

# Function to create topic if it doesn't exist
create_topic() {
  local topic_name=$1
  local partitions=${2:-1}
  local replication_factor=${3:-1}
  
  echo "Creating topic: ${topic_name}"
  
  # Check if topic already exists
  if /opt/kafka/bin/kafka-topics.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" --list | grep -q "^${topic_name}$"; then
    echo "Topic ${topic_name} already exists, skipping..."
  else
    /opt/kafka/bin/kafka-topics.sh \
      --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" \
      --create \
      --topic "${topic_name}" \
      --partitions "${partitions}" \
      --replication-factor "${replication_factor}" \
      --if-not-exists
    
    if [ $? -eq 0 ]; then
      echo "✓ Topic ${topic_name} created successfully"
    else
      echo "✗ Failed to create topic ${topic_name}"
      exit 1
    fi
  fi
}

echo ""
echo "=========================================="
echo "Creating Phase 9 Kafka Topics"
echo "=========================================="
echo ""

# Inbound Events
create_topic "exceptions.ingested" 3 1
create_topic "exceptions.normalized" 3 1

# Agent Events
create_topic "triage.requested" 3 1
create_topic "triage.completed" 3 1
create_topic "policy.requested" 3 1
create_topic "policy.completed" 3 1
create_topic "playbook.matched" 3 1
create_topic "step.requested" 3 1
create_topic "tool.requested" 3 1
create_topic "tool.completed" 3 1
create_topic "feedback.captured" 3 1

# Control & Ops Events
create_topic "control.retry" 3 1
create_topic "control.dlq" 3 1
create_topic "sla.imminent" 3 1
create_topic "sla.expired" 3 1

echo ""
echo "=========================================="
echo "Topic Creation Complete"
echo "=========================================="
echo ""
echo "Listing all topics:"
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "${KAFKA_BOOTSTRAP_SERVERS}" --list
echo ""
echo "All Phase 9 topics have been created successfully!"

