import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
  Chip,
  MenuItem,
  Select,
  FormControl,
  InputBase,
  Avatar,
  Divider,
  Badge,
  Tooltip,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import DashboardIcon from '@mui/icons-material/Dashboard'
import SupervisorAccountIcon from '@mui/icons-material/SupervisorAccount'
import SettingsIcon from '@mui/icons-material/Settings'
import BuildIcon from '@mui/icons-material/Build'
import SearchIcon from '@mui/icons-material/Search'
import NotificationsIcon from '@mui/icons-material/Notifications'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import MemoryIcon from '@mui/icons-material/Memory'
import BugReportIcon from '@mui/icons-material/BugReport'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import HistoryIcon from '@mui/icons-material/History'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import ScienceIcon from '@mui/icons-material/Science'
import { useTenant } from '../hooks/useTenant.tsx'
import { themeColors } from '../theme/theme.ts'
import { useThemeMode } from '../theme/ThemeModeProvider.tsx'
import { AICopilotDock } from '../components/copilot'
import { isOpsEnabled, isAdminEnabled } from '../utils/featureFlags'

const DRAWER_WIDTH = 256

interface AppLayoutProps {
  children: React.ReactNode
}

interface NavItem {
  label: string
  to: string
  icon: React.ReactElement
  section?: string // 'main' | 'ops' | 'admin'
}

interface NavSection {
  label?: string
  subtitle?: string
  items: NavItem[]
}

// Build nav items conditionally based on environment flags
// This function is called inside the component to ensure it re-evaluates
const getNavSections = (): NavSection[] => {
  // Debug logging in development
  if (import.meta.env.DEV) {
    console.log('[AppLayout] Feature flags:', {
      VITE_OPS_ENABLED: import.meta.env.VITE_OPS_ENABLED,
      VITE_ADMIN_ENABLED: import.meta.env.VITE_ADMIN_ENABLED,
      isOpsEnabled: isOpsEnabled(),
      isAdminEnabled: isAdminEnabled(),
    })
  }

  const sections: NavSection[] = [
    {
      label: 'Main',
      items: [
        {
          label: 'Exceptions',
          to: '/exceptions',
          icon: <DashboardIcon />,
          section: 'main',
        },
        {
          label: 'Supervisor',
          to: '/supervisor',
          icon: <SupervisorAccountIcon />,
          section: 'main',
        },
      ],
    },
  ]

  // Add Ops section if enabled
  if (isOpsEnabled()) {
    sections.push({
      label: 'Ops',
      subtitle: 'Operational monitoring & safe recovery',
      items: [
        {
          label: 'Overview',
          to: '/ops',
          icon: <DashboardIcon />,
          section: 'ops',
        },
        {
          label: 'Workers',
          to: '/ops/workers',
          icon: <BugReportIcon />,
          section: 'ops',
        },
        {
          label: 'SLA',
          to: '/ops/sla',
          icon: <BugReportIcon />,
          section: 'ops',
        },
        {
          label: 'DLQ',
          to: '/ops/dlq',
          icon: <BugReportIcon />,
          section: 'ops',
        },
        {
          label: 'Alerts',
          to: '/ops/alerts',
          icon: <NotificationsIcon />,
          section: 'ops',
        },
        {
          label: 'Alert History',
          to: '/ops/alerts/history',
          icon: <HistoryIcon />,
          section: 'ops',
        },
        {
          label: 'Usage',
          to: '/ops/usage',
          icon: <MemoryIcon />,
          section: 'ops',
        },
        {
          label: 'Rate Limits',
          to: '/ops/rate-limits',
          icon: <SettingsIcon />,
          section: 'ops',
        },
        {
          label: 'Reports',
          to: '/ops/reports',
          icon: <BugReportIcon />,
          section: 'ops',
        },
      ],
    })
  }

  // Add Admin section if enabled
  if (isAdminEnabled()) {
    sections.push({
      label: 'Admin',
      subtitle: 'Governance, approvals, and configuration control',
      items: [
        {
          label: 'Overview',
          to: '/admin',
          icon: <AdminPanelSettingsIcon />,
          section: 'admin',
        },
        {
          label: 'Config Changes',
          to: '/admin/config-changes',
          icon: <SettingsIcon />,
          section: 'admin',
        },
        {
          label: 'Packs',
          to: '/admin/packs',
          icon: <SettingsIcon />,
          section: 'admin',
        },
        {
          label: 'Playbooks',
          to: '/admin/playbooks',
          icon: <SettingsIcon />,
          section: 'admin',
        },
        {
          label: 'Tools',
          to: '/admin/tools',
          icon: <BuildIcon />,
          section: 'admin',
        },
        {
          label: 'Demo Settings',
          to: '/admin/demo',
          icon: <ScienceIcon />,
          section: 'admin',
        },
      ],
    })
  }

  return sections
}

