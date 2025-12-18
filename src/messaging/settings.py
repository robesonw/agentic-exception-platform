"""
Message broker configuration settings.

Reads broker connection settings from environment variables.
"""

import os
from typing import Optional


def get_kafka_bootstrap_servers() -> str:
    """
    Get Kafka bootstrap servers from environment variable.
    
    Returns:
        Comma-separated list of broker addresses (e.g., "localhost:9092")
    """
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")


def get_kafka_security_protocol() -> str:
    """
    Get Kafka security protocol from environment variable.
    
    Returns:
        Security protocol: "PLAINTEXT", "SSL", "SASL_PLAINTEXT", or "SASL_SSL"
    """
    return os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")


def get_kafka_sasl_mechanism() -> Optional[str]:
    """Get Kafka SASL mechanism from environment variable."""
    return os.getenv("KAFKA_SASL_MECHANISM")


def get_kafka_sasl_username() -> Optional[str]:
    """Get Kafka SASL username from environment variable."""
    return os.getenv("KAFKA_SASL_USERNAME")


def get_kafka_sasl_password() -> Optional[str]:
    """Get Kafka SASL password from environment variable."""
    return os.getenv("KAFKA_SASL_PASSWORD")


def get_kafka_ssl_cafile() -> Optional[str]:
    """Get Kafka SSL CA certificate file path from environment variable."""
    return os.getenv("KAFKA_SSL_CAFILE")


def get_kafka_ssl_certfile() -> Optional[str]:
    """Get Kafka SSL client certificate file path from environment variable."""
    return os.getenv("KAFKA_SSL_CERTFILE")


def get_kafka_ssl_keyfile() -> Optional[str]:
    """Get Kafka SSL client key file path from environment variable."""
    return os.getenv("KAFKA_SSL_KEYFILE")


def get_kafka_ssl_keyfile_password() -> Optional[str]:
    """
    Get Kafka SSL client key file password from environment variable.
    
    Phase 9 P9-24: TLS configuration enhancement.
    """
    return os.getenv("KAFKA_SSL_KEYFILE_PASSWORD")


def get_kafka_ssl_check_hostname() -> bool:
    """
    Get Kafka SSL hostname verification setting from environment variable.
    
    Phase 9 P9-24: TLS configuration enhancement.
    
    Returns:
        True if hostname verification is enabled (default: True for security)
    """
    return os.getenv("KAFKA_SSL_CHECK_HOSTNAME", "true").lower() in ("true", "1", "yes")


def get_kafka_ssl_crlfile() -> Optional[str]:
    """
    Get Kafka SSL Certificate Revocation List (CRL) file path from environment variable.
    
    Phase 9 P9-24: TLS configuration enhancement.
    """
    return os.getenv("KAFKA_SSL_CRLFILE")


def get_kafka_ssl_ciphers() -> Optional[str]:
    """
    Get Kafka SSL cipher suites from environment variable.
    
    Phase 9 P9-24: TLS configuration enhancement.
    
    Returns:
        Comma-separated list of allowed cipher suites
    """
    return os.getenv("KAFKA_SSL_CIPHERS")


def get_kafka_producer_retries() -> int:
    """Get Kafka producer retry count from environment variable."""
    return int(os.getenv("KAFKA_PRODUCER_RETRIES", "3"))


def get_kafka_producer_retry_backoff_ms() -> int:
    """Get Kafka producer retry backoff in milliseconds from environment variable."""
    return int(os.getenv("KAFKA_PRODUCER_RETRY_BACKOFF_MS", "100"))


def get_kafka_consumer_auto_offset_reset() -> str:
    """
    Get Kafka consumer auto offset reset policy from environment variable.
    
    Returns:
        "earliest" or "latest"
    """
    return os.getenv("KAFKA_CONSUMER_AUTO_OFFSET_RESET", "earliest")


def get_kafka_consumer_enable_auto_commit() -> bool:
    """Get Kafka consumer auto-commit setting from environment variable."""
    return os.getenv("KAFKA_CONSUMER_ENABLE_AUTO_COMMIT", "true").lower() in ("true", "1", "yes")


def get_kafka_consumer_max_poll_records() -> int:
    """Get Kafka consumer max poll records from environment variable."""
    return int(os.getenv("KAFKA_CONSUMER_MAX_POLL_RECORDS", "500"))


class BrokerSettings:
    """Message broker configuration settings."""
    
    def __init__(self):
        # Kafka settings
        self.kafka_bootstrap_servers = get_kafka_bootstrap_servers()
        self.kafka_security_protocol = get_kafka_security_protocol()
        self.kafka_sasl_mechanism = get_kafka_sasl_mechanism()
        self.kafka_sasl_username = get_kafka_sasl_username()
        self.kafka_sasl_password = get_kafka_sasl_password()
        self.kafka_ssl_cafile = get_kafka_ssl_cafile()
        self.kafka_ssl_certfile = get_kafka_ssl_certfile()
        self.kafka_ssl_keyfile = get_kafka_ssl_keyfile()
        self.kafka_ssl_keyfile_password = get_kafka_ssl_keyfile_password()
        self.kafka_ssl_check_hostname = get_kafka_ssl_check_hostname()
        self.kafka_ssl_crlfile = get_kafka_ssl_crlfile()
        self.kafka_ssl_ciphers = get_kafka_ssl_ciphers()
        
        # Producer settings
        self.kafka_producer_retries = get_kafka_producer_retries()
        self.kafka_producer_retry_backoff_ms = get_kafka_producer_retry_backoff_ms()
        
        # Consumer settings
        self.kafka_consumer_auto_offset_reset = get_kafka_consumer_auto_offset_reset()
        self.kafka_consumer_enable_auto_commit = get_kafka_consumer_enable_auto_commit()
        self.kafka_consumer_max_poll_records = get_kafka_consumer_max_poll_records()


# Global settings instance
_settings: Optional[BrokerSettings] = None


def get_broker_settings() -> BrokerSettings:
    """
    Get broker settings instance.
    
    Returns:
        BrokerSettings instance
    """
    global _settings
    if _settings is None:
        _settings = BrokerSettings()
    return _settings

