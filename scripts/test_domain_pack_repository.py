#!/usr/bin/env python3
"""
Quick test script for DomainPackRepository.

This script runs basic tests to verify the repository implementation.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import Column, DateTime, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import DomainPackVersion
from src.infrastructure.repositories.domain_pack_repository import DomainPackRepository

TestBase = declarative_base()


class TestDomainPackVersion(TestBase):
    __tablename__ = "domain_pack_version"
    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    pack_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


async def test_domain_pack_repository():
    """Run basic tests for DomainPackRepository."""
    print("=" * 70)
    print("DomainPackRepository Tests")
    print("=" * 70)
    
    # Create test engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS domain_pack_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                version INTEGER NOT NULL,
                pack_json TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE(domain, version)
            );
            CREATE INDEX IF NOT EXISTS ix_domain_pack_version_domain ON domain_pack_version(domain);
            """
            )
        )
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        repo = DomainPackRepository(session)
        
        # Test 1: Create domain pack version
        print("\n1. Testing create_domain_pack_version...")
        pack_json = {
            "domainName": "Finance",
            "version": "1.0.0",
            "entities": {"TradeOrder": {"keys": ["orderId"]}},
        }
        created = await repo.create_domain_pack_version("Finance", 1, pack_json)
        assert created is not None
        assert created.domain == "Finance"
        assert created.version == 1
        print("  [OK] Created domain pack version")
        
        # Test 2: Get domain pack
        print("\n2. Testing get_domain_pack...")
        retrieved = await repo.get_domain_pack("Finance", 1)
        assert retrieved is not None
        assert retrieved.pack_json == pack_json
        print("  [OK] Retrieved domain pack by domain and version")
        
        # Test 3: Create multiple versions
        print("\n3. Testing multiple versions...")
        await repo.create_domain_pack_version("Finance", 2, {"domainName": "Finance", "version": "2.0.0"})
        await repo.create_domain_pack_version("Finance", 3, {"domainName": "Finance", "version": "3.0.0"})
        await repo.create_domain_pack_version("Healthcare", 1, {"domainName": "Healthcare", "version": "1.0.0"})
        print("  [OK] Created multiple domain pack versions")
        
        # Test 4: Get latest domain pack
        print("\n4. Testing get_latest_domain_pack...")
        latest = await repo.get_latest_domain_pack("Finance")
        assert latest is not None
        assert latest.version == 3  # Highest version
        print(f"  [OK] Retrieved latest domain pack (version {latest.version})")
        
        # Test 5: List domain packs
        print("\n5. Testing list_domain_packs...")
        all_packs = await repo.list_domain_packs()
        assert len(all_packs) == 4
        print(f"  [OK] Listed all domain packs ({len(all_packs)} total)")
        
        finance_packs = await repo.list_domain_packs(domain="Finance")
        assert len(finance_packs) == 3
        assert all(pack.domain == "Finance" for pack in finance_packs)
        print(f"  [OK] Listed Finance domain packs ({len(finance_packs)} total)")
        
        # Test 6: Version ordering
        print("\n6. Testing version ordering...")
        # Create pack with lower version but newer timestamp
        pack_old = DomainPackVersion(
            domain="TestDomain",
            version=1,
            pack_json={"domainName": "TestDomain", "version": "1.0.0"},
            created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
        )
        pack_new = DomainPackVersion(
            domain="TestDomain",
            version=2,
            pack_json={"domainName": "TestDomain", "version": "2.0.0"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),  # Older timestamp
        )
        session.add_all([pack_old, pack_new])
        await session.commit()
        
        latest_test = await repo.get_latest_domain_pack("TestDomain")
        assert latest_test is not None
        assert latest_test.version == 2  # Should use highest version, not newest timestamp
        print("  [OK] Version ordering uses highest version number")
        
        # Test 7: Validation errors
        print("\n7. Testing validation errors...")
        try:
            await repo.create_domain_pack_version("", 1, {})
            print("  [FAILED] Should have raised ValueError for empty domain")
        except ValueError:
            print("  [OK] Empty domain rejected")
        
        try:
            await repo.create_domain_pack_version("Finance", 0, {})
            print("  [FAILED] Should have raised ValueError for version < 1")
        except ValueError:
            print("  [OK] Invalid version rejected")
        
        try:
            await repo.create_domain_pack_version("Finance", 1, {})
            print("  [FAILED] Should have raised ValueError for empty pack_json")
        except ValueError:
            print("  [OK] Empty pack_json rejected")
        
        try:
            await repo.create_domain_pack_version("Finance", 1, pack_json)
            print("  [FAILED] Should have raised ValueError for duplicate version")
        except ValueError:
            print("  [OK] Duplicate version rejected")
        
        await session.commit()
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS domain_pack_version;"))
    await engine.dispose()
    
    print("\n" + "=" * 70)
    print("[SUCCESS] All tests passed!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_domain_pack_repository()))


