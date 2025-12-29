# Phase 13 (Prompt 4B) — Workflow Viewer Manual Verification Checklist

## Implementation Summary

✅ **Dependencies Installed**

- @xyflow/react (React Flow)
- dagre (auto-layout)
- @types/dagre (TypeScript types)

✅ **Backend Implementation**

- New endpoint: `GET /api/exceptions/{exception_id}/workflow-graph`
- Response models: WorkflowNode, WorkflowEdge, WorkflowGraphResponse
- UIQueryService.get_exception_workflow_graph() method
- Tenant isolation enforced
- Pipeline stage status mapping from events

✅ **Frontend Implementation**

- WorkflowViewer component using React Flow + dagre
- ExceptionWorkflowTab component with auto-refresh
- API integration and type definitions
- Status-based node styling and icons
- Legend and tooltips
- Read-only interaction (no editing)

✅ **Integration**

- Added "Workflow" tab to Exception Detail Page
- Polling every 5 seconds for near real-time updates
- Error handling and loading states

✅ **Tests**

- Backend endpoint tests
- Integration test framework

## Manual Verification Steps

### 1. Backend API Verification

```bash
# Test the backend endpoint directly
curl "http://localhost:8000/ui/exceptions/{exception_id}/workflow-graph?tenant_id={tenant_id}"
```

Expected response structure:

```json
{
  "nodes": [
    {
      "id": "intake",
      "type": "agent",
      "label": "Intake",
      "status": "completed",
      "started_at": null,
      "completed_at": "2024-01-01T12:00:00Z",
      "meta": { "event_type": "ExceptionNormalized" }
    }
  ],
  "edges": [
    {
      "id": "intake-to-triage",
      "source": "intake",
      "target": "triage",
      "label": null
    }
  ],
  "current_stage": "triage",
  "playbook_id": null,
  "playbook_steps": null
}
```

### 2. UI Component Verification

**Steps:**

1. Start the development server: `cd ui && npm run dev`
2. Navigate to an exception detail page: `/exceptions/{exception_id}`
3. Click on the "Workflow" tab
4. Verify the workflow viewer loads correctly

**Expected Behavior:**

- [ ] Workflow tab appears between "Explanation" and "Audit" tabs
- [ ] Workflow diagram renders with pipeline stages
- [ ] Nodes show correct status colors:
  - **Blue**: Agent (pending)
  - **Orange**: In-progress
  - **Green**: Completed
  - **Red**: Failed
  - **Gray**: Skipped
- [ ] Node tooltips show timestamps and event details on hover
- [ ] Legend displays node types and statuses
- [ ] Current stage indicator shows if applicable
- [ ] Auto-refresh updates every 5 seconds
- [ ] No editing controls (read-only)
- [ ] Zoom and pan controls work
- [ ] MiniMap shows overview

### 3. Pipeline Stage Verification

**Expected Pipeline Stages (in order):**

1. **Intake** (🤖) - Exception normalization
2. **Triage** (🤖) - Classification and severity assignment
3. **Policy** (🤖) - Tenant policy evaluation
4. **Playbook** (🤖) - Playbook matching and execution
5. **Tool** (⚙️) - Tool execution
6. **Feedback** (🤖) - Outcome logging and metrics

**Status Mapping from Events:**

- `ExceptionNormalized` → Intake completed
- `TriageCompleted` → Triage completed
- `PolicyEvaluationCompleted` → Policy completed
- `PlaybookMatched` → Playbook in-progress
- `PlaybookStepCompleted` → Playbook completed
- `ToolExecutionRequested` → Tool in-progress
- `ToolExecutionCompleted` → Tool completed
- `FeedbackCaptured` → Feedback completed

### 4. Real-time Updates Verification

**Test Steps:**

1. Open workflow tab for an exception in-progress
2. Wait 5+ seconds and observe for updates
3. Process exception through pipeline stages
4. Verify workflow updates reflect stage progression

### 5. Error Handling Verification

**Test Cases:**

- [ ] Non-existent exception shows "No workflow data available"
- [ ] Network errors show error message
- [ ] Loading state displays while fetching
- [ ] Tenant isolation prevents cross-tenant access

### 6. Responsive Design Verification

**Test on different screen sizes:**

- [ ] Desktop (>1200px): Full layout with legend
- [ ] Tablet (768-1200px): Adapted layout
- [ ] Mobile (<768px): Usable on small screens

### 7. Performance Verification

**Expected Performance:**

- [ ] Initial load < 2 seconds
- [ ] Smooth animations and interactions
- [ ] No memory leaks with auto-refresh
- [ ] Efficient re-rendering on updates

### 8. Integration Testing

**Full Workflow Test:**

1. Create a new exception via API
2. Process through pipeline stages
3. Watch workflow update in real-time
4. Verify final completed state

## Known Limitations (MVP)

✅ **Intentional MVP Limitations:**

- Read-only workflow viewer (no editing)
- Linear pipeline stages only (no complex branching)
- Polling updates (not WebSockets)
- Basic playbook step display (no detailed step visualization)

## Success Criteria

Phase 13 Workflow Viewer is **COMPLETE** when:

✅ A playbook renders as a graph with pipeline stages
✅ Execution status overlays update (via polling)  
✅ Copilot can reference workflow steps (API available)
✅ No playbook editing is possible via UI
✅ Viewer works for both Finance and Healthcare packs (tenant-agnostic)
✅ All manual verification steps pass

## Deployment Notes

**Dependencies to ensure in production:**

- React Flow (@xyflow/react)
- dagre layout library
- Backend endpoint deployed and accessible
- Database event persistence working

**Performance considerations:**

- Consider WebSocket upgrade for high-frequency updates
- Cache workflow graph data for frequently accessed exceptions
- Monitor polling impact on server load

## Future Enhancements (Out of Scope)

- Drag/drop workflow editing
- Complex conditional logic visualization
- Real-time WebSocket updates
- Detailed playbook step breakdown
- Workflow animation and step highlighting
- Integration with Copilot for step explanations
