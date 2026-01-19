'use client';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  StatCard,
  Badge,
} from '@fec-saas/ui';
import {
  Users,
  DollarSign,
  PartyPopper,
  TrendingUp,
  Building2,
  Calendar,
} from 'lucide-react';

// Mock data for dashboard stats
const stats = [
  {
    title: 'Total Revenue',
    value: '$124,563',
    icon: DollarSign,
    trend: { value: 12.5, positive: true, label: 'from last month' },
  },
  {
    title: 'Active Venues',
    value: '12',
    icon: Building2,
    trend: { value: 2, positive: true, label: 'new this quarter' },
  },
  {
    title: 'Party Bookings',
    value: '248',
    icon: PartyPopper,
    trend: { value: 8.2, positive: true, label: 'from last month' },
  },
  {
    title: 'Total Customers',
    value: '15,234',
    icon: Users,
    trend: { value: 5.4, positive: true, label: 'from last month' },
  },
];

const recentBookings = [
  {
    id: '1',
    customerName: 'Johnson Family',
    package: 'Ultimate Birthday Bash',
    venue: 'FunZone Downtown',
    date: '2024-01-25',
    status: 'confirmed',
    amount: 450,
  },
  {
    id: '2',
    customerName: 'Smith Party',
    package: 'Classic Fun Package',
    venue: 'Adventure Park',
    date: '2024-01-26',
    status: 'pending',
    amount: 275,
  },
  {
    id: '3',
    customerName: 'Williams Event',
    package: 'VIP Experience',
    venue: 'FunZone Mall',
    date: '2024-01-27',
    status: 'confirmed',
    amount: 650,
  },
  {
    id: '4',
    customerName: 'Brown Celebration',
    package: 'Classic Fun Package',
    venue: 'FunZone Downtown',
    date: '2024-01-28',
    status: 'pending',
    amount: 275,
  },
];

const topVenues = [
  { name: 'FunZone Downtown', revenue: 45230, bookings: 89, growth: 15.2 },
  { name: 'Adventure Park', revenue: 38750, bookings: 72, growth: 8.5 },
  { name: 'FunZone Mall', revenue: 31200, bookings: 58, growth: 12.1 },
  { name: 'Kids Paradise', revenue: 28400, bookings: 52, growth: -2.3 },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard
            key={stat.title}
            title={stat.title}
            value={stat.value}
            icon={<stat.icon className="h-4 w-4" />}
            trend={stat.trend}
          />
        ))}
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Bookings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Party Bookings</CardTitle>
            <CardDescription>Latest bookings across all venues</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentBookings.map((booking) => (
                <div
                  key={booking.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <p className="font-medium">{booking.customerName}</p>
                    <p className="text-sm text-muted-foreground">
                      {booking.package} • {booking.venue}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      {booking.date}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">${booking.amount}</p>
                    <Badge
                      variant={booking.status === 'confirmed' ? 'success' : 'warning'}
                    >
                      {booking.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Performing Venues */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Performing Venues</CardTitle>
            <CardDescription>Revenue and booking statistics</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {topVenues.map((venue, index) => (
                <div
                  key={venue.name}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                      {index + 1}
                    </div>
                    <div>
                      <p className="font-medium">{venue.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {venue.bookings} bookings
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">
                      ${venue.revenue.toLocaleString()}
                    </p>
                    <div className="flex items-center justify-end gap-1 text-xs">
                      <TrendingUp
                        className={`h-3 w-3 ${
                          venue.growth >= 0 ? 'text-green-500' : 'text-red-500'
                        }`}
                      />
                      <span
                        className={
                          venue.growth >= 0 ? 'text-green-600' : 'text-red-600'
                        }
                      >
                        {venue.growth >= 0 ? '+' : ''}
                        {venue.growth}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <button className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-accent">
              <PartyPopper className="h-5 w-5 text-primary" />
              <span className="font-medium">New Party Booking</span>
            </button>
            <button className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-accent">
              <Building2 className="h-5 w-5 text-primary" />
              <span className="font-medium">Add New Venue</span>
            </button>
            <button className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-accent">
              <Users className="h-5 w-5 text-primary" />
              <span className="font-medium">View All Customers</span>
            </button>
            <button className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-accent">
              <TrendingUp className="h-5 w-5 text-primary" />
              <span className="font-medium">Generate Report</span>
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
