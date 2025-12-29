// Test authentication and navigation
// Simulate login and test pack navigation

console.log('Testing pack navigation authentication...');

// Set authentication in localStorage (simulating login)
localStorage.setItem('apiKey', 'test-api-key-123');
localStorage.setItem('tenantId', 'tenant_001');
localStorage.setItem('domain', 'TestDomain');

console.log('Authentication set up');
console.log('API Key:', localStorage.getItem('apiKey'));
console.log('Tenant ID:', localStorage.getItem('tenantId'));
console.log('Domain:', localStorage.getItem('domain'));

// Test fetching domain packs directly
fetch('/admin/packs/domain', {
  headers: {
    'X-API-KEY': 'test-api-key-123',
    'Content-Type': 'application/json'
  }
})
.then(response => {
  console.log('Domain packs response status:', response.status);
  if (response.ok) {
    return response.json();
  } else {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
})
.then(data => {
  console.log('Domain packs data:', data);
  console.log(`Found ${data.total} domain packs`);
})
.catch(error => {
  console.error('Error fetching domain packs:', error);
});

// Navigate to admin packs page
window.location.hash = '#/admin/packs';
console.log('Navigation set to admin packs page');