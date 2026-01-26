/**
 * =============================================================================
 * FILE: types/index.ts
 * PURPOSE: TypeScript type definitions for the admin portal
 * =============================================================================
 *
 * This file contains all shared TypeScript interfaces and types used
 * throughout the admin portal application.
 *
 * CATEGORIES:
 * - User & Auth types
 * - Venue types
 * - Party & Booking types
 * - Customer types
 * - Analytics types
 *
 * =============================================================================
 */

// =============================================================================
// User & Auth Types
// =============================================================================

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  email_verified: boolean;
  phone_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// =============================================================================
// Venue Types
// =============================================================================

export interface Venue {
  id: string;
  name: string;
  description?: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  phone: string;
  email: string;
  website?: string;
  status: VenueStatus;
  capacity: number;
  total_attractions: number;
  operating_hours: OperatingHours[];
  amenities: string[];
  images: string[];
  created_at: string;
  updated_at: string;
}

export type VenueStatus = 'active' | 'inactive' | 'maintenance' | 'coming_soon';

export interface OperatingHours {
  day_of_week: number; // 0 = Sunday, 6 = Saturday
  open_time: string; // HH:MM format
  close_time: string;
  is_closed: boolean;
}

export interface Attraction {
  id: string;
  venue_id: string;
  name: string;
  description?: string;
  type: AttractionType;
  capacity: number;
  duration_minutes: number;
  min_age?: number;
  max_age?: number;
  min_height_inches?: number;
  price_credits: number;
  status: 'active' | 'inactive' | 'maintenance';
  images: string[];
}

export type AttractionType =
  | 'arcade_game'
  | 'bowling_lane'
  | 'laser_tag'
  | 'mini_golf'
  | 'go_kart'
  | 'bumper_cars'
  | 'trampoline'
  | 'climbing_wall'
  | 'vr_experience'
  | 'escape_room'
  | 'other';

// =============================================================================
// Party & Booking Types
// =============================================================================

export interface PartyPackage {
  id: string;
  venue_id: string;
  name: string;
  description: string;
  duration_minutes: number;
  min_guests: number;
  max_guests: number;
  base_price: number;
  price_per_additional_guest: number;
  included_attractions: string[];
  included_food_items: string[];
  add_ons: PackageAddOn[];
  status: 'active' | 'inactive';
}

export interface PackageAddOn {
  id: string;
  name: string;
  description: string;
  price: number;
  category: 'food' | 'decoration' | 'activity' | 'other';
}

export interface PartyBooking {
  id: string;
  venue_id: string;
  package_id: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  event_date: string;
  start_time: string;
  end_time: string;
  guest_count: number;
  child_of_honor_name: string;
  child_of_honor_age: number;
  special_requests?: string;
  status: BookingStatus;
  total_amount: number;
  deposit_amount: number;
  deposit_paid: boolean;
  balance_paid: boolean;
  created_at: string;
  updated_at: string;
}

export type BookingStatus =
  | 'pending'
  | 'confirmed'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show';

// =============================================================================
// Customer Types
// =============================================================================

export interface Customer {
  id: string;
  user_id?: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  date_of_birth?: string;
  address?: Address;
  loyalty_tier: LoyaltyTier;
  loyalty_points: number;
  total_visits: number;
  total_spent: number;
  last_visit_at?: string;
  notes?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
}

export type LoyaltyTier = 'bronze' | 'silver' | 'gold' | 'platinum';

export interface CustomerVisit {
  id: string;
  customer_id: string;
  venue_id: string;
  check_in_time: string;
  check_out_time?: string;
  total_spent: number;
  points_earned: number;
  attractions_used: string[];
}

// =============================================================================
// Analytics Types
// =============================================================================

export interface DashboardStats {
  total_revenue: number;
  revenue_change_percent: number;
  total_bookings: number;
  bookings_change_percent: number;
  total_customers: number;
  customers_change_percent: number;
  active_venues: number;
}

export interface RevenueData {
  date: string;
  revenue: number;
  bookings: number;
}

export interface VenuePerformance {
  venue_id: string;
  venue_name: string;
  revenue: number;
  bookings: number;
  customers: number;
  avg_rating: number;
  growth_percent: number;
}

export interface BookingTrend {
  hour: number;
  day_of_week: number;
  booking_count: number;
}

// =============================================================================
// Common Types
// =============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface SelectOption {
  value: string;
  label: string;
}

// =============================================================================
// END OF FILE
// =============================================================================
