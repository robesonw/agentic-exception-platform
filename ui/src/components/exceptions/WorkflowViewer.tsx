import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MiniMap,
  ReactFlowProvider,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import {
  Box,
  Typography,
  Alert,
  Card,
  CardContent,
  Tooltip,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import { WorkflowNode as WorkflowNodeData, WorkflowEdge as WorkflowEdgeData } from '../../types/exceptions'
import { formatDateTime } from '../../utils/dateFormat'

export interface WorkflowViewerProps {
  /** Exception identifier */
  exceptionId: string
  /** Workflow nodes */
  nodes: WorkflowNodeData[]
  /** Workflow edges */
  edges: WorkflowEdgeData[]
  /** Current stage */
  currentStage?: string | null
  /** Loading state */
  loading?: boolean
  /** Error state */
  error?: string | null
}

/**
 * Get node color based on status and type
 */
function getNodeColor(status: string, type: string): { background: string; border: string } {
  // Status-based colors
  switch (status) {
    case 'completed':
      return { background: '#4caf50', border: '#388e3c' }
    case 'in-progress':
      return { background: '#ff9800', border: '#f57c00' }
    case 'failed':
      return { background: '#f44336', border: '#d32f2f' }
    case 'skipped':
      return { background: '#9e9e9e', border: '#616161' }
    case 'pending':
    default:
      // Type-based colors for pending
      switch (type) {
        case 'agent':
          return { background: '#e3f2fd', border: '#2196f3' }
        case 'human':
          return { background: '#f3e5f5', border: '#9c27b0' }
        case 'decision':
          return { background: '#fff3e0', border: '#ff9800' }
        case 'system':
          return { background: '#f5f5f5', border: '#9e9e9e' }
        case 'playbook':
          return { background: '#e8f5e8', border: '#66bb6a' }
        default:
          return { background: '#f5f5f5', border: '#9e9e9e' }
      }
  }
}

/**
 * Get node shape and styling based on kind
 */
function getNodeStyling(kind: string): { shape: string; borderStyle: string; opacity: number } {
  switch (kind) {
    case 'stage':
      return { shape: 'rounded', borderStyle: 'solid', opacity: 1.0 }
    case 'playbook':
      return { shape: 'rounded', borderStyle: 'dashed', opacity: 0.9 }
    case 'step':
      return { shape: 'rounded', borderStyle: 'dotted', opacity: 0.8 }
    default:
      return { shape: 'rounded', borderStyle: 'solid', opacity: 1.0 }
  }
}

/**
 * Get node icon based on type and kind
 */
function getNodeIcon(type: string, kind?: string): string {
  // Kind-specific icons
  if (kind === 'playbook') {
    return '📋'
  }
  if (kind === 'step') {
    return '📝'
  }
  
  // Type-specific icons
  switch (type) {
    case 'agent':
      return '🤖'
    case 'human':
      return '👤'
    case 'decision':
      return '🔀'
    case 'system':
      return '⚙️'
    case 'playbook':
      return '📋'
    default:
      return '◯'
  }
}

/**
 * Custom node component with status styling
 */
function CustomNode({ data }: { data: WorkflowNodeData & { position: { x: number; y: number } } }) {
  const { background, border } = getNodeColor(data.status, data.type)
  const styling = getNodeStyling(data.kind || 'stage')
  const icon = getNodeIcon(data.type, data.kind)

  const statusIcon = useMemo(() => {
    switch (data.status) {
      case 'completed':
        return '✓'
      case 'in-progress':
        return '⟳'
      case 'failed':
        return '✗'
      case 'skipped':
        return '⤷'
      default:
        return ''
    }
  }, [data.status])

  const tooltipContent = useMemo(() => {
    const lines = [
      `ID: ${data.id}`,
      `Kind: ${data.kind || 'stage'}`,
      `Type: ${data.type}`,
      `Status: ${data.status}`,
    ]
    
    if (data.started_at) {
      lines.push(`Started: ${formatDateTime(data.started_at)}`)
    }
    
    if (data.completed_at) {
      lines.push(`Completed: ${formatDateTime(data.completed_at)}`)
    }
    
    if (data.meta?.event_type) {
      lines.push(`Event: ${data.meta.event_type}`)
    }
    
    if (data.meta?.actor) {
      lines.push(`Actor: ${data.meta.actor}`)
    }
    
    if (data.meta?.step_index !== undefined && data.meta?.step_index !== null) {
      lines.push(`Step: ${Number(data.meta.step_index) + 1}`)
    }
    
    return lines.join('\n')
  }, [data])

  // Determine if this is a playbook-related node for special styling
  const isPlaybookNode = data.kind === 'playbook' || data.kind === 'step'

  return (
    <>
      <Handle type="target" position={Position.Left} id="target" />
      <Tooltip title={<pre style={{ fontSize: '0.875rem', margin: 0 }}>{tooltipContent}</pre>} placement="top" arrow>
        <Card
          sx={{
            minWidth: isPlaybookNode ? 140 : 120,
            backgroundColor: background,
            border: `2px ${styling.borderStyle} ${border}`,
            borderRadius: styling.shape === 'rounded' ? 2 : 0,
            opacity: styling.opacity,
            cursor: 'pointer',
            '&:hover': {
              boxShadow: 2,
              transform: 'scale(1.02)',
              opacity: 1.0,
            },
            transition: 'all 0.2s ease-in-out',
            // Special styling for playbook nodes
            ...(isPlaybookNode && {
              background: `linear-gradient(135deg, ${background}, ${alpha(background, 0.7)})`,
            }),
          }}
        >
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography variant="body2" sx={{ fontSize: '1.2em' }}>
              {icon}
            </Typography>
            {statusIcon && (
              <Typography variant="body2" sx={{ fontSize: '1em', fontWeight: 'bold', color: border }}>
                {statusIcon}
              </Typography>
            )}
            {data.kind && (
              <Typography variant="caption" sx={{ fontSize: '0.7em', color: alpha(border, 0.8), fontWeight: 'bold' }}>
                {data.kind.toUpperCase()}
              </Typography>
            )}
          </Box>
          <Typography variant="body2" sx={{ fontWeight: 600, color: '#000', textAlign: 'center', fontSize: isPlaybookNode ? '0.85rem' : '0.875rem' }}>
            {data.label}
          </Typography>
          <Typography variant="caption" sx={{ color: alpha('#000', 0.7), textAlign: 'center', display: 'block' }}>
            {data.status}
          </Typography>
        </CardContent>
        </Card>
      </Tooltip>
      <Handle type="source" position={Position.Right} id="source" />
    </>
  )
}

/**
 * Apply dagre layout to nodes and edges
 */
function getLayoutedElements(
  nodes: WorkflowNodeData[],
  edges: WorkflowEdgeData[],
  direction: 'TB' | 'LR' = 'LR'
) {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 160
  const nodeHeight = 80

  dagreGraph.setGraph({ rankdir: direction })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      id: node.id,
      type: 'custom',
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
      data: node as unknown as Record<string, unknown>,
    }
  }) as Node[]

  const layoutedEdges: Edge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label || undefined,
    type: 'smoothstep',
    animated: false,
    style: {
      stroke: '#b1b1b7',
      strokeWidth: 2,
    },
    labelStyle: {
      fontSize: 12,
      fontWeight: 500,
    },
  }))

  return { nodes: layoutedNodes, edges: layoutedEdges }
}

