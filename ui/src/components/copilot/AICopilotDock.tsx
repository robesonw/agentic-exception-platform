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
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  Badge,
} from '@mui/material';
import {
  Close as CloseIcon,
  Send as SendIcon,
  SmartToy as BotIcon,
  ExpandMore as ExpandMoreIcon,
  Security as SecurityIcon,
  Visibility as VisibilityIcon,
  PlaylistPlay as PlaybookIcon,
  FindInPage as SimilarIcon,
} from '@mui/icons-material';
import { themeColors } from '../../theme/theme';
import { useCopilotChat, type ChatMessage } from '../../hooks/useCopilotChat';

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
    'Explain classification logic for EX-12345', 
    'What is the policy for settlement failures?',
    'Show me recent critical exceptions',
    'Find similar exceptions to EX-12345',
    'Recommend a playbook for timeout errors',
    'Test structured response demo', // Added for testing
  ];

  /**
   * Get source type badge configuration
   */
  const getSourceTypeBadge = (sourceType: string) => {
    const badges = {
      'policy_doc': { label: 'POLICY', color: '#1976d2', bg: '#e3f2fd' },
      'resolved_exception': { label: 'RESOLVED', color: '#388e3c', bg: '#e8f5e8' },
      'audit_event': { label: 'AUDIT', color: '#f57c00', bg: '#fff3e0' },
      'tool_registry': { label: 'TOOL', color: '#7b1fa2', bg: '#f3e5f5' },
      'playbook': { label: 'PLAYBOOK', color: '#d32f2f', bg: '#ffebee' },
    };
    return badges[sourceType] || { label: sourceType.toUpperCase(), color: '#757575', bg: '#f5f5f5' };
  };

  /**
   * Render citation with proper source type badge and navigation
   */
  const renderCitation = (citation: any, index: number) => {
    const badge = getSourceTypeBadge(citation.source_type);
    // All these source types are clickable
    const isClickable = citation.url || 
      citation.source_type === 'resolved_exception' || 
      citation.source_type === 'playbook';

    const handleClick = (e: React.MouseEvent) => {
      e.preventDefault();
      if (citation.url) {
        navigate(citation.url);
      } else if (citation.source_type === 'resolved_exception') {
        navigate(`/exceptions/${citation.source_id || citation.id}`);
      } else if (citation.source_type === 'playbook') {
        // Navigate to playbooks page or specific playbook
        const playbookId = citation.source_id || citation.id;
        navigate(`/admin/playbooks?playbook=${playbookId}`);
      }
      setIsOpen(false);
    };

    return (
      <Chip
        key={index}
        label={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="caption" sx={{ color: badge.color, fontWeight: 600 }}>
              {badge.label}
            </Typography>
            <Typography variant="caption">
              {citation.title || citation.id}
            </Typography>
          </Box>
        }
        size="small"
        onClick={isClickable ? handleClick : undefined}
        sx={{
          height: 24,
          fontSize: '0.7rem',
          bgcolor: badge.bg,
          border: `1px solid ${badge.color}33`,
          cursor: isClickable ? 'pointer' : 'default',
          '&:hover': isClickable ? {
            bgcolor: `${badge.color}1A`,
            borderColor: badge.color,
          } : {},
        }}
      />
    );
  };

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
                  AI Co-Pilot v13
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
                const meta = msg.meta;
                const bullets = meta?.bullets || [];
                const citations = meta?.citations || [];
                const recommendedPlaybook = meta?.recommended_playbook;
                const similarExceptions = meta?.similar_exceptions || [];
                const safety = meta?.safety;
                const intent = meta?.intent;

                return (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      gap: 1,
                    }}
                  >
                    {/* Safety Warning Banner (for assistant messages with warnings) */}
                    {msg.role === 'assistant' && safety?.blocked && (
                      <Alert 
                        severity="warning" 
                        sx={{ 
                          alignSelf: 'flex-start',
                          maxWidth: '75%',
                          mb: 0.5
                        }}
                      >
                        Response blocked for safety reasons
                      </Alert>
                    )}

                    {msg.role === 'assistant' && safety?.warnings?.length > 0 && (
                      <Alert 
                        severity="info" 
                        sx={{ 
                          alignSelf: 'flex-start',
                          maxWidth: '75%',
                          mb: 0.5
                        }}
                      >
                        {safety.warnings.join('. ')}
                      </Alert>
                    )}

                    {/* Intent & READ_ONLY Badge (for assistant messages) */}
                    {msg.role === 'assistant' && (intent || safety?.mode) && (
                      <Box sx={{ display: 'flex', gap: 0.5, alignSelf: 'flex-start' }}>
                        {intent && (
                          <Chip
                            label={intent.replace(/_/g, ' ')}
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
                            }}
                          />
                        )}
                        {safety?.mode === 'READ_ONLY' && (
                          <Chip
                            icon={<SecurityIcon sx={{ fontSize: 14 }} />}
                            label="READ ONLY"
                            size="small"
                            sx={{
                              height: 20,
                              fontSize: '0.625rem',
                              fontWeight: 600,
                              bgcolor: `${themeColors.warning}1A`,
                              color: themeColors.warning,
                              border: `1px solid ${themeColors.warning}33`,
                            }}
                          />
                        )}
                      </Box>
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
                        {/* Main Answer Text */}
                        <Typography
                          variant="body2"
                          sx={{
                            color: msg.role === 'user' ? '#fff' : themeColors.textPrimary,
                            lineHeight: 1.5,
                            mb: bullets.length > 0 ? 1 : 0,
                          }}
                        >
                          {msg.text}
                        </Typography>

                        {/* Bullets List */}
                        {msg.role === 'assistant' && bullets.length > 0 && (
                          <List dense sx={{ py: 0 }}>
                            {bullets.map((bullet, bulletIndex) => (
                              <ListItem key={bulletIndex} sx={{ py: 0.25, px: 0 }}>
                                <ListItemText
                                  primary={`• ${bullet}`}
                                  sx={{
                                    '& .MuiListItemText-primary': {
                                      fontSize: '0.875rem',
                                      color: themeColors.textPrimary,
                                    }
                                  }}
                                />
                              </ListItem>
                            ))}
                          </List>
                        )}
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

                    {/* Citations, Playbook, and Similar Exceptions (for assistant messages only) */}
                    {msg.role === 'assistant' && (citations.length > 0 || recommendedPlaybook || similarExceptions.length > 0) && (
                      <Box
                        sx={{
                          maxWidth: '75%',
                          ml: '40px', // Align with message content
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                        }}
                      >
                        {/* Citations */}
                        {citations.length > 0 && (
                          <Box>
                            <Typography variant="caption" sx={{ color: themeColors.textTertiary, mb: 0.5, display: 'block' }}>
                              Sources:
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                              {citations.map((citation, citationIndex) => renderCitation(citation, citationIndex))}
                            </Box>
                          </Box>
                        )}

                        {/* Recommended Playbook */}
                        {recommendedPlaybook && (
                          <Accordion 
                            sx={{ 
                              bgcolor: 'transparent', 
                              boxShadow: 'none',
                              border: `1px solid ${themeColors.borderPrimary}`,
                              '&:before': { display: 'none' }
                            }}
                          >
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                <PlaybookIcon sx={{ fontSize: 16, color: themeColors.primary }} />
                                <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>
                                  Recommended: {recommendedPlaybook.name || recommendedPlaybook.playbook_id}
                                </Typography>
                                <Chip
                                  label={`${Math.round(recommendedPlaybook.confidence * 100)}% match`}
                                  size="small"
                                  sx={{
                                    height: 18,
                                    fontSize: '0.625rem',
                                    bgcolor: `${themeColors.success}1A`,
                                    color: themeColors.success,
                                  }}
                                />
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              {/* Rationale */}
                              <Typography variant="body2" sx={{ color: themeColors.textSecondary, mb: 1.5 }}>
                                {recommendedPlaybook.rationale}
                              </Typography>
                              
                              {/* Next Steps Summary - Show first 3 steps prominently */}
                              {(recommendedPlaybook.next_steps || recommendedPlaybook.steps)?.length > 0 && (
                                <Box sx={{ mb: 1.5 }}>
                                  <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5, color: themeColors.primary }}>
                                    Next Steps:
                                  </Typography>
                                  <List dense sx={{ py: 0 }}>
                                    {(recommendedPlaybook.next_steps || recommendedPlaybook.steps.slice(0, 3)).map((step: any, stepIndex: number) => (
                                      <ListItem key={stepIndex} sx={{ py: 0.25, px: 0 }}>
                                        <ListItemText
                                          primary={
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                              <Chip 
                                                label={step.step || stepIndex + 1} 
                                                size="small" 
                                                sx={{ 
                                                  height: 20, 
                                                  minWidth: 20,
                                                  bgcolor: themeColors.primary,
                                                  color: '#fff',
                                                  fontSize: '0.7rem'
                                                }} 
                                              />
                                              <Typography variant="body2">
                                                {step.text || step.name}
                                              </Typography>
                                              {step.action_type && (
                                                <Chip 
                                                  label={step.action_type} 
                                                  size="small" 
                                                  variant="outlined"
                                                  sx={{ 
                                                    height: 16, 
                                                    fontSize: '0.6rem',
                                                    borderColor: themeColors.textTertiary,
                                                    color: themeColors.textTertiary
                                                  }} 
                                                />
                                              )}
                                            </Box>
                                          }
                                        />
                                      </ListItem>
                                    ))}
                                  </List>
                                  {recommendedPlaybook.steps?.length > 3 && (
                                    <Typography variant="caption" sx={{ color: themeColors.textTertiary, ml: 1 }}>
                                      + {recommendedPlaybook.steps.length - 3} more steps
                                    </Typography>
                                  )}
                                </Box>
                              )}
                              
                              {/* Citation - Clickable Evidence */}
                              {recommendedPlaybook.citation && (
                                <Box sx={{ mb: 1 }}>
                                  <Typography variant="caption" sx={{ color: themeColors.textTertiary, mb: 0.5, display: 'block' }}>
                                    Evidence:
                                  </Typography>
                                  <Chip
                                    icon={<VisibilityIcon sx={{ fontSize: 14 }} />}
                                    label={
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <Typography variant="caption" sx={{ color: '#d32f2f', fontWeight: 600 }}>
                                          PLAYBOOK
                                        </Typography>
                                        <Typography variant="caption">
                                          {recommendedPlaybook.citation.title || recommendedPlaybook.name}
                                        </Typography>
                                      </Box>
                                    }
                                    size="small"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      // Navigate to playbook detail page
                                      const url = recommendedPlaybook.citation?.url || `/admin/playbooks`;
                                      navigate(url);
                                      setIsOpen(false);
                                    }}
                                    sx={{
                                      height: 24,
                                      fontSize: '0.7rem',
                                      bgcolor: '#ffebee',
                                      border: '1px solid #d32f2f33',
                                      cursor: 'pointer',
                                      '&:hover': {
                                        bgcolor: '#d32f2f1A',
                                        borderColor: '#d32f2f',
                                      },
                                    }}
                                  />
                                </Box>
                              )}
                              
                              <Alert severity="info" sx={{ mt: 1 }}>
                                <Typography variant="caption">
                                  This is a read-only view. Use the Exception Detail page to execute playbook steps.
                                </Typography>
                              </Alert>
                            </AccordionDetails>
                          </Accordion>
                        )}

                        {/* Similar Exceptions */}
                        {similarExceptions.length > 0 && (
                          <Box>
                            <Typography variant="caption" sx={{ color: themeColors.textTertiary, mb: 0.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <SimilarIcon sx={{ fontSize: 14 }} />
                              Similar Cases:
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                              {similarExceptions.slice(0, 3).map((similar, similarIndex) => (
                                <Chip
                                  key={similarIndex}
                                  label={
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                      <Typography variant="caption">
                                        {similar.exception_id}
                                      </Typography>
                                      <Badge 
                                        badgeContent={`${Math.round(similar.similarity_score * 100)}%`}
                                        sx={{
                                          '& .MuiBadge-badge': {
                                            fontSize: '0.5rem',
                                            height: 14,
                                            minWidth: 20,
                                          }
                                        }}
                                      />
                                    </Box>
                                  }
                                  size="small"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    navigate(`/exceptions/${similar.exception_id}`);
                                    setIsOpen(false);
                                  }}
                                  sx={{
                                    height: 24,
                                    fontSize: '0.7rem',
                                    bgcolor: `${themeColors.info}1A`,
                                    color: themeColors.info,
                                    border: `1px solid ${themeColors.info}33`,
                                    cursor: 'pointer',
                                    '&:hover': {
                                      bgcolor: `${themeColors.info}2A`,
                                      borderColor: themeColors.info,
                                    },
                                  }}
                                />
                              ))}
                            </Box>
                          </Box>
                        )}
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


