"""Test script for Gmail integration"""
import asyncio
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tools.gmail_tool import GmailTool

async def test_gmail():
    """Test Gmail manager functionality"""
    manager = GmailTool()
    user_id = "livekit-mem0"

    print("=" * 60)
    print("🧪 Testing Gmail Integration")
    print("=" * 60)

    # Test 1: Check connection
    print("\n1️⃣ Testing connection status...")
    is_connected = manager.is_connected(user_id)
    print(f"   ✓ Connected: {is_connected}")

    if not is_connected:
        print("\n❌ Gmail not connected!")
        print("📍 To connect, visit: http://localhost:8000/auth?user_id=livekit-mem0")
        print("\n⚠️  Make sure auth_server.py is running:")
        print("   python auth_server.py")
        return

    # Test 2: Search emails
    print("\n2️⃣ Testing email search...")
    test_queries = [
        "recent emails",
        "unread emails",
        "emails from yesterday"
    ]

    for query in test_queries:
        print(f"\n   Query: '{query}'")
        result = await manager.search_emails(user_id, query)
        if result["success"]:
            print(f"   ✓ {result['message']}")
            if result["emails"]:
                print(f"   📧 Found {len(result['emails'])} email(s)")
                for email in result["emails"][:2]:  # Show first 2
                    print(f"      - {email['subject'][:50]}")
        else:
            print(f"   ✗ {result['message']}")

    # Test 3: Connection instructions
    print("\n3️⃣ Testing connection instructions...")
    instructions = manager.get_connection_instructions()
    print(f"   ✓ Instructions: {instructions[:100]}...")

    # Test 4: Function definitions
    print("\n4️⃣ Testing function definitions...")
    functions = manager.get_function_definitions()
    print(f"   ✓ Found {len(functions)} function(s):")
    for func in functions:
        print(f"      - {func['name']}: {func['description'][:60]}...")

    print("\n" + "=" * 60)
    print("✅ Gmail integration tests complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_gmail())
