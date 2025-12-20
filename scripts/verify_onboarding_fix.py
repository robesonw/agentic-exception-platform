"""
Quick verification that onboarding.py has the correct pattern.
"""

import re
from pathlib import Path

onboarding_file = Path(__file__).parent.parent / "src" / "api" / "routes" / "onboarding.py"

content = onboarding_file.read_text(encoding="utf-8")

# Check for the OLD pattern (should NOT exist)
old_pattern = r'session_context=Depends\(get_db_session_context\)'
old_matches = list(re.finditer(old_pattern, content))

# Check for the NEW pattern (should exist)
new_pattern = r'async with get_db_session_context\(\) as session:'
new_matches = list(re.finditer(new_pattern, content))

print("=" * 60)
print("Verification of onboarding.py fix")
print("=" * 60)
print(f"\nOLD pattern (should be 0): {len(old_matches)}")
if old_matches:
    print("  ERROR: Found old pattern!")
    for match in old_matches[:5]:  # Show first 5
        line_num = content[:match.start()].count('\n') + 1
        print(f"    Line {line_num}: {match.group()}")

print(f"\nNEW pattern (should be > 0): {len(new_matches)}")
if new_matches:
    print("  OK: Found new pattern")
    for match in new_matches[:3]:  # Show first 3
        line_num = content[:match.start()].count('\n') + 1
        print(f"    Line {line_num}: {match.group()}")

print("\n" + "=" * 60)
if len(old_matches) == 0 and len(new_matches) > 0:
    print("SUCCESS: Fix verified! All endpoints use the correct pattern.")
    print("\nNext step: Restart your FastAPI server to pick up the changes.")
else:
    print("WARNING: Fix may not be complete. Please check the output above.")

