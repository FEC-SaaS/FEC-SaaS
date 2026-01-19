'use client';

import { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Badge,
  DataTable,
  PageHeader,
} from '@fec-saas/ui';
import type { Column } from '@fec-saas/ui';
import {
  Plus,
  Search,
  MapPin,
  Phone,
  Mail,
  Clock,
  MoreVertical,
  Edit,
  Trash2,
  Eye,
} from 'lucide-react';

interface Venue {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  phone: string;
  email: string;
  status: 'active' | 'inactive' | 'maintenance';
  totalAttractions: number;
  capacity: number;
  todayBookings: number;
  monthlyRevenue: number;
}

// Mock venue data
const venues: Venue[] = [
  {
    id: '1',
    name: 'FunZone Downtown',
    address: '123 Main Street',
    city: 'Austin',
    state: 'TX',
    phone: '(512) 555-0100',
    email: 'downtown@funzone.com',
    status: 'active',
    totalAttractions: 24,
    capacity: 350,
    todayBookings: 8,
    monthlyRevenue: 45230,
  },
  {
    id: '2',
    name: 'Adventure Park',
    address: '456 Oak Avenue',
    city: 'Dallas',
    state: 'TX',
    phone: '(214) 555-0200',
    email: 'adventure@funzone.com',
    status: 'active',
    totalAttractions: 32,
    capacity: 500,
    todayBookings: 12,
    monthlyRevenue: 38750,
  },
  {
    id: '3',
    name: 'FunZone Mall',
    address: '789 Commerce Blvd',
    city: 'Houston',
    state: 'TX',
    phone: '(713) 555-0300',
    email: 'mall@funzone.com',
    status: 'active',
    totalAttractions: 18,
    capacity: 275,
    todayBookings: 5,
    monthlyRevenue: 31200,
  },
  {
    id: '4',
    name: 'Kids Paradise',
    address: '321 Family Lane',
    city: 'San Antonio',
    state: 'TX',
    phone: '(210) 555-0400',
    email: 'paradise@funzone.com',
    status: 'maintenance',
    totalAttractions: 20,
    capacity: 200,
    todayBookings: 0,
    monthlyRevenue: 28400,
  },
  {
    id: '5',
    name: 'Splash Zone',
    address: '555 Water Way',
    city: 'Austin',
    state: 'TX',
    phone: '(512) 555-0500',
    email: 'splash@funzone.com',
    status: 'inactive',
    totalAttractions: 15,
    capacity: 400,
    todayBookings: 0,
    monthlyRevenue: 0,
  },
];

const statusColors = {
  active: 'success',
  inactive: 'secondary',
  maintenance: 'warning',
} as const;

export default function VenuesPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedVenue, setSelectedVenue] = useState<Venue | null>(null);

  const filteredVenues = venues.filter(
    (venue) =>
      venue.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      venue.city.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const columns: Column<Venue>[] = [
    {
      key: 'name',
      header: 'Venue',
      cell: (venue) => (
        <div>
          <p className="font-medium">{venue.name}</p>
          <p className="text-sm text-muted-foreground">
            {venue.city}, {venue.state}
          </p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (venue) => (
        <Badge variant={statusColors[venue.status]}>{venue.status}</Badge>
      ),
    },
    {
      key: 'totalAttractions',
      header: 'Attractions',
      cell: (venue) => venue.totalAttractions,
    },
    {
      key: 'capacity',
      header: 'Capacity',
      cell: (venue) => venue.capacity.toLocaleString(),
    },
    {
      key: 'todayBookings',
      header: "Today's Bookings",
      cell: (venue) => venue.todayBookings,
    },
    {
      key: 'monthlyRevenue',
      header: 'Monthly Revenue',
      cell: (venue) => `$${venue.monthlyRevenue.toLocaleString()}`,
    },
    {
      key: 'actions',
      header: '',
      cell: (venue) => (
        <div className="flex items-center gap-2">
          <button
            className="rounded p-1 hover:bg-accent"
            title="View Details"
            onClick={() => setSelectedVenue(venue)}
          >
            <Eye className="h-4 w-4" />
          </button>
          <button className="rounded p-1 hover:bg-accent" title="Edit">
            <Edit className="h-4 w-4" />
          </button>
          <button
            className="rounded p-1 hover:bg-accent text-destructive"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
      className: 'w-24',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Venue Management"
        description="Manage all your Family Entertainment Center venues"
        actions={
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Add Venue
          </Button>
        }
      />

      {/* Search and filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search venues by name or city..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Button variant="outline">Filters</Button>
            <Button variant="outline">Export</Button>
          </div>
        </CardContent>
      </Card>

      {/* Venues table */}
      <DataTable
        columns={columns}
        data={filteredVenues}
        keyExtractor={(venue) => venue.id}
        onRowClick={(venue) => setSelectedVenue(venue)}
        emptyMessage="No venues found"
      />

      {/* Venue detail panel */}
      {selectedVenue && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{selectedVenue.name}</CardTitle>
            <button
              onClick={() => setSelectedVenue(null)}
              className="rounded p-1 hover:bg-accent"
            >
              ×
            </button>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <h4 className="font-medium">Contact Information</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <span>
                      {selectedVenue.address}, {selectedVenue.city},{' '}
                      {selectedVenue.state}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedVenue.phone}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedVenue.email}</span>
                  </div>
                </div>
              </div>
              <div className="space-y-4">
                <h4 className="font-medium">Operating Hours</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Mon - Thu:</span>
                    <span>10:00 AM - 9:00 PM</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Fri - Sat:</span>
                    <span>10:00 AM - 11:00 PM</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Sunday:</span>
                    <span>11:00 AM - 8:00 PM</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-6 flex gap-2">
              <Button>Edit Venue</Button>
              <Button variant="outline">View Full Details</Button>
              <Button variant="outline">Manage Attractions</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
