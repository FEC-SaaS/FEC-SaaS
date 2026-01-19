'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Badge,
  DataTable,
  PageHeader,
  StatCard,
} from '@fec-saas/ui';
import type { Column } from '@fec-saas/ui';
import {
  Plus,
  Search,
  Calendar,
  Clock,
  Users,
  DollarSign,
  PartyPopper,
  Filter,
  Download,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
} from 'lucide-react';

interface PartyBooking {
  id: string;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  packageName: string;
  venueName: string;
  date: string;
  startTime: string;
  endTime: string;
  guestCount: number;
  childAge: number;
  status: 'pending' | 'confirmed' | 'completed' | 'cancelled';
  totalAmount: number;
  depositPaid: number;
  specialRequests?: string;
  createdAt: string;
}

// Mock party bookings data
const bookings: PartyBooking[] = [
  {
    id: 'PB-001',
    customerName: 'Sarah Johnson',
    customerEmail: 'sarah.j@email.com',
    customerPhone: '(512) 555-1234',
    packageName: 'Ultimate Birthday Bash',
    venueName: 'FunZone Downtown',
    date: '2024-01-25',
    startTime: '14:00',
    endTime: '17:00',
    guestCount: 20,
    childAge: 8,
    status: 'confirmed',
    totalAmount: 450,
    depositPaid: 150,
    specialRequests: 'Allergy: peanuts',
    createdAt: '2024-01-10',
  },
  {
    id: 'PB-002',
    customerName: 'Michael Smith',
    customerEmail: 'msmith@email.com',
    customerPhone: '(214) 555-5678',
    packageName: 'Classic Fun Package',
    venueName: 'Adventure Park',
    date: '2024-01-26',
    startTime: '11:00',
    endTime: '13:00',
    guestCount: 15,
    childAge: 6,
    status: 'pending',
    totalAmount: 275,
    depositPaid: 0,
    createdAt: '2024-01-15',
  },
  {
    id: 'PB-003',
    customerName: 'Emily Williams',
    customerEmail: 'emily.w@email.com',
    customerPhone: '(713) 555-9012',
    packageName: 'VIP Experience',
    venueName: 'FunZone Mall',
    date: '2024-01-27',
    startTime: '15:00',
    endTime: '19:00',
    guestCount: 30,
    childAge: 10,
    status: 'confirmed',
    totalAmount: 650,
    depositPaid: 250,
    specialRequests: 'Dinosaur theme decorations',
    createdAt: '2024-01-08',
  },
  {
    id: 'PB-004',
    customerName: 'David Brown',
    customerEmail: 'dbrown@email.com',
    customerPhone: '(210) 555-3456',
    packageName: 'Classic Fun Package',
    venueName: 'FunZone Downtown',
    date: '2024-01-28',
    startTime: '10:00',
    endTime: '12:00',
    guestCount: 12,
    childAge: 5,
    status: 'pending',
    totalAmount: 275,
    depositPaid: 100,
    createdAt: '2024-01-18',
  },
  {
    id: 'PB-005',
    customerName: 'Lisa Anderson',
    customerEmail: 'lisa.a@email.com',
    customerPhone: '(512) 555-7890',
    packageName: 'Ultimate Birthday Bash',
    venueName: 'Adventure Park',
    date: '2024-01-20',
    startTime: '13:00',
    endTime: '16:00',
    guestCount: 25,
    childAge: 9,
    status: 'completed',
    totalAmount: 450,
    depositPaid: 450,
    createdAt: '2024-01-05',
  },
  {
    id: 'PB-006',
    customerName: 'James Wilson',
    customerEmail: 'jwilson@email.com',
    customerPhone: '(713) 555-2345',
    packageName: 'Classic Fun Package',
    venueName: 'FunZone Mall',
    date: '2024-01-22',
    startTime: '16:00',
    endTime: '18:00',
    guestCount: 10,
    childAge: 7,
    status: 'cancelled',
    totalAmount: 275,
    depositPaid: 100,
    createdAt: '2024-01-12',
  },
];

const statusColors = {
  pending: 'warning',
  confirmed: 'success',
  completed: 'info',
  cancelled: 'destructive',
} as const;

const stats = [
  {
    title: 'Total Bookings',
    value: '248',
    icon: PartyPopper,
    trend: { value: 12.5, positive: true, label: 'this month' },
  },
  {
    title: 'Pending Approval',
    value: '18',
    icon: Clock,
    description: 'requires attention',
  },
  {
    title: 'This Week',
    value: '24',
    icon: Calendar,
    trend: { value: 8.2, positive: true, label: 'vs last week' },
  },
  {
    title: 'Revenue',
    value: '$12,450',
    icon: DollarSign,
    trend: { value: 15.3, positive: true, label: 'this week' },
  },
];