// Sample tenant/domain options for demo (can be replaced with API call later)
const SAMPLE_TENANTS = ['tenant_001', 'tenant_002', 'TENANT_A', 'TENANT_FINANCE_001', 'TENANT_FIANNCE_001']
const SAMPLE_DOMAINS = ['TestDomain', 'Finance', 'Healthcare', 'Retail']

export default function AppLayout({ children }: AppLayoutProps) {
  const theme = useTheme()
  const location = useLocation()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [mobileOpen, setMobileOpen] = useState(false)
  const { tenantId, domain, setTenantId, setDomain } = useTenant()
  const { mode, toggleMode } = useThemeMode()

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const handleTenantChange = (event: { target: { value: string } }) => {
    setTenantId(event.target.value || null)
  }

  const handleDomainChange = (event: { target: { value: string } }) => {
    setDomain(event.target.value || null)
  }

  const drawer = (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: themeColors.bgSecondary,
        borderRight: '1px solid',
        borderColor: themeColors.borderPrimary,
      }}
    >
      {/* Logo/Brand Section */}
      <Box
        sx={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          px: 3,
          borderBottom: '1px solid',
          borderColor: themeColors.borderPrimary,
        }}
      >
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 1,
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 4px 14px 0 ${themeColors.primaryGlow}`,
          }}
        >
          <MemoryIcon sx={{ fontSize: 20, color: 'white' }} />
        </Box>
        <Typography
          variant="h6"
          component="div"
          sx={{
            ml: 1.5,
            fontWeight: 700,
            fontSize: '1.125rem',
            color: 'white',
            letterSpacing: '-0.02em',
          }}
        >
          Sentin<span style={{ color: theme.palette.primary.main }}>AI</span>
        </Typography>
      </Box>

      {/* Navigation */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          py: 1.5,
          px: 1,
        }}
      >
        {getNavSections().map((section, sectionIndex) => (
          <Box key={sectionIndex} sx={{ mb: section.label ? 2 : 0 }}>
            {section.label && (
              <Box sx={{ px: 1.5, py: 0.5 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: themeColors.textTertiary,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    display: 'block',
                  }}
                >
                  {section.label}
                </Typography>
                {section.subtitle && (
                  <Typography
                    variant="caption"
                    sx={{
                      color: themeColors.textTertiary,
                      fontSize: '0.65rem',
                      fontWeight: 400,
                      display: 'block',
                      mt: 0.25,
                      opacity: 0.7,
                    }}
                  >
                    {section.subtitle}
                  </Typography>
                )}
              </Box>
            )}
            <List sx={{ py: 0 }}>
              {section.items.map((item) => {
                const isActive =
                  location.pathname === item.to || location.pathname.startsWith(item.to + '/')
                return (
                  <ListItemButton
                    key={item.to}
                    component={Link}
                    to={item.to}
                    onClick={() => {
                      // Close mobile drawer when navigating
                      if (isMobile) {
                        setMobileOpen(false)
                      }
                    }}
                    selected={isActive}
                    sx={{
                      mb: 0.5,
                      borderRadius: 2,
                      px: 1.5,
                      py: 1.5,
                      '&:hover': {
                        backgroundColor: themeColors.bgTertiary,
                      },
                      '&.Mui-selected': {
                        backgroundColor: `${themeColors.primary}1A`, // 10% opacity
                        border: '1px solid',
                        borderColor: `${themeColors.primary}33`, // 20% opacity
                        boxShadow: `0 1px 3px 0 ${themeColors.primary}1A`,
                        '&:hover': {
                          backgroundColor: `${themeColors.primary}26`, // 15% opacity
                        },
                      },
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        color: isActive ? 'primary.main' : themeColors.textTertiary,
                        minWidth: 40,
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{
                        fontSize: '0.875rem',
                        fontWeight: isActive ? 500 : 400,
                        color: isActive ? themeColors.textPrimary : themeColors.textSecondary,
                      }}
                    />
                    {isActive && (
                      <Box
                        sx={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          bgcolor: 'primary.main',
                          ml: 'auto',
                          boxShadow: `0 0 8px ${themeColors.primary}80`,
                        }}
                      />
                    )}
                  </ListItemButton>
                )
              })}
            </List>
          </Box>
        ))}
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Box
        component="nav"
        sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}
        aria-label="navigation"
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile
          }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              backgroundColor: themeColors.bgSecondary,
              borderRight: '1px solid',
              borderColor: themeColors.borderPrimary,
            },
          }}
        >
          {drawer}
        </Drawer>
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              backgroundColor: themeColors.bgSecondary,
              borderRight: '1px solid',
              borderColor: themeColors.borderPrimary,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: '100vh',
          backgroundColor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <AppBar
          position="sticky"
          sx={{
            zIndex: (theme) => theme.zIndex.drawer + 1,
            height: 64,
            backgroundColor: 'background.paper',
            backdropFilter: 'blur(12px)',
            borderBottom: '1px solid',
            borderColor: 'divider',
            boxShadow: 'none',
          }}
        >
        <Toolbar sx={{ px: { xs: 2, md: 4 }, justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { md: 'none' }, color: 'text.secondary' }}
            >
              <MenuIcon />
            </IconButton>

            {/* Tenant Selector */}
            <FormControl
              size="small"
              sx={{
                minWidth: 140,
                '& .MuiOutlinedInput-root': {
                  border: 'none',
                  '& fieldset': {
                    border: 'none',
                  },
                  '&:hover fieldset': {
                    border: 'none',
                  },
                  '&.Mui-focused fieldset': {
                    border: 'none',
                  },
                },
              }}
            >
              <Select
                value={tenantId || ''}
                onChange={handleTenantChange}
                displayEmpty
                renderValue={(value) => (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                      Tenant:
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem', color: 'text.primary' }}>
                      {value || 'Global FinCo'}
                    </Typography>
                    <KeyboardArrowDownIcon sx={{ fontSize: 16, color: 'text.secondary', ml: 0.5 }} />
                  </Box>
                )}
                sx={{
                  color: 'text.primary',
                  fontSize: '0.875rem',
                  '& .MuiSelect-icon': {
                    display: 'none',
                  },
                  '&:hover': {
                    color: 'text.primary',
                  },
                  transition: 'color 0.2s',
                }}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      mt: 0.5,
                    },
                  },
                }}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {SAMPLE_TENANTS.map((tenant) => (
                  <MenuItem key={tenant} value={tenant} sx={{ color: 'text.primary' }}>
                    {tenant}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Vertical Separator */}
            <Divider
              orientation="vertical"
              flexItem
              sx={{ borderColor: 'divider', height: 20, alignSelf: 'center' }}
            />

            {/* Domain Selector */}
            <FormControl
              size="small"
              sx={{
                minWidth: 160,
                '& .MuiOutlinedInput-root': {
                  border: 'none',
                  '& fieldset': {
                    border: 'none',
                  },
                  '&:hover fieldset': {
                    border: 'none',
                  },
                  '&.Mui-focused fieldset': {
                    border: 'none',
                  },
                },
              }}
            >
              <Select
                value={domain || ''}
                onChange={handleDomainChange}
                displayEmpty
                renderValue={(value) => (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                      Domain:
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem', color: 'text.primary' }}>
                      {value || 'Capital Markets'}
                    </Typography>
                    <KeyboardArrowDownIcon sx={{ fontSize: 16, color: 'text.secondary', ml: 0.5 }} />
                  </Box>
                )}
                sx={{
                  color: 'text.primary',
                  fontSize: '0.875rem',
                  '& .MuiSelect-icon': {
                    display: 'none',
                  },
                  '&:hover': {
                    color: 'text.primary',
                  },
                  transition: 'color 0.2s',
                }}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      mt: 0.5,
                    },
                  },
                }}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {SAMPLE_DOMAINS.map((dom) => (
                  <MenuItem key={dom} value={dom} sx={{ color: 'text.primary' }}>
                    {dom}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Search Input */}
            <Box
              sx={{
                position: 'relative',
                display: { xs: 'none', md: 'block' },
                width: 256,
                transition: 'width 0.3s',
                '&:focus-within': {
                  width: 320,
                },
              }}
            >
              <Box
                sx={{
                  position: 'absolute',
                  left: 12,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'text.secondary',
                  pointerEvents: 'none',
                }}
              >
                <SearchIcon sx={{ fontSize: 16 }} />
              </Box>
              <InputBase
                placeholder="Search exceptions, entities..."
                sx={{
                  width: '100%',
                  pl: 4.5,
                  pr: 2,
                  py: 1,
                  fontSize: '0.875rem',
                  backgroundColor: 'action.hover',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 20,
                  color: 'text.primary',
                  '&:focus': {
                    borderColor: 'primary.main',
                  },
                  transition: 'border-color 0.2s',
                }}
              />
            </Box>

            {/* Theme Toggle */}
            <Tooltip title={mode === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}>
              <IconButton
                onClick={toggleMode}
                data-testid="theme-toggle"
                sx={{
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary', backgroundColor: 'action.hover' },
                  transition: 'all 0.2s',
                }}
              >
                {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
              </IconButton>
            </Tooltip>

            {/* Notifications */}
            <IconButton
              sx={{
                color: 'text.secondary',
                '&:hover': { color: 'text.primary', backgroundColor: 'action.hover' },
                transition: 'all 0.2s',
              }}
            >
              <Badge badgeContent={3} color="error">
                <NotificationsIcon />
              </Badge>
            </IconButton>

            {/* User Profile & ENV Badge */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                pl: 2,
                borderLeft: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Box sx={{ display: { xs: 'none', md: 'flex' }, flexDirection: 'column', alignItems: 'flex-end' }}>
                <Typography variant="body2" sx={{ fontSize: '0.875rem', fontWeight: 500, color: 'text.primary' }}>
                  User Name
                </Typography>
                <Chip
                  label={`ENV: ${import.meta.env.MODE.toUpperCase()}`}
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: '0.625rem',
                    fontFamily: 'monospace',
                    fontWeight: 500,
                    bgcolor: import.meta.env.MODE === 'development' ? 'rgba(37, 99, 235, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                    color: import.meta.env.MODE === 'development' ? 'primary.main' : 'success.main',
                    border: `1px solid ${import.meta.env.MODE === 'development' ? 'rgba(37, 99, 235, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
                  }}
                />
              </Box>
              <Avatar
                sx={{
                  width: 36,
                  height: 36,
                  bgcolor: 'primary.main',
                  border: '1px solid',
                  borderColor: 'divider',
                  cursor: 'pointer',
                  '&:hover': { borderColor: 'primary.main' },
                  transition: 'border-color 0.2s',
                }}
              >
                U
              </Avatar>
            </Box>
          </Box>
        </Toolbar>
      </AppBar>
          <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: { xs: 2, sm: 3, md: 4 },
          }}
        >
          {children}
        </Box>

        {/* AI Co-Pilot Dock - Available globally across all pages */}
        <AICopilotDock />
        
        {/* Dev-only debug overlay - disabled after design system verification */}
        {/* <StyleProbe /> */}
      </Box>
    </Box>
  )
}
