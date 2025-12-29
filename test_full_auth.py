from src.api.auth import AuthManager

# Test the full authentication flow
auth_manager = AuthManager()

# Test with the exact API key from the curl request
api_key = "test_api_key_tenant_001"

try:
    user_context = auth_manager.authenticate(api_key=api_key)
    print(f"✅ Authentication successful:")
    print(f"  - tenant_id: '{user_context.tenant_id}'")
    print(f"  - user_id: '{user_context.user_id}'")
    print(f"  - user_id type: {type(user_context.user_id)}")
    print(f"  - user_id bool: {bool(user_context.user_id)}")
    print(f"  - user_id repr: {repr(user_context.user_id)}")
    print(f"  - role: {user_context.role}")
    print(f"  - auth_method: {user_context.auth_method}")
    
    # Test the dict creation like require_authenticated_user does
    auth_dict = {
        "user_id": user_context.user_id,
        "tenant_id": user_context.tenant_id
    }
    print(f"\\n✅ Auth dict:")
    print(f"  - auth_dict['user_id']: '{auth_dict['user_id']}'")
    print(f"  - auth_dict['tenant_id']: '{auth_dict['tenant_id']}'")
    print(f"  - bool(auth_dict['user_id']): {bool(auth_dict['user_id'])}")
    
except Exception as e:
    print(f"❌ Authentication failed: {e}")
    import traceback
    traceback.print_exc()