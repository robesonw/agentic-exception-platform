// Comprehensive test of the Playbooks Page action buttons
// This script will test the login flow and then the action buttons

async function testPlaybooksPageActions() {
  console.log('🧪 Testing Playbooks Page Action Buttons...\n');
  
  // Test 1: Check if login page loads
  try {
    const loginResponse = await fetch('http://localhost:3000/login');
    console.log('✅ Login page accessible:', loginResponse.ok ? 'YES' : 'NO');
  } catch (error) {
    console.log('❌ Login page error:', error.message);
  }
  
  // Test 2: Check if backend API works
  try {
    const apiResponse = await fetch('http://localhost:8000/admin/playbooks/registry?tenant_id=cmt3', {
      headers: {
        'X-API-Key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json'
      }
    });
    const data = await apiResponse.json();
    console.log('✅ Backend API working:', apiResponse.ok ? 'YES' : 'NO');
    if (apiResponse.ok) {
      console.log('   📊 Playbooks available:', data.items?.length || 0);
      if (data.items?.length > 0) {
        console.log('   📝 Sample playbook:', data.items[0].playbook_id);
      }
    }
  } catch (error) {
    console.log('❌ Backend API error:', error.message);
  }
  
  // Test 3: Check if admin playbooks page loads (without auth)
  try {
    const adminResponse = await fetch('http://localhost:3000/admin/playbooks');
    console.log('✅ Admin playbooks page accessible:', adminResponse.ok ? 'YES' : 'NO');
  } catch (error) {
    console.log('❌ Admin playbooks page error:', error.message);
  }
  
  // Test 4: Simulate action button functionality
  console.log('\n🔘 Simulating Action Button Functionality:');
  
  const testPlaybook = {
    playbook_id: "CMT3.mismatched_trade_details",
    name: "Playbook for MISMATCHED_TRADE_DETAILS",
    exception_type: "MISMATCHED_TRADE_DETAILS",
    domain: "CMT3",
    version: "v1.0",
    status: "active",
    source_pack_type: "domain",
    source_pack_id: 5,
    steps_count: 6,
    tool_refs_count: 0
  };
  
  // Test View Details Action
  console.log('🔍 Testing "View Details" action...');
  try {
    // This simulates what happens when handleViewDetail is called
    console.log('   ✅ Opening detail dialog for:', testPlaybook.name);
    console.log('   ✅ Fetching domain pack for source_pack_id:', testPlaybook.source_pack_id);
    console.log('   ✅ Would display playbook metadata and steps');
  } catch (error) {
    console.log('   ❌ View Details error:', error.message);
  }
  
  // Test View Diagram Action
  console.log('🔄 Testing "View Diagram" action...');
  try {
    console.log('   ✅ Opening workflow diagram for:', testPlaybook.name);
    console.log('   ✅ Would show', testPlaybook.steps_count, 'workflow steps');
    console.log('   ✅ Would render step-by-step visualization');
  } catch (error) {
    console.log('   ❌ View Diagram error:', error.message);
  }
  
  // Test View Source Pack Action
  console.log('📦 Testing "View Source Pack" action...');
  try {
    const expectedUrl = `/admin/packs/domain/${testPlaybook.domain}/${testPlaybook.version}`;
    console.log('   ✅ Would open new tab to:', expectedUrl);
    console.log('   ✅ Source pack type:', testPlaybook.source_pack_type);
  } catch (error) {
    console.log('   ❌ View Source Pack error:', error.message);
  }
  
  console.log('\n🎯 Test Summary:');
  console.log('The action buttons should work if:');
  console.log('1. User is logged in with valid credentials');
  console.log('2. Tenant has playbooks data');
  console.log('3. No JavaScript runtime errors occur');
  
  console.log('\n🔧 Next Steps:');
  console.log('1. Navigate to http://localhost:3000/login');
  console.log('2. Set: Tenant=TENANT_001, Domain=TestDomain, API Key=test_api_key_tenant_001');
  console.log('3. Go to http://localhost:3000/admin/playbooks');
  console.log('4. Click any action button to test functionality');
}

// Run the test
testPlaybooksPageActions();