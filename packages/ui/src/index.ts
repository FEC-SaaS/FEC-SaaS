/**
 * FEC SaaS UI Components
 *
 * Shared UI components based on shadcn/ui patterns
 */

// Utility functions
export {
  cn,
  formatCurrency,
  formatPercentage,
  formatNumber,
  formatDate,
  formatTime,
  getInitials,
} from './lib/utils';

// Components
export { Button, type ButtonProps } from './components/button';
export { Input, type InputProps } from './components/input';
export { Label } from './components/label';
export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './components/card';
export { Badge, type BadgeProps } from './components/badge';
export { Alert, AlertDescription, AlertTitle } from './components/alert';
export { Separator } from './components/separator';
export { Skeleton } from './components/skeleton';
export { Spinner } from './components/spinner';

// Layout components
export { Sidebar, SidebarItem, SidebarSection } from './components/sidebar';
export { PageHeader } from './components/page-header';
export { StatCard } from './components/stat-card';
export { DataTable, type Column } from './components/data-table';

// Hooks
export { useToast, toast } from './hooks/use-toast';
