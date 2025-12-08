import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Fab,
  CircularProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  Send as SendIcon,
  SmartToy as BotIcon,
} from '@mui/icons-material';
import { themeColors } from '../../theme/theme';
import { useCopilotChat, type ChatMessage, type CopilotAnswerType } from '../../hooks/useCopilotChat';

export interface AICopilotDockProps {
  initiallyOpen?: boolean;
}

export default function AICopilotDock({ initiallyOpen = false }: AICopilotDockProps) {
  const [isOpen, setIsOpen] = useState(initiallyOpen);
  const { messages, loading, error, sendMessage } = useCopilotChat();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleSend = () => {
    if (!input.trim() || loading) return;

    const messageText = input.trim();
    setInput('');
    sendMessage(messageText);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    // Optionally auto-focus input when suggestion is clicked
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      // Focus input when copilot opens
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const quickSuggestions = [
    'Summarize today\'s exceptions',
    'Explain EX-12345',
    'What is the policy for settlement failures?',
    'Show me recent critical exceptions',
  ];

  return (
    <>
      {/* Floating Trigger Button */}
      {!isOpen && (
        <Fab
          color="primary"
          aria-label="Open AI Co-Pilot"
          onClick={() => setIsOpen(true)}
          sx={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 1300,
            boxShadow: `0 4px 16px 0 ${themeColors.primary}40`,
            '&:hover': {
              transform: 'scale(1.1)',
              boxShadow: `0 6px 20px 0 ${themeColors.primary}60`,
            },
            transition: 'all 0.2s ease-in-out',
          }}
        >
          <BotIcon />
        </Fab>
      )}

      {/* Docked Chat Window */}
      {isOpen && (
        <Fade in={isOpen}>
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
                onClick={() => setIsOpen(false)}
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
              {messages.map((msg, index) => {
                const answerType = msg.meta?.answer_type;
                const citations = msg.meta?.citations || [];

                // Format answer type for display (e.g., "POLICY_HINT" -> "POLICY HINT")
                const formatAnswerType = (type: CopilotAnswerType | undefined): string => {
                  if (!type) return '';
                  return type.replace(/_/g, ' ');
                };

                return (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      gap: 0.5,
                    }}
                  >
                    {/* Answer Type Badge (for assistant messages only) */}
                    {msg.role === 'assistant' && answerType && (
                      <Chip
                        label={formatAnswerType(answerType)}
                        size="small"
                        sx={{
                          height: 20,
                          fontSize: '0.625rem',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          bgcolor: `${themeColors.primary}1A`,
                          color: themeColors.primary,
                          border: `1px solid ${themeColors.primary}33`,
                          alignSelf: 'flex-start',
                        }}
                      />
                    )}

                    {/* Message Content */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                        gap: 1,
                        width: '100%',
                      }}
                    >
                      {msg.role === 'assistant' && (
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

                    {/* Citations (for assistant messages only) */}
                    {msg.role === 'assistant' && citations.length > 0 && (
                      <Box
                        sx={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 0.5,
                          maxWidth: '75%',
                          ml: msg.role === 'assistant' ? '40px' : 0, // Align with message content
                        }}
                      >
                        {citations.map((citation, citationIndex) => {
                          const isException = citation.type === 'exception';
                          const citationId = citation.id;

                          if (isException && citationId) {
                            // Make exception citations clickable
                            return (
                              <Chip
                                key={citationIndex}
                                label={citationId}
                                size="small"
                                onClick={(e) => {
                                  e.preventDefault();
                                  // Navigate to exception detail page
                                  navigate(`/exceptions/${citationId}`);
                                  // Close the copilot dock when clicking a citation
                                  setIsOpen(false);
                                }}
                                sx={{
                                  height: 22,
                                  fontSize: '0.7rem',
                                  bgcolor: themeColors.bgElevated,
                                  color: themeColors.primary,
                                  border: `1px solid ${themeColors.borderSecondary}`,
                                  cursor: 'pointer',
                                  '&:hover': {
                                    bgcolor: `${themeColors.primary}1A`,
                                    borderColor: themeColors.primary,
                                  },
                                }}
                              />
                            );
                          } else {
                            // Non-exception citations (policy, domain) as regular chips
                            return (
                              <Chip
                                key={citationIndex}
                                label={citationId}
                                size="small"
                                sx={{
                                  height: 22,
                                  fontSize: '0.7rem',
                                  bgcolor: themeColors.bgElevated,
                                  color: themeColors.textSecondary,
                                  border: `1px solid ${themeColors.borderSecondary}`,
                                }}
                              />
                            );
                          }
                        })}
                      </Box>
                    )}
                  </Box>
                );
              })}
              {loading && (
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'flex-start',
                    gap: 1,
                  }}
                >
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
                  <Paper
                    sx={{
                      p: 1.5,
                      backgroundColor: themeColors.bgSecondary,
                      border: `1px solid ${themeColors.borderPrimary}`,
                      borderRadius: 2,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                    }}
                  >
                    <CircularProgress size={16} sx={{ color: themeColors.primary }} />
                    <Typography
                      variant="body2"
                      sx={{
                        color: themeColors.textSecondary,
                        fontStyle: 'italic',
                      }}
                    >
                      Thinking...
                    </Typography>
                  </Paper>
                </Box>
              )}
              {error && (
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'flex-start',
                    gap: 1,
                  }}
                >
                  <Avatar
                    sx={{
                      width: 32,
                      height: 32,
                      bgcolor: themeColors.error,
                      boxShadow: `0 2px 8px ${themeColors.error}40`,
                    }}
                  >
                    <BotIcon sx={{ fontSize: 18 }} />
                  </Avatar>
                  <Paper
                    sx={{
                      p: 1.5,
                      backgroundColor: themeColors.bgSecondary,
                      border: `1px solid ${themeColors.error}`,
                      borderRadius: 2,
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{
                        color: themeColors.error,
                        lineHeight: 1.5,
                      }}
                    >
                      {error}
                    </Typography>
                  </Paper>
                </Box>
              )}
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
                      onClick={() => handleSuggestionClick(suggestion)}
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
                    e.preventDefault();
                    handleSend();
                  }
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={handleSend}
                        disabled={!input.trim() || loading}
                        sx={{
                          color: input.trim() && !loading ? themeColors.primary : themeColors.textTertiary,
                          '&:hover': {
                            backgroundColor: `${themeColors.primary}1A`,
                          },
                        }}
                      >
                        {loading ? (
                          <CircularProgress size={16} sx={{ color: themeColors.textTertiary }} />
                        ) : (
                          <SendIcon fontSize="small" />
                        )}
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
      )}
    </>
  );
}


