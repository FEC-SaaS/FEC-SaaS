/**
 * Customer types (GuestIQ)
 */
import type { UUID, ISODateString } from './common';
import type { LoyaltyTier } from './auth';

// Customer segment
export type CustomerSegment = 'NEW' | 'REGULAR' | 'VIP' | 'AT_RISK' | 'CHURNED';

// Customer source
export type CustomerSource = 'WALK_IN' | 'ONLINE' | 'REFERRAL' | 'SOCIAL_MEDIA' | 'EVENT' | 'CORPORATE';

// Customer
export interface Customer {
  id: UUID;
  userId?: UUID;
  venueId: UUID;
  firstName: string;
  lastName: string;
  email?: string;
  phone?: string;
  dateOfBirth?: ISODateString;
  segment: CustomerSegment;
  source: CustomerSource;
  loyaltyTier: LoyaltyTier;
  loyaltyPoints: number;
  lifetimeValue: number;
  visitCount: number;
  lastVisitAt?: ISODateString;
  averageSpend: number;
  preferredActivities: string[];
  dietaryRestrictions?: string[];
  notes?: string;
  tags: string[];
  isVip: boolean;
  churnRisk?: number;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

// Customer visit
export interface CustomerVisit {
  id: UUID;
  customerId: UUID;
  venueId: UUID;
  visitDate: ISODateString;
  checkInTime: string;
  checkOutTime?: string;
  partySize: number;
  totalSpend: number;
  activities: string[];
  satisfaction?: number;
  notes?: string;
}

// Customer feedback
export interface CustomerFeedback {
  id: UUID;
  customerId: UUID;
  venueId: UUID;
  visitId?: UUID;
  rating: number;
  comment?: string;
  category: 'SERVICE' | 'FOOD' | 'ACTIVITIES' | 'CLEANLINESS' | 'VALUE' | 'GENERAL';
  sentiment?: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  isResolved: boolean;
  responseText?: string;
  createdAt: ISODateString;
}

// Customer search/filter
export interface CustomerFilter {
  search?: string;
  segment?: CustomerSegment;
  loyaltyTier?: LoyaltyTier;
  minVisits?: number;
  maxVisits?: number;
  minLifetimeValue?: number;
  tags?: string[];
  isVip?: boolean;
  lastVisitFrom?: ISODateString;
  lastVisitTo?: ISODateString;
}

// Customer analytics
export interface CustomerAnalytics {
  totalCustomers: number;
  newThisMonth: number;
  activeCustomers: number;
  atRiskCustomers: number;
  averageLifetimeValue: number;
  segmentBreakdown: Record<CustomerSegment, number>;
  tierBreakdown: Record<LoyaltyTier, number>;
  topCustomers: Customer[];
}

// Create customer input
export interface CreateCustomerInput {
  firstName: string;
  lastName: string;
  email?: string;
  phone?: string;
  dateOfBirth?: ISODateString;
  source?: CustomerSource;
  notes?: string;
  tags?: string[];
}

export interface UpdateCustomerInput extends Partial<CreateCustomerInput> {
  segment?: CustomerSegment;
  isVip?: boolean;
}
