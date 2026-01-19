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
  Badge,
  StatCard,
  Input,
  Label,
} from '@fec-saas/ui';
import {
  ArrowLeft,
  MapPin,
  Phone,
  Mail,
  Clock,
  Users,
  DollarSign,
  PartyPopper,
  TrendingUp,
  Edit,
  Save,
  X,
} from 'lucide-react';

// Mock venue data - would come from API
const venue = {
  id: '1',
  name: 'FunZone Downtown',
  address: '123 Main Street',
  city: 'Austin',
  state: 'TX',
  zipCode: '78701',
  phone: '(512) 555-0100',
  email: 'downtown@funzone.com',
  status: 'active' as const,
  description: 'Our flagship location featuring over 20 attractions including go-karts, laser tag, arcade games, and a dedicated party zone.',
  totalAttractions: 24,
  capacity: 350,
  todayBookings: 8,
  monthlyRevenue: 45230,
  yearlyRevenue: 542760,
  totalCustomers: 12500,
  avgRating: 4.7,
  hours: {
    monday: { open: '10:00', close: '21:00' },
    tuesday: { open: '10:00', close: '21:00' },
    wednesday: { open: '10:00', close: '21:00' },
    thursday: { open: '10:00', close: '21:00' },
    friday: { open: '10:00', close: '23:00' },
    saturday: { open: '10:00', close: '23:00' },
    sunday: { open: '11:00', close: '20:00' },
  },
  features: ['Go Karts', 'Laser Tag', 'Arcade', 'Party Rooms', 'Food Court', 'Mini Golf'],
};

export default function VenueDetailPage() {
  const [isEditing, setIsEditing] = useState(false);
  const [editedVenue, setEditedVenue] = useState(venue);

  const stats = [
    {
      title: 'Monthly Revenue',
      value: `$${venue.monthlyRevenue.toLocaleString()}`,
      icon: DollarSign,
      trend: { value: 12.5, positive: true, label: 'vs last month' },
    },
    {
      title: 'Total Customers',
      value: venue.totalCustomers.toLocaleString(),
      icon: Users,
      trend: { value: 8.2, positive: true, label: 'this month' },
    },
    {
      title: 'Party Bookings',
      value: venue.todayBookings.toString(),
      icon: PartyPopper,
      description: 'scheduled today',
    },
    {
      title: 'Avg Rating',
      value: venue.avgRating.toFixed(1),
      icon: TrendingUp,
      description: 'out of 5 stars',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/venues">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{venue.name}</h1>
              <Badge variant="success">{venue.status}</Badge>
            </div>
            <p className="text-muted-foreground">
              {venue.address}, {venue.city}, {venue.state}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                <X className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button onClick={() => setIsEditing(false)}>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)}>
              <Edit className="mr-2 h-4 w-4" />
              Edit Venue
            </Button>
          )}
        </div>
      </div>

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

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Venue Info */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Venue Information</CardTitle>
            <CardDescription>Basic details about this location</CardDescription>
          </CardHeader>
          <CardContent>
            {isEditing ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Venue Name</Label>
                  <Input
                    id="name"
                    value={editedVenue.name}
                    onChange={(e) =>
                      setEditedVenue({ ...editedVenue, name: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone</Label>
                  <Input
                    id="phone"
                    value={editedVenue.phone}
                    onChange={(e) =>
                      setEditedVenue({ ...editedVenue, phone: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    value={editedVenue.email}
                    onChange={(e) =>
                      setEditedVenue({ ...editedVenue, email: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="address">Address</Label>
                  <Input
                    id="address"
                    value={editedVenue.address}
                    onChange={(e) =>
                      setEditedVenue({ ...editedVenue, address: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input
                    id="city"
                    value={editedVenue.city}
                    onChange={(e) =>
                      setEditedVenue({ ...editedVenue, city: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="capacity">Capacity</Label>
                  <Input
                    id="capacity"
                    type="number"
                    value={editedVenue.capacity}
                    onChange={(e) =>
                      setEditedVenue({
                        ...editedVenue,
                        capacity: parseInt(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-muted-foreground">{venue.description}</p>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <span>
                      {venue.address}, {venue.city}, {venue.state} {venue.zipCode}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{venue.phone}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{venue.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span>Capacity: {venue.capacity} guests</span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Operating Hours */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Operating Hours
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {Object.entries(venue.hours).map(([day, hours]) => (
                <div key={day} className="flex items-center justify-between">
                  <span className="capitalize text-muted-foreground">{day}</span>
                  <span>
                    {hours.open} - {hours.close}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Features */}
      <Card>
        <CardHeader>
          <CardTitle>Available Features & Attractions</CardTitle>
          <CardDescription>
            {venue.totalAttractions} total attractions at this venue
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {venue.features.map((feature) => (
              <Badge key={feature} variant="secondary" className="text-sm">
                {feature}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
