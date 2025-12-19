/**
 * Tests for ConfirmDialog component
 * 
 * P11-4: Tests for confirmation dialog behavior
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ConfirmDialog from '../ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders dialog when open', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('Test Title')).toBeDefined()
    expect(screen.getByText('Test Message')).toBeDefined()
  })

  it('does not render when closed', () => {
    render(
      <ConfirmDialog
        open={false}
        title="Test Title"
        message="Test Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.queryByText('Test Title')).toBeNull()
  })

  it('calls onConfirm when confirm button clicked', async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />
    )

    const confirmButton = screen.getByText('Confirm')
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledTimes(1)
    })
  })

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    )

    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('shows loading state when loading', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={true}
      />
    )

    const confirmButton = screen.getByText('Confirm')
    expect(confirmButton).toBeDisabled()
  })

  it('shows destructive styling when destructive', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        destructive={true}
      />
    )

    const confirmButton = screen.getByText('Confirm')
    expect(confirmButton).toHaveAttribute('color', 'error')
  })

  it('uses custom labels when provided', () => {
    render(
      <ConfirmDialog
        open={true}
        title="Test Title"
        message="Test Message"
        confirmLabel="Yes, Delete"
        cancelLabel="No, Keep"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('Yes, Delete')).toBeDefined()
    expect(screen.getByText('No, Keep')).toBeDefined()
  })
})

