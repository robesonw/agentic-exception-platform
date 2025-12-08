import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  InputAdornment,
  Button,
  Stack,
  Avatar,
  Chip,
  Fade,
} from '@mui/material'
import {
  Close as CloseIcon,
  Send as SendIcon,
  SmartToy as BotIcon,
} from '@mui/icons-material'
import { themeColors } from '../../theme/theme.ts'

interface Message {
  role: 'user' | 'ai'
  text: string
  timestamp?: Date
}

interface AICopilotProps {
  open: boolean
  onClose: () => void
}

export default function AICopilot({ open, onClose }: AICopilotProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'ai',
      text: 'Hello, Operator. I am monitoring active exceptions. How can I assist you today?',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSend = () => {
    if (!input.trim()) return

    const userMessage: Message = {
      role: 'user',
      text: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')

    // Simulate AI response (in production, this would call an API)
    setTimeout(() => {
      const aiMessage: Message = {
        role: 'ai',
        text: 'I am analyzing the correlation between recent exceptions and system patterns. One moment...',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, aiMessage])
    }, 1000)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open && inputRef.current) {
      // Focus input when copilot opens
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  const quickSuggestions = [
    'Summarize critical exceptions',
    'Show similar past cases',
    'Draft escalation response',
    'Analyze trends',
  ]

  if (!open) return null

  return (
    <Fade in={open}>
      <Paper
        sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          width: { xs: 'calc(100% - 48px)', sm: 420, md: 480 },
          height: { xs: 'calc(100% - 96px)', sm: 600 },
          maxHeight: 600,
          display: 'flex',
          flexDirection: 'column',
          zIndex: 1300,
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4), 0 4px 16px 0 rgba(0, 0, 0, 0.3)',
          border: `1px solid ${themeColors.borderPrimary}`,
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <Box
          sx={{
            p: 2,
            borderBottom: `1px solid ${themeColors.borderPrimary}`,
            backgroundColor: themeColors.bgTertiary,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: themeColors.success,
                boxShadow: `0 0 8px ${themeColors.success}80`,
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 },
                },
              }}
            />
            <BotIcon sx={{ fontSize: 20, color: themeColors.primary }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: themeColors.textPrimary }}>
              AI Co-Pilot
            </Typography>
            <Chip
              label="Active"
              size="small"
              sx={{
                height: 20,
                fontSize: '0.625rem',
                bgcolor: `${themeColors.success}1A`,
                color: themeColors.success,
                border: `1px solid ${themeColors.success}33`,
              }}
            />
          </Box>
          <IconButton
            size="small"
            onClick={onClose}
            sx={{
              color: themeColors.textSecondary,
              '&:hover': { color: themeColors.textPrimary, backgroundColor: themeColors.bgElevated },
            }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        {/* Messages */}
        <Box
          sx={{
            flex: 1,
            overflowY: 'auto',
            p: 2,
            backgroundColor: themeColors.bgPrimary,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {messages.map((msg, index) => (
            <Box
              key={index}
              sx={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                gap: 1,
              }}
            >
              {msg.role === 'ai' && (
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    bgcolor: themeColors.primary,
                    boxShadow: `0 2px 8px ${themeColors.primary}40`,
                  }}
                >
                  <BotIcon sx={{ fontSize: 18 }} />
                </Avatar>
              )}
              <Paper
                sx={{
                  maxWidth: '75%',
                  p: 1.5,
                  backgroundColor: msg.role === 'user' ? themeColors.primary : themeColors.bgSecondary,
                  border: `1px solid ${msg.role === 'user' ? themeColors.primary : themeColors.borderPrimary}`,
                  borderRadius: 2,
                  boxShadow: msg.role === 'user' ? `0 2px 8px ${themeColors.primary}30` : 'none',
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    color: msg.role === 'user' ? '#fff' : themeColors.textPrimary,
                    lineHeight: 1.5,
                  }}
                >
                  {msg.text}
                </Typography>
              </Paper>
              {msg.role === 'user' && (
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    bgcolor: themeColors.bgElevated,
                    border: `1px solid ${themeColors.borderSecondary}`,
                  }}
                >
                  U
                </Avatar>
              )}
            </Box>
          ))}
          <div ref={messagesEndRef} />
        </Box>

        {/* Quick Suggestions */}
        {messages.length === 1 && (
          <Box sx={{ p: 2, borderTop: `1px solid ${themeColors.borderPrimary}`, backgroundColor: themeColors.bgTertiary }}>
            <Typography variant="caption" sx={{ color: themeColors.textTertiary, mb: 1, display: 'block' }}>
              Quick suggestions:
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
              {quickSuggestions.map((suggestion, index) => (
                <Button
                  key={index}
                  size="small"
                  variant="outlined"
                  onClick={() => setInput(suggestion)}
                  sx={{
                    fontSize: '0.75rem',
                    py: 0.5,
                    px: 1.5,
                    borderColor: themeColors.borderSecondary,
                    color: themeColors.textSecondary,
                    '&:hover': {
                      borderColor: themeColors.primary,
                      color: themeColors.primary,
                      backgroundColor: `${themeColors.primary}0A`,
                    },
                  }}
                >
                  {suggestion}
                </Button>
              ))}
            </Stack>
          </Box>
        )}

        {/* Input */}
        <Box
          sx={{
            p: 2,
            borderTop: `1px solid ${themeColors.borderPrimary}`,
            backgroundColor: themeColors.bgTertiary,
          }}
        >
          <TextField
            inputRef={inputRef}
            fullWidth
            size="small"
            placeholder="Ask about exceptions, trends, or rules..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={handleSend}
                    disabled={!input.trim()}
                    sx={{
                      color: input.trim() ? themeColors.primary : themeColors.textTertiary,
                      '&:hover': {
                        backgroundColor: `${themeColors.primary}1A`,
                      },
                    }}
                  >
                    <SendIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
              sx: {
                backgroundColor: themeColors.bgSecondary,
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: themeColors.borderPrimary,
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: themeColors.borderSecondary,
                },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: themeColors.primary,
                },
              },
            }}
          />
        </Box>
      </Paper>
    </Fade>
  )
}

