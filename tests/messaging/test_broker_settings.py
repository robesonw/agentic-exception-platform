"""
Unit tests for broker settings.
"""

import os
import pytest
from unittest.mock import patch

from src.messaging.settings import (
    BrokerSettings,
    get_broker_settings,
    get_kafka_bootstrap_servers,
    get_kafka_producer_retries,
    get_kafka_consumer_auto_offset_reset,
)


class TestBrokerSettings:
    """Test broker settings loading."""
    
    def test_get_kafka_bootstrap_servers_default(self):
        """Test default bootstrap servers."""
        with patch.dict(os.environ, {}, clear=True):
            servers = get_kafka_bootstrap_servers()
            assert servers == "localhost:9092"
            
    def test_get_kafka_bootstrap_servers_from_env(self):
        """Test bootstrap servers from environment variable."""
        with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "kafka1:9092,kafka2:9092"}):
            servers = get_kafka_bootstrap_servers()
            assert servers == "kafka1:9092,kafka2:9092"
            
    def test_get_kafka_producer_retries_default(self):
        """Test default producer retries."""
        with patch.dict(os.environ, {}, clear=True):
            retries = get_kafka_producer_retries()
            assert retries == 3
            
    def test_get_kafka_producer_retries_from_env(self):
        """Test producer retries from environment variable."""
        with patch.dict(os.environ, {"KAFKA_PRODUCER_RETRIES": "5"}):
            retries = get_kafka_producer_retries()
            assert retries == 5
            
    def test_get_kafka_consumer_auto_offset_reset_default(self):
        """Test default consumer auto offset reset."""
        with patch.dict(os.environ, {}, clear=True):
            offset_reset = get_kafka_consumer_auto_offset_reset()
            assert offset_reset == "earliest"
            
    def test_get_kafka_consumer_auto_offset_reset_from_env(self):
        """Test consumer auto offset reset from environment variable."""
        with patch.dict(os.environ, {"KAFKA_CONSUMER_AUTO_OFFSET_RESET": "latest"}):
            offset_reset = get_kafka_consumer_auto_offset_reset()
            assert offset_reset == "latest"
            
    def test_broker_settings_initialization(self):
        """Test BrokerSettings initialization."""
        with patch.dict(os.environ, {
            "KAFKA_BOOTSTRAP_SERVERS": "test:9092",
            "KAFKA_PRODUCER_RETRIES": "7",
            "KAFKA_CONSUMER_AUTO_OFFSET_RESET": "latest",
        }):
            settings = BrokerSettings()
            assert settings.kafka_bootstrap_servers == "test:9092"
            assert settings.kafka_producer_retries == 7
            assert settings.kafka_consumer_auto_offset_reset == "latest"
            
    def test_get_broker_settings_singleton(self):
        """Test get_broker_settings returns singleton."""
        settings1 = get_broker_settings()
        settings2 = get_broker_settings()
        
        assert settings1 is settings2
        
    def test_security_settings(self):
        """Test security-related settings."""
        with patch.dict(os.environ, {
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "KAFKA_SASL_MECHANISM": "PLAIN",
            "KAFKA_SASL_USERNAME": "user",
            "KAFKA_SASL_PASSWORD": "pass",
        }):
            settings = BrokerSettings()
            assert settings.kafka_security_protocol == "SASL_SSL"
            assert settings.kafka_sasl_mechanism == "PLAIN"
            assert settings.kafka_sasl_username == "user"
            assert settings.kafka_sasl_password == "pass"