/**
 * Legend component
 */
function Legend() {
  const typeItems = [
    { icon: '🤖', label: 'Agent', color: '#2196f3' },
    { icon: '👤', label: 'Human', color: '#9c27b0' },
    { icon: '🔀', label: 'Decision', color: '#ff9800' },
    { icon: '⚙️', label: 'System', color: '#9e9e9e' },
    { icon: '📋', label: 'Playbook', color: '#66bb6a' },
  ]

  const kindItems = [
    { icon: '◉', label: 'Stage (solid border)', style: 'solid' },
    { icon: '◈', label: 'Playbook (dashed border)', style: 'dashed' },
    { icon: '◇', label: 'Step (dotted border)', style: 'dotted' },
  ]

  const statusItems = [
    { icon: '◯', label: 'Pending', color: '#e0e0e0' },
    { icon: '⟳', label: 'In Progress', color: '#ff9800' },
    { icon: '✓', label: 'Completed', color: '#4caf50' },
    { icon: '✗', label: 'Failed', color: '#f44336' },
    { icon: '⤷', label: 'Skipped', color: '#9e9e9e' },
  ]

  return (
    <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 10 }}>
      <Card sx={{ p: 2, backgroundColor: alpha('#fff', 0.95), maxWidth: 200 }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
          Node Types
        </Typography>
        {typeItems.map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography sx={{ fontSize: '1em' }}>{item.icon}</Typography>
            <Box sx={{ width: 12, height: 12, backgroundColor: item.color, borderRadius: 1 }} />
            <Typography variant="caption">{item.label}</Typography>
          </Box>
        ))}
        
        <Typography variant="subtitle2" sx={{ mb: 1, mt: 2, fontWeight: 600 }}>
          Node Kinds
        </Typography>
        {kindItems.map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography sx={{ fontSize: '1em' }}>{item.icon}</Typography>
            <Box sx={{ 
              width: 12, 
              height: 12, 
              backgroundColor: '#e0e0e0', 
              border: `2px ${item.style} #999`, 
              borderRadius: 1 
            }} />
            <Typography variant="caption" sx={{ fontSize: '0.7em' }}>{item.label}</Typography>
          </Box>
        ))}
        
        <Typography variant="subtitle2" sx={{ mb: 1, mt: 2, fontWeight: 600 }}>
          Status
        </Typography>
        {statusItems.map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography sx={{ fontSize: '1em' }}>{item.icon}</Typography>
            <Box sx={{ width: 12, height: 12, backgroundColor: item.color, borderRadius: 1 }} />
            <Typography variant="caption">{item.label}</Typography>
          </Box>
        ))}
      </Card>
    </Box>
  )
}

