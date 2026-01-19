/**
 * Auth & User Management types
 */
import type { AuditFields, UUID, ISODateString } from './common';

// Loyalty tiers
export type LoyaltyTier = 'BRONZE' | 'SILVER' | 'GOLD' | 'PLATINUM';

// User roles
export type UserRole = 'SUPER_ADMIN' | 'VENUE_ADMIN' | 'MANAGER' | 'STAFF' | 'CUSTOMER';

// Family roles
export type FamilyRole = 'PARENT' | 'GUARDIAN' | 'CHILD' | 'DEPENDENT';

// Membership status
export type MembershipStatus = 'ACTIVE' | 'FROZEN' | 'CANCELLED' | 'EXPIRED';

// User
export interface User {
  id: UUID;
  email: string;
  phone?: string;
  firstName?: string;
  lastName?: string;
  avatarUrl?: string;
  dateOfBirth?: ISODateString;
  emailVerified: boolean;
  phoneVerified: boolean;
  preferredLanguage: string;
  preferredCurrency: string;
  loyaltyTier: LoyaltyTier;
  loyaltyPoints: number;
  lifetimePoints: number;
  accessibilityNeeds?: Record<string, boolean>;
  facialRecognitionConsent: boolean;
  facialRecognitionEnrolled: boolean;
  createdAt: ISODateString;
  updatedAt: ISODateString;
  lastLoginAt?: ISODateString;
}

// User with roles for a venue
export interface UserWithRoles extends User {
  roles: VenueRole[];
}

export interface VenueRole {
  venueId: UUID;
  venueName: string;
  role: UserRole;
  permissions: string[];
}

// Auth tokens
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// Login/Register inputs
export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
}

export interface PasswordResetInput {
  email: string;
}

export interface PasswordResetConfirmInput {
  token: string;
  password: string;
}

// Family
export interface FamilyGroup {
  id: UUID;
  name: string;
  primaryContactId: UUID;
  sharedRewardsEnabled: boolean;
  members: FamilyMember[];
  createdAt: ISODateString;
}

export interface FamilyMember {
  id: UUID;
  userId: UUID;
  user?: User;
  familyRole: FamilyRole;
  nickname?: string;
  canManageFamily: boolean;
  joinedAt: ISODateString;
}

// Parental controls
export interface ParentalControl {
  id: UUID;
  parentId: UUID;
  childId: UUID;
  dailySpendLimit?: number;
  hourlySpendLimit?: number;
  totalBalanceLimit?: number;
  allowedPlayStart?: string;
  allowedPlayEnd?: string;
  blackoutDates?: string[];
  restrictedGameTypes?: string[];
  ageRestrictionOverride: boolean;
  activityNotifications: boolean;
  lowBalanceAlerts: boolean;
  spendAlerts: boolean;
  isActive: boolean;
}

// Membership
export interface MembershipPlan {
  id: UUID;
  venueId?: UUID;
  name: string;
  description?: string;
  planType: string;
  billingPeriod: 'MONTHLY' | 'QUARTERLY' | 'ANNUAL';
  price: number;
  freeGamesPerPeriod: number;
  discountPercentage: number;
  priorityBooking: boolean;
  guestPassesPerPeriod: number;
  bonusPointsMultiplier: number;
  maxFreezesPerYear: number;
  freezeDurationDays: number;
  minCommitmentMonths: number;
  isActive: boolean;
}

export interface Membership {
  id: UUID;
  userId: UUID;
  planId: UUID;
  plan?: MembershipPlan;
  venueId?: UUID;
  status: MembershipStatus;
  startDate: ISODateString;
  endDate?: ISODateString;
  nextBillingDate?: ISODateString;
  freezeStartDate?: ISODateString;
  freezeEndDate?: ISODateString;
  freezesUsedThisYear: number;
  gamesUsedThisPeriod: number;
  guestPassesUsedThisPeriod: number;
  autoRenew: boolean;
}

// User preferences
export interface UserPreference {
  id: UUID;
  userId: UUID;
  preferenceKey: string;
  preferenceValue: unknown;
}

// Session
export interface UserSession {
  id: UUID;
  userId: UUID;
  ipAddress?: string;
  userAgent?: string;
  lastActiveAt: ISODateString;
  expiresAt: ISODateString;
  isActive: boolean;
}