export default function PartiesPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedBooking, setSelectedBooking] = useState<PartyBooking | null>(null);

  const filteredBookings = bookings.filter((booking) => {
    const matchesSearch =
      booking.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      booking.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      booking.venueName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || booking.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const columns: Column<PartyBooking>[] = [
    {
      key: 'id',
      header: 'Booking ID',
      cell: (booking) => (
        <span className="font-mono text-sm">{booking.id}</span>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      cell: (booking) => (
        <div>
          <p className="font-medium">{booking.customerName}</p>
          <p className="text-sm text-muted-foreground">{booking.customerEmail}</p>
        </div>
      ),
    },
    {
      key: 'package',
      header: 'Package',
      cell: (booking) => (
        <div>
          <p className="font-medium">{booking.packageName}</p>
          <p className="text-sm text-muted-foreground">{booking.venueName}</p>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date & Time',
      cell: (booking) => (
        <div>
          <p>{booking.date}</p>
          <p className="text-sm text-muted-foreground">
            {booking.startTime} - {booking.endTime}
          </p>
        </div>
      ),
    },
    {
      key: 'guests',
      header: 'Guests',
      cell: (booking) => (
        <div className="flex items-center gap-1">
          <Users className="h-4 w-4 text-muted-foreground" />
          <span>{booking.guestCount}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (booking) => (
        <Badge variant={statusColors[booking.status]}>{booking.status}</Badge>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      cell: (booking) => (
        <div>
          <p className="font-medium">${booking.totalAmount}</p>
          <p className="text-xs text-muted-foreground">
            Paid: ${booking.depositPaid}
          </p>
        </div>
      ),
    },
    {
      key: 'actions',
      header: '',
      cell: (booking) => (
        <div className="flex items-center gap-1">
          <button
            className="rounded p-1 hover:bg-accent"
            title="View Details"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedBooking(booking);
            }}
          >
            <Eye className="h-4 w-4" />
          </button>
          {booking.status === 'pending' && (
            <>
              <button
                className="rounded p-1 hover:bg-accent text-green-600"
                title="Confirm"
              >
                <CheckCircle className="h-4 w-4" />
              </button>
              <button
                className="rounded p-1 hover:bg-accent text-destructive"
                title="Cancel"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </>
          )}
          <button className="rounded p-1 hover:bg-accent" title="Edit">
            <Edit className="h-4 w-4" />
          </button>
        </div>
      ),
      className: 'w-28',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Party Bookings"
        description="Manage birthday party and event bookings"
        actions={
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Booking
          </Button>
        }
      />

      {/* Stats */}
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

      {/* Search and filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by customer, booking ID, or venue..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <Button variant="outline">
                <Filter className="mr-2 h-4 w-4" />
                More Filters
              </Button>
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bookings table */}
      <DataTable
        columns={columns}
        data={filteredBookings}
        keyExtractor={(booking) => booking.id}
        onRowClick={(booking) => setSelectedBooking(booking)}
        emptyMessage="No bookings found"
      />

      {/* Booking detail panel */}
      {selectedBooking && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                Booking {selectedBooking.id}
                <Badge variant={statusColors[selectedBooking.status]}>
                  {selectedBooking.status}
                </Badge>
              </CardTitle>
              <CardDescription>
                Created on {selectedBooking.createdAt}
              </CardDescription>
            </div>
            <button
              onClick={() => setSelectedBooking(null)}
              className="rounded p-1 hover:bg-accent text-lg"
            >
              ×
            </button>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-3">
              {/* Customer Info */}
              <div className="space-y-3">
                <h4 className="font-medium">Customer Information</h4>
                <div className="space-y-2 text-sm">
                  <p>
                    <span className="text-muted-foreground">Name:</span>{' '}
                    {selectedBooking.customerName}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Email:</span>{' '}
                    {selectedBooking.customerEmail}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Phone:</span>{' '}
                    {selectedBooking.customerPhone}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Child Age:</span>{' '}
                    {selectedBooking.childAge} years old
                  </p>
                </div>
              </div>

              {/* Event Details */}
              <div className="space-y-3">
                <h4 className="font-medium">Event Details</h4>
                <div className="space-y-2 text-sm">
                  <p>
                    <span className="text-muted-foreground">Package:</span>{' '}
                    {selectedBooking.packageName}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Venue:</span>{' '}
                    {selectedBooking.venueName}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Date:</span>{' '}
                    {selectedBooking.date}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Time:</span>{' '}
                    {selectedBooking.startTime} - {selectedBooking.endTime}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Guests:</span>{' '}
                    {selectedBooking.guestCount}
                  </p>
                </div>
              </div>

              {/* Payment Info */}
              <div className="space-y-3">
                <h4 className="font-medium">Payment Information</h4>
                <div className="space-y-2 text-sm">
                  <p>
                    <span className="text-muted-foreground">Total:</span>{' '}
                    <span className="font-medium">
                      ${selectedBooking.totalAmount}
                    </span>
                  </p>
                  <p>
                    <span className="text-muted-foreground">Deposit Paid:</span>{' '}
                    ${selectedBooking.depositPaid}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Balance Due:</span>{' '}
                    <span className="font-medium text-destructive">
                      $
                      {selectedBooking.totalAmount - selectedBooking.depositPaid}
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* Special Requests */}
            {selectedBooking.specialRequests && (
              <div className="mt-4 rounded-lg border bg-muted/50 p-3">
                <h4 className="text-sm font-medium">Special Requests</h4>
                <p className="mt-1 text-sm text-muted-foreground">
                  {selectedBooking.specialRequests}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="mt-6 flex gap-2">
              {selectedBooking.status === 'pending' && (
                <>
                  <Button>
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Confirm Booking
                  </Button>
                  <Button variant="destructive">
                    <XCircle className="mr-2 h-4 w-4" />
                    Cancel Booking
                  </Button>
                </>
              )}
              <Button variant="outline">
                <Edit className="mr-2 h-4 w-4" />
                Edit Booking
              </Button>
              <Link href={`/parties/${selectedBooking.id}`}>
                <Button variant="outline">View Full Details</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