/**
 * Workflow viewer component with React Flow
 */
export default function WorkflowViewer({
  exceptionId: _exceptionId,
  nodes: inputNodes,
  edges: inputEdges,
  currentStage,
  loading = false,
  error = null,
}: WorkflowViewerProps) {
  // _exceptionId is available for future use (e.g., node click actions)
  void _exceptionId
  void currentStage
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  // Custom node types
  const nodeTypes = useMemo(
    () => ({
      custom: CustomNode,
    }),
    []
  )

  // Layout and set nodes/edges when input changes
  useEffect(() => {
    if (inputNodes.length > 0) {
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        inputNodes,
        inputEdges,
        'LR'
      )
      
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    }
  }, [inputNodes, inputEdges, setNodes, setEdges])

  // Handle node click (could be used for future interactions)
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      console.log('Node clicked:', node.data)
    },
    []
  )

  if (loading) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography>Loading workflow...</Typography>
      </Box>
    )
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        {error}
      </Alert>
    )
  }

  if (inputNodes.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No workflow data available</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ height: 500, position: 'relative', border: '1px solid #e0e0e0', borderRadius: 1 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesConnectable={false}
        nodesDraggable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
        preventScrolling={false}
      >
        <Background />
        <Controls />
        <MiniMap
          style={{
            height: 120,
            backgroundColor: '#f5f5f5',
          }}
          zoomable
          pannable
        />
      </ReactFlow>
      <Legend />
      
      {currentStage && (
        <Box sx={{ position: 'absolute', top: 16, left: 16, zIndex: 10 }}>
          <Alert severity="info" sx={{ backgroundColor: alpha('#2196f3', 0.1) }}>
            Current stage: <strong>{currentStage}</strong>
          </Alert>
        </Box>
      )}
    </Box>
  )
}

/**
 * Wrapper component that provides ReactFlowProvider
 */
export function WorkflowViewerWithProvider(props: WorkflowViewerProps) {
  return (
    <ReactFlowProvider>
      <WorkflowViewer {...props} />
    </ReactFlowProvider>
  )
}