/**
 * Booking and Party types
 */
import type { UUID, ISODateString, Priority } from './common';

// Booking status
export type BookingStatus = 'PENDING' | 'CONFIRMED' | 'CHECKED_IN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED' | 'NO_SHOW';

// Booking type
export type BookingType = 'BOWLING' | 'ARCADE' | 'MINI_GOLF' | 'PARTY' | 'CORPORATE_EVENT' | 'RESTAURANT';

// Party type
export type PartyType = 'BIRTHDAY' | 'CORPORATE' | 'HOLIDAY' | 'CUSTOM';

// Corporate event type
export type CorporateEventType = 'TEAM_BUILDING' | 'HAPPY_HOUR' | 'CONFERENCE' | 'HOLIDAY_PARTY';

// Party package
export interface PartyPackage {
  id: UUID;
  venueId: UUID;
  packageName: string;
  packageType: PartyType;
  minGuests: number;
  maxGuests: number;
  basePrice: number;
  pricePerAdditionalGuest: number;
  durationMinutes: number;
  includesFood: boolean;
  includesActivities: boolean;
  description?: string;
  imageUrl?: string;
  isActive: boolean;
  createdAt: ISODateString;
}

// Party add-on (upsells)
export interface PartyAddon {
  id: UUID;
  venueId: UUID;
  addonName: string;
  addonType: 'EXTRA_TIME' | 'PREMIUM_FOOD' | 'DECORATIONS' | 'PARTY_FAVORS' | 'PHOTOGRAPHY' | 'ENTERTAINMENT';
  price: number;
  description?: string;
  imageUrl?: string;
  isActive: boolean;
}

// Party booking
export interface PartyBooking {
  id: UUID;
  venueId: UUID;
  customerId: UUID;
  customer?: {
    firstName: string;
    lastName: string;
    email?: string;
    phone?: string;
  };
  packageId: UUID;
  package?: PartyPackage;
  bookingType: PartyType;
  partyDate: ISODateString;
  startTime: string;
  endTime: string;
  guestCount: number;
  childCount?: number;
  adultCount?: number;
  guestOfHonorName?: string;
  guestOfHonorAge?: number;
  basePrice: number;
  totalPrice: number;
  depositAmount: number;
  depositPaid: boolean;
  balanceDue: number;
  status: BookingStatus;
  specialRequests?: string;
  dietaryRestrictions?: string;
  addons: PartyBookingAddon[];
  timeline?: PartyTimelineItem[];
  assignedStaff?: PartyStaffAssignment[];
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

// Party booking addon
export interface PartyBookingAddon {
  id: UUID;
  bookingId: UUID;
  addonId: UUID;
  addon?: PartyAddon;
  quantity: number;
  price: number;
}

// Party timeline item
export interface PartyTimelineItem {
  id: UUID;
  bookingId: UUID;
  timelineItem: string;
  scheduledTime: string;
  actualTime?: string;
  completed: boolean;
  assignedStaffId?: UUID;
  notes?: string;
}

// Party staff assignment
export interface PartyStaffAssignment {
  id: UUID;
  bookingId: UUID;
  staffId: UUID;
  staffName?: string;
  role: 'PRIMARY_HOST' | 'ASSISTANT' | 'FOOD_RUNNER';
  assignedAt: ISODateString;
}

// Corporate event
export interface CorporateEvent {
  id: UUID;
  venueId: UUID;
  companyName: string;
  contactName: string;
  contactEmail: string;
  contactPhone?: string;
  eventType: CorporateEventType;
  eventDate: ISODateString;
  startTime: string;
  endTime: string;
  attendeeCount: number;
  estimatedBudget?: number;
  totalPrice?: number;
  status: 'INQUIRY' | 'PROPOSAL_SENT' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
  leadScore?: number;
  specialRequests?: string;
  cateringRequirements?: string;
  avRequirements?: string;
  createdAt: ISODateString;
}

// General booking (bowling, arcade, etc.)
export interface Booking {
  id: UUID;
  venueId: UUID;
  customerId?: UUID;
  bookingType: BookingType;
  bookingDate: ISODateString;
  startTime: string;
  endTime?: string;
  partySize: number;
  status: BookingStatus;
  resourceId?: UUID;
  resourceName?: string;
  totalPrice?: number;
  notes?: string;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

// Create booking inputs
export interface CreatePartyBookingInput {
  customerId: UUID;
  packageId: UUID;
  partyDate: ISODateString;
  startTime: string;
  guestCount: number;
  childCount?: number;
  adultCount?: number;
  guestOfHonorName?: string;
  guestOfHonorAge?: number;
  specialRequests?: string;
  dietaryRestrictions?: string;
  addonIds?: UUID[];
}

export interface CreateBookingInput {
  customerId?: UUID;
  bookingType: BookingType;
  bookingDate: ISODateString;
  startTime: string;
  endTime?: string;
  partySize: number;
  resourceId?: UUID;
  notes?: string;
}

// Calendar view
export interface CalendarEvent {
  id: UUID;
  title: string;
  start: Date;
  end: Date;
  type: BookingType | PartyType;
  status: BookingStatus;
  customerId?: UUID;
  customerName?: string;
  resourceId?: UUID;
  resourceName?: string;
  color?: string;
}

// Availability
export interface TimeSlot {
  startTime: string;
  endTime: string;
  available: boolean;
  price?: number;
}

export interface AvailabilityResponse {
  date: ISODateString;
  resourceId?: UUID;
  resourceName?: string;
  slots: TimeSlot[];
}

// Party analytics
export interface PartyAnalytics {
  totalBookings: number;
  totalRevenue: number;
  averagePartySize: number;
  averagePartyValue: number;
  upsellConversionRate: number;
  cancellationRate: number;
  byPackage: {
    packageId: UUID;
    packageName: string;
    count: number;
    revenue: number;
  }[];
  byMonth: {
    month: string;
    count: number;
    revenue: number;
  }[];
}
