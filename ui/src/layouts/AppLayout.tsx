import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  AppBar,
  Box,
  CssBaseline,
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
  InputLabel,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import DashboardIcon from '@mui/icons-material/Dashboard'
import SupervisorAccountIcon from '@mui/icons-material/SupervisorAccount'
import SettingsIcon from '@mui/icons-material/Settings'
import { useTenant } from '../hooks/useTenant.tsx'

const DRAWER_WIDTH = 240

interface AppLayoutProps {
  children: React.ReactNode
}

interface NavItem {
  label: string
  to: string
  icon: React.ReactElement
}

const navItems: NavItem[] = [
  {
    label: 'Exceptions',
    to: '/exceptions',
    icon: <DashboardIcon />,
  },
  {
    label: 'Supervisor',
    to: '/supervisor',
    icon: <SupervisorAccountIcon />,
  },
  {
    label: 'Config',
    to: '/config',
    icon: <SettingsIcon />,
  },
]

// Sample tenant/domain options for demo (can be replaced with API call later)
const SAMPLE_TENANTS = ['tenant_001', 'tenant_002', 'TENANT_A', 'TENANT_FINANCE_001']
const SAMPLE_DOMAINS = ['TestDomain', 'Finance', 'Healthcare', 'Retail']

export default function AppLayout({ children }: AppLayoutProps) {
  const theme = useTheme()
  const location = useLocation()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [mobileOpen, setMobileOpen] = useState(false)
  const { tenantId, domain, setTenantId, setDomain } = useTenant()

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
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          Exception Platform
        </Typography>
      </Toolbar>
      <List>
        {navItems.map((item) => {
          const isActive = location.pathname === item.to || location.pathname.startsWith(item.to + '/')
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
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                },
                '&.Mui-selected': {
                  backgroundColor: theme.palette.action.selected,
                  '&:hover': {
                    backgroundColor: theme.palette.action.selected,
                  },
                },
              }}
            >
              <ListItemIcon
                sx={{
                  color: isActive ? theme.palette.primary.main : 'inherit',
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          )
        })}
      </List>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Agentic Exception Platform
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Tenant Selector */}
            <FormControl
              size="small"
              sx={{
                minWidth: 120,
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: 1,
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.23)',
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                },
                display: { xs: 'none', sm: 'flex' },
              }}
            >
              <InputLabel sx={{ color: 'white' }}>Tenant</InputLabel>
              <Select
                value={tenantId || ''}
                onChange={handleTenantChange}
                label="Tenant"
                sx={{
                  color: 'white',
                  '& .MuiSvgIcon-root': {
                    color: 'white',
                  },
                }}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {SAMPLE_TENANTS.map((tenant) => (
                  <MenuItem key={tenant} value={tenant}>
                    {tenant}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Domain Selector */}
            <FormControl
              size="small"
              sx={{
                minWidth: 120,
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: 1,
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.23)',
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.5)',
                },
                display: { xs: 'none', sm: 'flex' },
              }}
            >
              <InputLabel sx={{ color: 'white' }}>Domain</InputLabel>
              <Select
                value={domain || ''}
                onChange={handleDomainChange}
                label="Domain"
                sx={{
                  color: 'white',
                  '& .MuiSvgIcon-root': {
                    color: 'white',
                  },
                }}
              >
                <MenuItem value="">
                  <em>None</em>
                </MenuItem>
                {SAMPLE_DOMAINS.map((dom) => (
                  <MenuItem key={dom} value={dom}>
                    {dom}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Mobile view: show text only */}
            <Typography variant="body2" sx={{ display: { xs: 'block', sm: 'none' } }}>
              {tenantId ? `T: ${tenantId}` : 'T: [TBD]'} | {domain ? `D: ${domain}` : 'D: [TBD]'}
            </Typography>

            <Chip
              label={`ENV: ${import.meta.env.MODE.toUpperCase()}`}
              size="small"
              color={import.meta.env.MODE === 'development' ? 'primary' : 'default'}
              sx={{ fontWeight: 'bold' }}
            />
          </Box>
        </Toolbar>
      </AppBar>
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
          p: { xs: 2, sm: 3 }, // Responsive padding: 2 on mobile, 3 on desktop
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          minHeight: '100vh',
          backgroundColor: theme.palette.background.default,
        }}
      >
        <Toolbar /> {/* Spacer for AppBar */}
        {children}
      </Box>
    </Box>
  )
}
