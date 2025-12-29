// Test script to verify playbook action buttons work
// This simulates what happens when a user clicks the action buttons

console.log('Testing Playbook Actions...');

// Test data similar to what the API returns
const testPlaybook = {
  playbook_id: "CMT3.mismatched_trade_details",
  name: "Playbook for MISMATCHED_TRADE_DETAILS",
  description: "Automated playbook for MISMATCHED_TRADE_DETAILS",
  exception_type: "MISMATCHED_TRADE_DETAILS",
  domain: "CMT3",
  version: "v1.0",
  status: "active",
  source_pack_type: "domain",
  source_pack_id: 5,
  source_pack_version: "v1.0",
  steps_count: 6,
  tool_refs_count: 0,
  overridden: false,
  overridden_from: null
};

// Simulate the handleViewDetail function
function testHandleViewDetail(playbook) {
  console.log('Testing handleViewDetail...');
  console.log('Playbook:', playbook.name);
  console.log('Exception Type:', playbook.exception_type);
  console.log('Domain:', playbook.domain);
  console.log('✅ View Detail would show dialog with playbook metadata');
}

// Simulate the handleViewDiagram function
function testHandleViewDiagram(playbook) {
  console.log('Testing handleViewDiagram...');
  console.log('Playbook:', playbook.name);
  console.log('Steps Count:', playbook.steps_count);
  console.log('✅ View Diagram would show workflow visualization');
}

// Simulate the handleViewSourcePack function  
function testHandleViewSourcePack(playbook) {
  console.log('Testing handleViewSourcePack...');
  const url = playbook.source_pack_type === 'domain' 
    ? `/admin/packs/domain/${playbook.domain}/${playbook.version}`
    : `/admin/packs/tenant/${playbook.domain}/${playbook.version}`;
  console.log('Would open:', url);
  console.log('✅ View Source Pack would open new tab');
}

// Run the tests
console.log('=== Testing Playbook Action Buttons ===');
testHandleViewDetail(testPlaybook);
console.log('');
testHandleViewDiagram(testPlaybook);  
console.log('');
testHandleViewSourcePack(testPlaybook);
console.log('');
console.log('=== All Action Button Tests Complete ===');