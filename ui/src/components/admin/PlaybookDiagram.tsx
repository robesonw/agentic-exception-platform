import { useMemo, useCallback } from 'react'
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  ReactFlowProvider,
  Handle,
  Position,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import {
  Box,
  Typography,
  Card,
  CardContent,
  Tooltip,
  Chip,
  Stack,
} from '@mui/material'
import { alpha } from '@mui/material/styles'

export interface PlaybookStep {
  action?: string
  name?: string
  description?: string
  type?: 'agent' | 'human' | 'decision' | 'system'
  tool?: string
  [key: string]: any
}

export interface PlaybookDiagramProps {
  /** Playbook steps */
  steps: PlaybookStep[]
  /** Playbook name */
  playbookName: string
}

/**
 * Get node color based on step type
 */
function getStepColor(type?: string): { background: string; border: string; text: string } {
  switch (type) {
    case 'agent':
      return { background: '#e3f2fd', border: '#2196f3', text: '#1565c0' }
    case 'human':
      return { background: '#fff3e0', border: '#ff9800', text: '#e65100' }
    case 'decision':
      return { background: '#fce4ec', border: '#e91e63', text: '#ad1457' }
    case 'system':
      return { background: '#f3e5f5', border: '#9c27b0', text: '#6a1b9a' }
    default:
      return { background: '#e8f5e9', border: '#4caf50', text: '#2e7d32' }
  }
}

/**
 * Get icon for step type
 */
function getStepIcon(type?: string): string {
  switch (type) {
    case 'agent':
      return '🤖'
    case 'human':
      return '👤'
    case 'decision':
      return '🔀'
    case 'system':
      return '⚙️'
    default:
      return '📋'
  }
}

interface StepNodeData {
  stepIndex: number
  step: PlaybookStep
}

/**
 * Custom node component for playbook steps
 */
function StepNode({ data }: { data: StepNodeData }) {
  const { stepIndex, step } = data
  const colors = getStepColor(step.type)
  const icon = getStepIcon(step.type)
  const stepName = step.action || step.name || `Step ${stepIndex + 1}`

  const tooltipContent = useMemo(() => {
    const lines = [
      `Step ${stepIndex + 1}`,
      `Type: ${step.type || 'default'}`,
    ]
    if (step.description) {
      lines.push(`Description: ${step.description}`)
    }
    if (step.tool) {
      lines.push(`Tool: ${step.tool}`)
    }
    return lines.join('\n')
  }, [step, stepIndex])

  return (
    <>
      <Handle type="target" position={Position.Left} id="target" style={{ background: colors.border }} />
      <Tooltip title={<pre style={{ fontSize: '0.75rem', margin: 0, whiteSpace: 'pre-wrap' }}>{tooltipContent}</pre>} placement="top" arrow>
        <Card
          sx={{
            minWidth: 180,
            maxWidth: 220,
            backgroundColor: colors.background,
            border: `2px solid ${colors.border}`,
            borderRadius: 2,
            cursor: 'pointer',
            '&:hover': {
              boxShadow: 4,
              transform: 'scale(1.02)',
            },
            transition: 'all 0.2s ease-in-out',
          }}
        >
          <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
            {/* Header with icon and step number */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="body1" sx={{ fontSize: '1.2em' }}>
                {icon}
              </Typography>
              <Box
                sx={{
                  bgcolor: colors.border,
                  color: 'white',
                  borderRadius: '50%',
                  width: 24,
                  height: 24,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 'bold',
                }}
              >
                {stepIndex + 1}
              </Box>
              {step.type && (
                <Chip
                  label={step.type}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.65rem',
                    bgcolor: alpha(colors.border, 0.2),
                    color: colors.text,
                    fontWeight: 600,
                  }}
                />
              )}
            </Box>
            
            {/* Step name */}
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.text,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                lineHeight: 1.3,
                mb: step.description ? 0.5 : 0,
              }}
            >
              {stepName}
            </Typography>
            
            {/* Description preview */}
            {step.description && (
              <Typography
                variant="caption"
                sx={{
                  color: alpha(colors.text, 0.7),
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  lineHeight: 1.2,
                }}
              >
                {step.description}
              </Typography>
            )}
            
            {/* Tool badge */}
            {step.tool && (
              <Chip
                label={`🔧 ${step.tool}`}
                size="small"
                sx={{
                  mt: 1,
                  height: 20,
                  fontSize: '0.65rem',
                  bgcolor: alpha('#9c27b0', 0.15),
                  color: '#7b1fa2',
                }}
              />
            )}
          </CardContent>
        </Card>
      </Tooltip>
      <Handle type="source" position={Position.Right} id="source" style={{ background: colors.border }} />
    </>
  )
}

/**
 * Start node component
 */
function StartNode() {
  return (
    <>
      <Box
        sx={{
          width: 60,
          height: 60,
          borderRadius: '50%',
          bgcolor: '#4caf50',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 2,
        }}
      >
        <Typography sx={{ color: 'white', fontWeight: 'bold', fontSize: '0.8rem' }}>
          START
        </Typography>
      </Box>
      <Handle type="source" position={Position.Right} id="source" style={{ background: '#4caf50' }} />
    </>
  )
}

