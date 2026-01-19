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
  Input,
  Label,
  Alert,
  AlertDescription,
  AlertTitle,
} from '@fec-saas/ui';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  Calendar,
  Clock,
  MapPin,
  Users,
  DollarSign,
  Gift,
  MessageSquare,
  Edit,
  Save,
  X,
  Printer,
  Send,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';

// Mock booking data
const booking = {
  id: 'PB-001',
  customerName: 'Sarah Johnson',
  customerEmail: 'sarah.j@email.com',
  customerPhone: '(512) 555-1234',
  packageName: 'Ultimate Birthday Bash',
  packageDescription: 'Our premium party package includes 3 hours of unlimited attractions, dedicated party host, pizza & drinks for all guests, birthday cake, and exclusive party room.',
  venueName: 'FunZone Downtown',
  venueAddress: '123 Main Street, Austin, TX 78701',
  date: '2024-01-25',
  startTime: '14:00',
  endTime: '17:00',
  guestCount: 20,
  childName: 'Emma Johnson',
  childAge: 8,
  status: 'confirmed' as const,
  totalAmount: 450,
  depositPaid: 150,
  depositDate: '2024-01-10',
  balanceDue: 300,
  balanceDueDate: '2024-01-25',
  specialRequests: 'Allergy: peanuts. Please ensure all food is peanut-free. Also, Emma loves unicorns - if possible, any unicorn decorations would be appreciated!',
  addOns: [
    { name: 'Extra Hour', price: 75, quantity: 1 },
    { name: 'Goodie Bags', price: 5, quantity: 20 },
    { name: 'Photo Package', price: 50, quantity: 1 },
  ],
  timeline: [
    { time: '14:00', activity: 'Guest Arrival & Check-in' },
    { time: '14:15', activity: 'Free Play - Arcade Zone' },
    { time: '15:00', activity: 'Group Activity - Laser Tag' },
    { time: '15:45', activity: 'Party Room - Pizza & Drinks' },
    { time: '16:15', activity: 'Birthday Cake & Presents' },
    { time: '16:45', activity: 'Goodie Bags Distribution' },
    { time: '17:00', activity: 'Guest Departure' },
  ],
  notes: [
    { date: '2024-01-10', author: 'John (Sales)', text: 'Customer booked via phone, deposit received.' },
    { date: '2024-01-15', author: 'System', text: 'Confirmation email sent to customer.' },
    { date: '2024-01-18', author: 'Sarah (Manager)', text: 'Called customer to confirm allergy requirements.' },
  ],
  createdAt: '2024-01-10',
};

const statusColors = {
  pending: 'warning',
  confirmed: 'success',
  completed: 'info',
  cancelled: 'destructive',
} as const;

