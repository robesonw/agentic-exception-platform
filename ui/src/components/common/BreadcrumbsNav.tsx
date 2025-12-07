/**
 * Breadcrumbs Navigation Component
 * 
 * Provides consistent breadcrumb navigation for detail pages.
 * Uses MUI Breadcrumbs with react-router-dom Link integration.
 */

import { Breadcrumbs, Link, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'

export interface BreadcrumbItem {
  /** Display label for the breadcrumb */
  label: string
  /** Optional route path (if provided, breadcrumb is clickable) */
  to?: string
}

export interface BreadcrumbsNavProps {
  /** Array of breadcrumb items */
  items: BreadcrumbItem[]
  /** Additional CSS styling */
  sx?: Record<string, unknown>
}

/**
 * Breadcrumbs Navigation Component
 * 
 * Renders a breadcrumb trail with clickable links for navigation.
 * The last item (current page) is rendered as plain text, not a link.
 */
export default function BreadcrumbsNav({ items, sx }: BreadcrumbsNavProps) {
  if (!items || items.length === 0) {
    return null
  }

  return (
    <Breadcrumbs
      aria-label="breadcrumb navigation"
      sx={{ mb: 2, ...sx }}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1

        if (isLast || !item.to) {
          // Last item or item without 'to' prop - render as plain text
          return (
            <Typography
              key={index}
              color="text.primary"
              sx={{ fontWeight: isLast ? 500 : 400 }}
            >
              {item.label}
            </Typography>
          )
        }

        // Clickable breadcrumb item
        return (
          <Link
            key={index}
            component={RouterLink}
            to={item.to}
            color="inherit"
            underline="hover"
            sx={{
              '&:hover': {
                textDecoration: 'underline',
              },
            }}
          >
            {item.label}
          </Link>
        )
      })}
    </Breadcrumbs>
  )
}