/**
 * End node component
 */
function EndNode() {
  return (
    <>
      <Handle type="target" position={Position.Left} id="target" style={{ background: '#f44336' }} />
      <Box
        sx={{
          width: 60,
          height: 60,
          borderRadius: '50%',
          bgcolor: '#f44336',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 2,
        }}
      >
        <Typography sx={{ color: 'white', fontWeight: 'bold', fontSize: '0.8rem' }}>
          END
        </Typography>
      </Box>
    </>
  )
}

const nodeTypes = {
  stepNode: StepNode,
  startNode: StartNode,
  endNode: EndNode,
}

/**
 * Apply dagre layout to nodes and edges
 */
function getLayoutedElements(nodes: Node[], edges: Edge[], direction: 'LR' | 'TB' = 'LR') {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 200
  const nodeHeight = 100
  const startEndSize = 60

  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 80 })

  nodes.forEach((node) => {
    const isStartEnd = node.type === 'startNode' || node.type === 'endNode'
    dagreGraph.setNode(node.id, {
      width: isStartEnd ? startEndSize : nodeWidth,
      height: isStartEnd ? startEndSize : nodeHeight,
    })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    const isStartEnd = node.type === 'startNode' || node.type === 'endNode'
    const width = isStartEnd ? startEndSize : nodeWidth
    const height = isStartEnd ? startEndSize : nodeHeight
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

/**
 * Inner component that uses React Flow hooks
 */
function PlaybookDiagramInner({ steps }: PlaybookDiagramProps) {
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => {
    // Create nodes from steps
    const nodes: Node[] = [
      // Start node
      {
        id: 'start',
        type: 'startNode',
        position: { x: 0, y: 0 },
        data: {},
      },
      // Step nodes
      ...steps.map((step, index) => ({
        id: `step-${index}`,
        type: 'stepNode',
        position: { x: 0, y: 0 },
        data: { stepIndex: index, step },
      })),
      // End node
      {
        id: 'end',
        type: 'endNode',
        position: { x: 0, y: 0 },
        data: {},
      },
    ]

    // Create edges connecting nodes in sequence
    const edges: Edge[] = []

    // Connect start to first step
    if (steps.length > 0) {
      edges.push({
        id: 'edge-start-0',
        source: 'start',
        target: 'step-0',
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#4caf50', strokeWidth: 2 },
      })
    }

    // Connect steps in sequence
    for (let i = 0; i < steps.length - 1; i++) {
      edges.push({
        id: `edge-${i}-${i + 1}`,
        source: `step-${i}`,
        target: `step-${i + 1}`,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#b1b1b7', strokeWidth: 2 },
      })
    }

    // Connect last step to end
    if (steps.length > 0) {
      edges.push({
        id: `edge-${steps.length - 1}-end`,
        source: `step-${steps.length - 1}`,
        target: 'end',
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#f44336', strokeWidth: 2 },
      })
    } else {
      // Direct connection from start to end if no steps
      edges.push({
        id: 'edge-start-end',
        source: 'start',
        target: 'end',
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#9e9e9e', strokeWidth: 2 },
      })
    }

    return getLayoutedElements(nodes, edges)
  }, [steps])

  const onInit = useCallback((reactFlowInstance: any) => {
    reactFlowInstance.fitView({ padding: 0.2 })
  }, [])

  return (
    <Box sx={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Legend */}
      <Box
        sx={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 10,
          bgcolor: 'background.paper',
          p: 1.5,
          borderRadius: 1,
          boxShadow: 1,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}>
          Step Types
        </Typography>
        <Stack spacing={0.5}>
          {[
            { type: 'agent', icon: '🤖', label: 'Agent', color: '#2196f3' },
            { type: 'human', icon: '👤', label: 'Human', color: '#ff9800' },
            { type: 'decision', icon: '🔀', label: 'Decision', color: '#e91e63' },
            { type: 'system', icon: '⚙️', label: 'System', color: '#9c27b0' },
          ].map((item) => (
            <Box key={item.type} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  bgcolor: item.color,
                }}
              />
              <Typography variant="caption">
                {item.icon} {item.label}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Box>

      <ReactFlow
        nodes={layoutedNodes}
        edges={layoutedEdges}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Controls />
        <MiniMap 
          nodeColor={(node) => {
            if (node.type === 'startNode') return '#4caf50'
            if (node.type === 'endNode') return '#f44336'
            const step = (node.data as unknown as StepNodeData)?.step
            return getStepColor(step?.type).border
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
      </ReactFlow>
    </Box>
  )
}

/**
 * Playbook Diagram component that visualizes playbook steps as an interactive workflow
 */
export default function PlaybookDiagram(props: PlaybookDiagramProps) {
  return (
    <ReactFlowProvider>
      <PlaybookDiagramInner {...props} />
    </ReactFlowProvider>
  )
}
