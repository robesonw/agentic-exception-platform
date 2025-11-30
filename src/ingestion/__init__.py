"""
Ingestion module.

Provides both batch (REST) and streaming ingestion capabilities.
"""

from src.ingestion.streaming import (
    KafkaIngestionBackend,
    StreamingIngestionBackend,
    StreamingIngestionService,
    StreamingMessage,
    StubIngestionBackend,
    create_streaming_backend,
    load_streaming_config,
)

__all__ = [
    "KafkaIngestionBackend",
    "StreamingIngestionBackend",
    "StreamingIngestionService",
    "StreamingMessage",
    "StubIngestionBackend",
    "create_streaming_backend",
    "load_streaming_config",
]

