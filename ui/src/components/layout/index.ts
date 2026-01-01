/**
 * Layout Components - Base44-quality Enterprise Layout System
 * 
 * Provides consistent page structure and spacing across all pages.
 * 
 * RECOMMENDED USAGE (Wave 1 primitives):
 *   import { PageShell, Section, KpiGrid } from '../components/layout'
 * 
 *   <PageShell title="..." subtitle="..." actions={...}>
 *     <AlertBanner />
 *     <KpiGrid>
 *       <StatCard />
 *     </KpiGrid>
 *     <Section title="...">
 *       <DataTable />
 *     </Section>
 *   </PageShell>
 * 
 * LEGACY (still supported):
 *   PageContainer, PageHeader, SectionBlock, CardGrid
 */

// Wave 1 Layout Primitives (Base44-style)
export { default as PageShell } from './PageShell'
export type { PageShellProps } from './PageShell'

export { default as Section } from './Section'
export type { SectionProps } from './Section'

export { default as KpiGrid } from './KpiGrid'
export type { KpiGridProps } from './KpiGrid'

// Legacy components (still supported for backward compatibility)
export { default as PageContainer } from './PageContainer'
export type { PageContainerProps } from './PageContainer'

export { default as PageHeader } from './PageHeader'
export type { PageHeaderProps } from './PageHeader'

export { default as SectionBlock } from './SectionBlock'
export type { SectionBlockProps } from './SectionBlock'

export { default as CardGrid } from './CardGrid'
export type { CardGridProps } from './CardGrid'