export default function PartyDetailPage() {
  const [isEditing, setIsEditing] = useState(false);
  const [newNote, setNewNote] = useState('');

  const addOnsTotal = booking.addOns.reduce(
    (sum, addon) => sum + addon.price * addon.quantity,
    0
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/parties">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">Booking {booking.id}</h1>
              <Badge variant={statusColors[booking.status]}>
                {booking.status}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              {booking.packageName} at {booking.venueName}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Printer className="mr-2 h-4 w-4" />
            Print
          </Button>
          <Button variant="outline">
            <Send className="mr-2 h-4 w-4" />
            Send Reminder
          </Button>
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                <X className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button onClick={() => setIsEditing(false)}>
                <Save className="mr-2 h-4 w-4" />
                Save
              </Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)}>
              <Edit className="mr-2 h-4 w-4" />
              Edit Booking
            </Button>
          )}
        </div>
      </div>

      {/* Alert for special requests */}
      {booking.specialRequests && (
        <Alert variant="warning">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Special Requirements</AlertTitle>
          <AlertDescription>{booking.specialRequests}</AlertDescription>
        </Alert>
      )}

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-2">
          {/* Customer & Event Info */}
          <Card>
            <CardHeader>
              <CardTitle>Customer & Event Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:grid-cols-2">
                {/* Customer Info */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <User className="h-4 w-4" />
                    Customer Information
                  </h4>
                  <div className="space-y-2 text-sm">
                    <p className="font-medium text-lg">{booking.customerName}</p>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Mail className="h-4 w-4" />
                      {booking.customerEmail}
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Phone className="h-4 w-4" />
                      {booking.customerPhone}
                    </div>
                  </div>
                </div>

                {/* Birthday Child */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <Gift className="h-4 w-4" />
                    Birthday Child
                  </h4>
                  <div className="space-y-2 text-sm">
                    <p className="font-medium text-lg">{booking.childName}</p>
                    <p className="text-muted-foreground">
                      Turning {booking.childAge} years old
                    </p>
                  </div>
                </div>

                {/* Event Date & Time */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Event Schedule
                  </h4>
                  <div className="space-y-2 text-sm">
                    <p>
                      <span className="text-muted-foreground">Date:</span>{' '}
                      <span className="font-medium">{booking.date}</span>
                    </p>
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      {booking.startTime} - {booking.endTime} (3 hours)
                    </div>
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-muted-foreground" />
                      {booking.guestCount} guests expected
                    </div>
                  </div>
                </div>

                {/* Venue */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    Venue
                  </h4>
                  <div className="space-y-2 text-sm">
                    <p className="font-medium">{booking.venueName}</p>
                    <p className="text-muted-foreground">{booking.venueAddress}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Party Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Party Timeline</CardTitle>
              <CardDescription>Scheduled activities for the event</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {booking.timeline.map((item, index) => (
                  <div key={index} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                        {item.time.split(':')[0]}
                      </div>
                      {index < booking.timeline.length - 1 && (
                        <div className="h-full w-px bg-border" />
                      )}
                    </div>
                    <div className="pb-4">
                      <p className="font-medium">{item.activity}</p>
                      <p className="text-sm text-muted-foreground">{item.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Notes & Communication */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Notes & Communication
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {booking.notes.map((note, index) => (
                  <div key={index} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{note.author}</span>
                      <span className="text-muted-foreground">{note.date}</span>
                    </div>
                    <p className="mt-1 text-sm">{note.text}</p>
                  </div>
                ))}
                <div className="flex gap-2">
                  <Input
                    placeholder="Add a note..."
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                  />
                  <Button disabled={!newNote}>Add Note</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right column - Payment */}
        <div className="space-y-6">
          {/* Package Info */}
          <Card>
            <CardHeader>
              <CardTitle>{booking.packageName}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {booking.packageDescription}
              </p>
            </CardContent>
          </Card>

          {/* Payment Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Payment Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Package Base Price</span>
                  <span>$350.00</span>
                </div>

                {booking.addOns.map((addon, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span className="text-muted-foreground">
                      {addon.name} {addon.quantity > 1 && `(x${addon.quantity})`}
                    </span>
                    <span>${(addon.price * addon.quantity).toFixed(2)}</span>
                  </div>
                ))}

                <div className="border-t pt-3">
                  <div className="flex justify-between font-medium">
                    <span>Total</span>
                    <span>${booking.totalAmount.toFixed(2)}</span>
                  </div>
                </div>

                <div className="border-t pt-3 space-y-2">
                  <div className="flex justify-between text-sm text-green-600">
                    <span>Deposit Paid ({booking.depositDate})</span>
                    <span>-${booking.depositPaid.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-medium text-destructive">
                    <span>Balance Due</span>
                    <span>${booking.balanceDue.toFixed(2)}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Due by {booking.balanceDueDate}
                  </p>
                </div>

                <Button className="w-full">
                  <DollarSign className="mr-2 h-4 w-4" />
                  Record Payment
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="outline" className="w-full justify-start">
                <Send className="mr-2 h-4 w-4" />
                Send Confirmation Email
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Calendar className="mr-2 h-4 w-4" />
                Reschedule Party
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Users className="mr-2 h-4 w-4" />
                Assign Party Host
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start text-destructive"
              >
                <X className="mr-2 h-4 w-4" />
                Cancel Booking
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
