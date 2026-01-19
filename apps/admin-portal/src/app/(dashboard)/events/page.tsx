'use client';

import { PageHeader, Card, CardContent, CardHeader, CardTitle, Button } from '@fec-saas/ui';
import { Plus, Calendar } from 'lucide-react';

export default function EventsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Events"
        description="Manage corporate events and special occasions"
        actions={<Button><Plus className="mr-2 h-4 w-4" />Create Event</Button>}
      />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Upcoming Events
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Event management features coming soon. This section will include:</p>
          <ul className="mt-4 list-disc list-inside space-y-2 text-sm text-muted-foreground">
            <li>Corporate event bookings</li>
            <li>Group reservations</li>
            <li>Special holiday events</li>
            <li>Private venue rentals</li>
            <li>Event calendar view</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
