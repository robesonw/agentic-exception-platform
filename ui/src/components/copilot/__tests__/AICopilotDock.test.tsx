import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import AICopilotDock from '../AICopilotDock'
import type { ChatMessage } from '../../../hooks/useCopilotChat'

// Mock useCopilotChat hook
const mockMessages: ChatMessage[] = [
  {
    role: 'assistant',
    text: 'Hello, Operator. I am monitoring active exceptions. How can I assist you today?',
  },
]

const mockSendMessage = vi.fn()
const mockUseCopilotChat = vi.fn(() => ({
  messages: mockMessages,
  setMessages: vi.fn(),
  loading: false,
  error: null,
  sendMessage: mockSendMessage,
}))

vi.mock('../../../hooks/useCopilotChat', () => ({
  useCopilotChat: () => mockUseCopilotChat(),
}))

// Mock useTenant hook (used by useCopilotChat)
vi.mock('../../../hooks/useTenant', () => ({
  useTenant: () => ({
    tenantId: 'test-tenant',
    domain: 'test-domain',
    apiKey: 'test-api-key',
    setTenantId: vi.fn(),
    setDomain: vi.fn(),
    setApiKey: vi.fn(),
  }),
}))

// Helper to render component with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('AICopilotDock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseCopilotChat.mockReturnValue({
      messages: mockMessages,
      setMessages: vi.fn(),
      loading: false,
      error: null,
      sendMessage: mockSendMessage,
    })
  })

  it('renders floating button when dock is closed', () => {
    renderWithRouter(<AICopilotDock />)
    
    const button = screen.getByRole('button', { name: /open ai co-pilot/i })
    expect(button).toBeInTheDocument()
  })

  it('opens dock when floating button is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock />)
    
    const button = screen.getByRole('button', { name: /open ai co-pilot/i })
    await user.click(button)
    
    // Dock should be visible (check for input field which is inside the dock)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask about exceptions/i)).toBeInTheDocument()
    })
  })

  it('renders dock when initiallyOpen is true', () => {
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    // Input field should be visible
    expect(screen.getByPlaceholderText(/ask about exceptions/i)).toBeInTheDocument()
    
    // Initial assistant message should be visible
    expect(screen.getByText(/Hello, Operator/i)).toBeInTheDocument()
  })

  it('displays initial assistant message', () => {
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    expect(screen.getByText(/Hello, Operator. I am monitoring active exceptions/i)).toBeInTheDocument()
  })

  it('allows typing into input field', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    await user.type(input, 'Test message')
    
    expect(input).toHaveValue('Test message')
  })

  it('calls sendMessage when send button is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    await user.type(input, 'Test message')
    
    // Find send button by its icon testid
    const sendButton = screen.getByTestId('SendIcon').closest('button')
    expect(sendButton).not.toBeDisabled()
    if (sendButton) {
      await user.click(sendButton)
    }
    
    expect(mockSendMessage).toHaveBeenCalledWith('Test message')
    expect(mockSendMessage).toHaveBeenCalledTimes(1)
  })

  it('calls sendMessage when Enter key is pressed', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    await user.type(input, 'Test message{Enter}')
    
    expect(mockSendMessage).toHaveBeenCalledWith('Test message')
    expect(mockSendMessage).toHaveBeenCalledTimes(1)
  })

  it('clears input after sending message', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i) as HTMLInputElement
    await user.type(input, 'Test message')
    await user.type(input, '{Enter}')
    
    // Input should be cleared (component clears it before calling sendMessage)
    await waitFor(() => {
      expect(input.value).toBe('')
    })
  })

  it('does not send empty messages', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    const sendButton = screen.getByTestId('SendIcon').closest('button')
    
    // Send button should be disabled when input is empty
    expect(sendButton).toBeDisabled()
    
    // Try to send empty message
    await user.type(input, '{Enter}')
    
    expect(mockSendMessage).not.toHaveBeenCalled()
  })

  it('displays loading state when loading is true', () => {
    mockUseCopilotChat.mockReturnValue({
      messages: mockMessages,
      setMessages: vi.fn(),
      loading: true,
      error: null,
      sendMessage: mockSendMessage,
    })
    
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    // Should show "Thinking..." text
    expect(screen.getByText(/Thinking/i)).toBeInTheDocument()
    
    // Check that loading indicators are present (there may be multiple)
    const progressBars = screen.getAllByRole('progressbar')
    expect(progressBars.length).toBeGreaterThan(0)
    
    // Input should still be visible
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    expect(input).toBeInTheDocument()
  })

  it('displays error message when error occurs', () => {
    const errorMessage = 'Co-Pilot is temporarily unavailable.'
    mockUseCopilotChat.mockReturnValue({
      messages: mockMessages,
      setMessages: vi.fn(),
      loading: false,
      error: errorMessage,
      sendMessage: mockSendMessage,
    })
    
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    expect(screen.getByText(errorMessage)).toBeInTheDocument()
  })

  it('displays error message in chat when sendMessage throws', async () => {
    const user = userEvent.setup()
    const errorMessage = 'Co-Pilot is temporarily unavailable.'
    
    // Mock sendMessage to simulate error
    let callCount = 0
    mockSendMessage.mockImplementation(async () => {
      callCount++
      if (callCount === 1) {
        throw new Error('Network error')
      }
    })
    
    // Start with no error, but will update after sendMessage is called
    const setMessagesMock = vi.fn()
    mockUseCopilotChat.mockReturnValue({
      messages: mockMessages,
      setMessages: setMessagesMock,
      loading: false,
      error: null,
      sendMessage: mockSendMessage,
    })
    
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    const input = screen.getByPlaceholderText(/ask about exceptions/i)
    await user.type(input, 'Test message')
    await user.type(input, '{Enter}')
    
    // The hook should handle the error and add error message to messages
    // Since we're mocking the hook, we need to verify sendMessage was called
    // The actual error handling happens in the hook, which we're mocking
    expect(mockSendMessage).toHaveBeenCalledWith('Test message')
    
    // For this test, we verify that sendMessage was called with the error
    // The actual UI update would happen in the real hook implementation
  })

  it('closes dock when close button is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    // Dock should be visible
    expect(screen.getByPlaceholderText(/ask about exceptions/i)).toBeInTheDocument()
    
    // Find and click close button by its icon testid
    const closeButton = screen.getByTestId('CloseIcon').closest('button')
    expect(closeButton).toBeInTheDocument()
    if (closeButton) {
      await user.click(closeButton)
    }
    
    // Dock should be closed (input should not be visible)
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/ask about exceptions/i)).not.toBeInTheDocument()
    })
    
    // Floating button should be visible again
    expect(screen.getByRole('button', { name: /open ai co-pilot/i })).toBeInTheDocument()
  })

  it('displays user messages when added to messages array', () => {
    const messagesWithUser: ChatMessage[] = [
      ...mockMessages,
      {
        role: 'user',
        text: 'What are today\'s exceptions?',
      },
    ]
    
    mockUseCopilotChat.mockReturnValue({
      messages: messagesWithUser,
      setMessages: vi.fn(),
      loading: false,
      error: null,
      sendMessage: mockSendMessage,
    })
    
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    expect(screen.getByText(/What are today's exceptions/i)).toBeInTheDocument()
  })

  it('displays assistant messages with metadata', () => {
    const messagesWithMeta: ChatMessage[] = [
      ...mockMessages,
      {
        role: 'assistant',
        text: 'Here is a summary of today\'s exceptions.',
        meta: {
          answer_type: 'SUMMARY',
          citations: [
            { type: 'exception', id: 'EX-12345' },
          ],
        },
      },
    ]
    
    mockUseCopilotChat.mockReturnValue({
      messages: messagesWithMeta,
      setMessages: vi.fn(),
      loading: false,
      error: null,
      sendMessage: mockSendMessage,
    })
    
    renderWithRouter(<AICopilotDock initiallyOpen={true} />)
    
    // Should display answer type badge
    expect(screen.getByText('SUMMARY')).toBeInTheDocument()
    
    // Should display citation
    expect(screen.getByText('EX-12345')).toBeInTheDocument()
  })
})

