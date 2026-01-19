/**
 * Venue Management types
 */
import type { UUID, ISODateString, DayOfWeek } from './common';

// Subscription tiers
export type SubscriptionTier = 'STARTER' | 'PRO' | 'ENTERPRISE';

// Status
export type VenueStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';

// Venue feature types
export type VenueFeature = 'BOWLING' | 'ARCADE' | 'MINI_GOLF_INDOOR' | 'MINI_GOLF_OUTDOOR' | 'DARTS' | 'RESTAURANT' | 'BAR' | 'PARTIES' | 'LASER_TAG' | 'GO_KARTS';

// AI service types
export type AIService = 'DYNAMIC_PRICING' | 'SMART_STAFF' | 'CHURN_PREDICTION' | 'GAME_FLOOR_OPTIMIZER' | 'PARTY_FLOW' | 'SENTIMENT_ANALYZER' | 'FOOD_WASTE_OPTIMIZER' | 'RECOMMENDATION_ENGINE';

// AI strategy
export type AIStrategy = 'AGGRESSIVE' | 'MODERATE' | 'CONSERVATIVE';

// Address
export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
}

// Venue
export interface Venue {
  id: UUID;
  name: string;
  legalName?: string;
  address: Address;
  timezone: string;
  phone?: string;
  email?: string;
  website?: string;
  subscriptionTier: SubscriptionTier;
  status: VenueStatus;
  onboardingCompleted: boolean;
  goLiveDate?: ISODateString;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

export interface VenueWithDetails extends Venue {
  hours: VenueHours[];
  features: VenueFeatureConfig[];
  aiConfig: VenueAIConfig[];
  settings: VenueSetting[];
}

// Operating hours
export interface VenueHours {
  id: UUID;
  venueId: UUID;
  dayOfWeek: DayOfWeek;
  openTime: string;
  closeTime: string;
  isClosed: boolean;
}

export interface VenueHoursInput {
  dayOfWeek: DayOfWeek;
  openTime: string;
  closeTime: string;
  isClosed: boolean;
}

// Feature configuration
export interface VenueFeatureConfig {
  id: UUID;
  venueId: UUID;
  featureName: VenueFeature;
  isEnabled: boolean;
  config?: Record<string, unknown>;
}

// AI configuration
export interface VenueAIConfig {
  id: UUID;
  venueId: UUID;
  aiService: AIService;
  isEnabled: boolean;
  strategy: AIStrategy;
  params?: Record<string, unknown>;
}

// Venue settings (key-value)
export interface VenueSetting {
  id: UUID;
  venueId: UUID;
  settingKey: string;
  settingValue: string;
  settingType: 'STRING' | 'NUMBER' | 'BOOLEAN' | 'JSON';
}

// Venue performance metrics
export interface VenuePerformance {
  id: UUID;
  venueId: UUID;
  date: ISODateString;
  revenue: number;
  customers: number;
  transactions: number;
  ebitdaPercentage: number;
  laborCostPercentage: number;
  foodWastePercentage: number;
  metrics?: Record<string, unknown>;
}

// Venue benchmark comparison
export interface VenueBenchmark {
  venueId: UUID;
  venueName: string;
  revenue: number;
  revenueRank: number;
  customers: number;
  customersRank: number;
  avgTransactionValue: number;
  avgTransactionValueRank: number;
  ebitdaMargin: number;
  ebitdaMarginRank: number;
}

// Create/Update inputs
export interface CreateVenueInput {
  name: string;
  legalName?: string;
  address: Address;
  timezone: string;
  phone?: string;
  email?: string;
  website?: string;
  subscriptionTier?: SubscriptionTier;
}

export interface UpdateVenueInput extends Partial<CreateVenueInput> {
  status?: VenueStatus;
}

// Dashboard stats
export interface VenueDashboardStats {
  revenue: {
    today: number;
    week: number;
    month: number;
    percentChange: number;
  };
  customers: {
    today: number;
    week: number;
    month: number;
    percentChange: number;
  };
  occupancy: {
    current: number;
    average: number;
    peak: number;
  };
  upcomingParties: number;
  activeStaff: number;
  lowInventoryItems: number;
}
