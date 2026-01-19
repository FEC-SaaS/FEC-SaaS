'use client';

import { PageHeader, Card, CardContent, CardHeader, CardTitle, StatCard } from '@fec-saas/ui';
import { BarChart3, TrendingUp, Users, DollarSign, PartyPopper, Building2 } from 'lucide-react';

const stats = [
  { title: 'Total Revenue (MTD)', value: '$124,563', icon: DollarSign, trend: { value: 12.5, positive: true, label: 'vs last month' } },
  { title: 'Total Customers', value: '15,234', icon: Users, trend: { value: 5.4, positive: true, label: 'vs last month' } },
  { title: 'Party Bookings', value: '248', icon: PartyPopper, trend: { value: 8.2, positive: true, label: 'vs last month' } },
  { title: 'Active Venues', value: '12', icon: Building2, description: 'across all locations' },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Performance metrics and business insights"
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard
            key={stat.title}
            title={stat.title}
            value={stat.value}
            icon={<stat.icon className="h-4 w-4" />}
            trend={stat.trend}
            description={stat.description}
          />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Revenue Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-[300px] items-center justify-center text-muted-foreground">
              <p>Revenue chart will be displayed here</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Booking Trends
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex h-[300px] items-center justify-center text-muted-foreground">
              <p>Booking trends chart will be displayed here</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
