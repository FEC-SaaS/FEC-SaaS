'use client';

import { PageHeader, Card, CardContent, Button, Input, Badge, DataTable } from '@fec-saas/ui';
import type { Column } from '@fec-saas/ui';
import { Plus, Search, Mail, Phone, Star } from 'lucide-react';
import { useState } from 'react';

interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  membershipTier: 'bronze' | 'silver' | 'gold' | 'platinum';
  totalVisits: number;
  totalSpent: number;
  lastVisit: string;
  joinDate: string;
}

const customers: Customer[] = [
  { id: '1', name: 'Sarah Johnson', email: 'sarah.j@email.com', phone: '(512) 555-1234', membershipTier: 'gold', totalVisits: 24, totalSpent: 1250, lastVisit: '2024-01-15', joinDate: '2023-03-10' },
  { id: '2', name: 'Michael Smith', email: 'msmith@email.com', phone: '(214) 555-5678', membershipTier: 'silver', totalVisits: 12, totalSpent: 650, lastVisit: '2024-01-18', joinDate: '2023-06-22' },
  { id: '3', name: 'Emily Williams', email: 'emily.w@email.com', phone: '(713) 555-9012', membershipTier: 'platinum', totalVisits: 48, totalSpent: 3200, lastVisit: '2024-01-20', joinDate: '2022-08-15' },
  { id: '4', name: 'David Brown', email: 'dbrown@email.com', phone: '(210) 555-3456', membershipTier: 'bronze', totalVisits: 5, totalSpent: 275, lastVisit: '2024-01-10', joinDate: '2023-11-05' },
];

const tierColors = {
  bronze: 'secondary',
  silver: 'secondary',
  gold: 'warning',
  platinum: 'info',
} as const;

export default function CustomersPage() {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: Column<Customer>[] = [
    { key: 'name', header: 'Customer', cell: (c) => (
      <div>
        <p className="font-medium">{c.name}</p>
        <p className="text-sm text-muted-foreground">{c.email}</p>
      </div>
    )},
    { key: 'phone', header: 'Phone', cell: (c) => c.phone },
    { key: 'membershipTier', header: 'Tier', cell: (c) => <Badge variant={tierColors[c.membershipTier]}>{c.membershipTier}</Badge> },
    { key: 'totalVisits', header: 'Visits', cell: (c) => c.totalVisits },
    { key: 'totalSpent', header: 'Total Spent', cell: (c) => `$${c.totalSpent.toLocaleString()}` },
    { key: 'lastVisit', header: 'Last Visit', cell: (c) => c.lastVisit },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        description="Manage customer profiles and memberships"
        actions={<Button><Plus className="mr-2 h-4 w-4" />Add Customer</Button>}
      />
      <Card>
        <CardContent className="pt-6">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>
      <DataTable columns={columns} data={filteredCustomers} keyExtractor={(c) => c.id} />
    </div>
  );
}
