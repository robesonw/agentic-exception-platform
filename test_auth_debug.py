from src.api.auth import APIKeyAuth

api_auth = APIKeyAuth()
api_key = 'test_api_key_tenant_001'
print(f'Testing API key: {api_key}')
print(f'Last 8 chars: {api_key[-8:]}')

user_context = api_auth.validate_api_key(api_key)
print(f'User context created:')
print(f'  - tenant_id: {user_context.tenant_id}')
print(f'  - user_id: "{user_context.user_id}"')
print(f'  - user_id is truthy: {bool(user_context.user_id)}')
print(f'  - role: {user_context.role}')