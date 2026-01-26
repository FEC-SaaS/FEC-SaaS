/**
 * =============================================================================
 * FILE: (dashboard)/customers/page.tsx
 * PURPOSE: Customer management page with profiles, loyalty tiers, and analytics
 * =============================================================================
 *
 * This page provides comprehensive customer relationship management:
 * - Customer listing with search and filters
 * - Loyalty tier visualization (Bronze, Silver, Gold, Platinum)
 * - Customer statistics and engagement metrics
 * - Quick actions for customer management
 * - Customer profile details panel
 *
 * FEATURES:
 * - Search by name, email, or phone
 * - Filter by loyalty tier
 * - Sort by visits, spending, or join date
 * - Customer detail slide-over panel
 * - Loyalty points tracking
 * - Visit history
 *
 * =============================================================================
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  Mail,
  Phone,
  Calendar,
  MapPin,
  Star,
  TrendingUp,
  DollarSign,
  Users,
  Crown,
  Award,
  Gift,
  Tag,
  Filter,
  Download,
  MoreVertical,
  Edit,
  Trash2,
  Eye,
  MessageSquare,
  X,
  ChevronRight,
  Clock,
  Sparkles,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';

/**
 * Customer interface
 */
interface Customer {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  avatar: string;
  membershipTier: 'bronze' | 'silver' | 'gold' | 'platinum';
  loyaltyPoints: number;
  totalVisits: number;
  totalSpent: number;
  avgSpendPerVisit: number;
  lastVisit: string;
  joinDate: string;
  birthDate?: string;
  address?: {
    city: string;
    state: string;
  };
  tags: string[];
  notes?: string;
  recentBookings: {
    id: string;
    venue: string;
    date: string;
    amount: number;
  }[];
}

/**
 * Mock customer data
 */
const customers: Customer[] = [
  {
    id: '1',
    firstName: 'Sarah',
    lastName: 'Johnson',
    email: 'sarah.j@email.com',
    phone: '(512) 555-1234',
    avatar: 'SJ',
    membershipTier: 'gold',
    loyaltyPoints: 2450,
    totalVisits: 24,
    totalSpent: 1250,
    avgSpendPerVisit: 52,
    lastVisit: '2024-01-15',
    joinDate: '2023-03-10',
    birthDate: '1988-06-15',
    address: { city: 'Austin', state: 'TX' },
    tags: ['VIP', 'Birthday Club'],
    notes: 'Prefers weekend bookings. Has 2 children.',
    recentBookings: [
      { id: 'PB-001', venue: 'FunZone Downtown', date: '2024-01-15', amount: 450 },
      { id: 'PB-010', venue: 'Adventure Park', date: '2023-12-20', amount: 325 },
    ],
  },
  {
    id: '2',
    firstName: 'Michael',
    lastName: 'Smith',
    email: 'msmith@email.com',
    phone: '(214) 555-5678',
    avatar: 'MS',
    membershipTier: 'silver',
    loyaltyPoints: 1200,
    totalVisits: 12,
    totalSpent: 650,
    avgSpendPerVisit: 54,
    lastVisit: '2024-01-18',
    joinDate: '2023-06-22',
    address: { city: 'Dallas', state: 'TX' },
    tags: ['Corporate'],
    recentBookings: [
      { id: 'PB-005', venue: 'Adventure Park', date: '2024-01-18', amount: 275 },
    ],
  },
  {
    id: '3',
    firstName: 'Emily',
    lastName: 'Williams',
    email: 'emily.w@email.com',
    phone: '(713) 555-9012',
    avatar: 'EW',
    membershipTier: 'platinum',
    loyaltyPoints: 5800,
    totalVisits: 48,
    totalSpent: 3200,
    avgSpendPerVisit: 67,
    lastVisit: '2024-01-20',
    joinDate: '2022-08-15',
    birthDate: '1985-11-22',
    address: { city: 'Houston', state: 'TX' },
    tags: ['VIP', 'Birthday Club', 'Ambassador'],
    notes: 'Long-time customer. Refers many friends.',
    recentBookings: [
      { id: 'PB-003', venue: 'FunZone Mall', date: '2024-01-20', amount: 650 },
      { id: 'PB-012', venue: 'FunZone Downtown', date: '2024-01-05', amount: 450 },
      { id: 'PB-015', venue: 'Adventure Park', date: '2023-12-15', amount: 550 },
    ],
  },
  {
    id: '4',
    firstName: 'David',
    lastName: 'Brown',
    email: 'dbrown@email.com',
    phone: '(210) 555-3456',
    avatar: 'DB',
    membershipTier: 'bronze',
    loyaltyPoints: 350,
    totalVisits: 5,
    totalSpent: 275,
    avgSpendPerVisit: 55,
    lastVisit: '2024-01-10',
    joinDate: '2023-11-05',
    address: { city: 'San Antonio', state: 'TX' },
    tags: ['New'],
    recentBookings: [
      { id: 'PB-008', venue: 'Kids Paradise', date: '2024-01-10', amount: 275 },
    ],
  },
  {
    id: '5',
    firstName: 'Lisa',
    lastName: 'Anderson',
    email: 'lisa.a@email.com',
    phone: '(512) 555-7890',
    avatar: 'LA',
    membershipTier: 'gold',
    loyaltyPoints: 2100,
    totalVisits: 18,
    totalSpent: 980,
    avgSpendPerVisit: 54,
    lastVisit: '2024-01-12',
    joinDate: '2023-04-18',
    birthDate: '1990-03-08',
    address: { city: 'Austin', state: 'TX' },
    tags: ['Birthday Club'],
    recentBookings: [
      { id: 'PB-020', venue: 'FunZone Downtown', date: '2024-01-12', amount: 450 },
    ],
  },
  {
    id: '6',
    firstName: 'James',
    lastName: 'Wilson',
    email: 'jwilson@email.com',
    phone: '(713) 555-2345',
    avatar: 'JW',
    membershipTier: 'silver',
    loyaltyPoints: 950,
    totalVisits: 8,
    totalSpent: 520,
    avgSpendPerVisit: 65,
    lastVisit: '2024-01-08',
    joinDate: '2023-07-30',
    address: { city: 'Houston', state: 'TX' },
    tags: ['Corporate'],
    recentBookings: [
      { id: 'PB-025', venue: 'FunZone Mall', date: '2024-01-08', amount: 325 },
    ],
  },
];

/**
 * Tier badge styles
 */
const tierStyles = {
  bronze: {
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-400',
    icon: Award,
    gradient: 'from-amber-400 to-amber-600',
  },
  silver: {
    bg: 'bg-slate-100 dark:bg-slate-700',
    text: 'text-slate-600 dark:text-slate-400',
    icon: Award,
    gradient: 'from-slate-400 to-slate-600',
  },
  gold: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
    text: 'text-yellow-700 dark:text-yellow-500',
    icon: Crown,
    gradient: 'from-yellow-400 to-yellow-600',
  },
  platinum: {
    bg: 'bg-purple-100 dark:bg-purple-900/30',
    text: 'text-purple-700 dark:text-purple-400',
    icon: Sparkles,
    gradient: 'from-purple-400 to-purple-600',
  },
};

export default function CustomersPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [sortBy, setSortBy] = useState<'visits' | 'spent' | 'recent'>('recent');

  // Filter and sort customers
  const filteredCustomers = customers
    .filter((customer) => {
      const matchesSearch =
        `${customer.firstName} ${customer.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
        customer.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        customer.phone.includes(searchQuery);
      const matchesTier = tierFilter === 'all' || customer.membershipTier === tierFilter;
      return matchesSearch && matchesTier;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'visits':
          return b.totalVisits - a.totalVisits;
        case 'spent':
          return b.totalSpent - a.totalSpent;
        case 'recent':
          return new Date(b.lastVisit).getTime() - new Date(a.lastVisit).getTime();
        default:
          return 0;
      }
    });

  // Calculate stats
  const totalCustomers = customers.length;
  const totalSpent = customers.reduce((sum, c) => sum + c.totalSpent, 0);
  const avgLoyaltyPoints = Math.round(customers.reduce((sum, c) => sum + c.loyaltyPoints, 0) / customers.length);
  const platinumCount = customers.filter((c) => c.membershipTier === 'platinum').length;

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Total Customers', value: totalCustomers.toLocaleString(), icon: Users, color: 'indigo', change: '+12%' },
          { label: 'Total Revenue', value: `$${totalSpent.toLocaleString()}`, icon: DollarSign, color: 'emerald', change: '+8%' },
          { label: 'Avg. Loyalty Points', value: avgLoyaltyPoints.toLocaleString(), icon: Star, color: 'amber', change: '+15%' },
          { label: 'Platinum Members', value: platinumCount, icon: Crown, color: 'purple', change: '+2' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{stat.label}</p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">{stat.value}</p>
              </div>
              <div className={cn(
                'flex h-10 w-10 items-center justify-center rounded-lg',
                `bg-${stat.color}-100 dark:bg-${stat.color}-900/30`
              )}>
                <stat.icon className={cn('h-5 w-5', `text-${stat.color}-600 dark:text-${stat.color}-400`)} />
              </div>
            </div>
            <div className="mt-3 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-emerald-500 mr-1" />
              <span className="text-emerald-600 font-medium">{stat.change}</span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">vs last month</span>
            </div>
          </div>
        ))}
      </div>

      {/* Actions bar */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-1 gap-3 w-full sm:w-auto">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 pl-10 pr-4 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          {/* Tier filter */}
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          >
            <option value="all">All Tiers</option>
            <option value="platinum">Platinum</option>
            <option value="gold">Gold</option>
            <option value="silver">Silver</option>
            <option value="bronze">Bronze</option>
          </select>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'visits' | 'spent' | 'recent')}
            className="h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          >
            <option value="recent">Most Recent</option>
            <option value="visits">Most Visits</option>
            <option value="spent">Highest Spend</option>
          </select>
        </div>

        <div className="flex items-center gap-3">
          {/* Export */}
          <button className="flex items-center gap-2 h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Export</span>
          </button>

          {/* Add customer */}
          <Link
            href="/customers/new"
            className="flex items-center gap-2 h-10 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:from-indigo-600 hover:to-purple-700 shadow-lg shadow-indigo-500/25 transition-all"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Add Customer</span>
          </Link>
        </div>
      </div>

      {/* Customer Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredCustomers.map((customer) => {
          const tierStyle = tierStyles[customer.membershipTier];
          const TierIcon = tierStyle.icon;
          return (
            <div
              key={customer.id}
              onClick={() => setSelectedCustomer(customer)}
              className="group relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm hover:shadow-lg hover:border-indigo-300 dark:hover:border-indigo-600 transition-all duration-300 cursor-pointer"
            >
              {/* Header with gradient */}
              <div className={cn(
                'h-16 bg-gradient-to-r',
                tierStyle.gradient
              )} />

              {/* Avatar */}
              <div className="relative px-5 -mt-8">
                <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-xl shadow-lg border-4 border-white dark:border-slate-800">
                  {customer.avatar}
                </div>
              </div>

              {/* Content */}
              <div className="p-5 pt-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">
                      {customer.firstName} {customer.lastName}
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{customer.email}</p>
                  </div>
                  <div className={cn(
                    'flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium capitalize',
                    tierStyle.bg,
                    tierStyle.text
                  )}>
                    <TierIcon className="h-3 w-3" />
                    {customer.membershipTier}
                  </div>
                </div>

                {/* Tags */}
                {customer.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {customer.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-400"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Stats */}
                <div className="mt-4 grid grid-cols-3 gap-3 py-3 border-t border-b border-slate-100 dark:border-slate-700">
                  <div className="text-center">
                    <p className="text-lg font-bold text-slate-900 dark:text-white">{customer.totalVisits}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Visits</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-slate-900 dark:text-white">${customer.totalSpent}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Spent</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-amber-500">{customer.loyaltyPoints}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Points</p>
                  </div>
                </div>

                {/* Footer */}
                <div className="mt-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Last visit: {new Date(customer.lastVisit).toLocaleDateString()}</span>
                  </div>
                  <button className="flex items-center gap-1 text-indigo-600 dark:text-indigo-400 font-medium">
                    View
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filteredCustomers.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center mb-4">
            <Users className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
            No customers found
          </h3>
          <p className="text-slate-500 dark:text-slate-400 mb-6">
            Try adjusting your search or filter criteria
          </p>
          <Link
            href="/customers/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add New Customer
          </Link>
        </div>
      )}

      {/* Customer Detail Slide-over */}
      {selectedCustomer && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedCustomer(null)} />
          <div className="absolute inset-y-0 right-0 w-full max-w-lg">
            <div className="h-full bg-white dark:bg-slate-800 shadow-xl flex flex-col overflow-hidden">
              {/* Header with gradient */}
              <div className={cn(
                'relative h-32 bg-gradient-to-r',
                tierStyles[selectedCustomer.membershipTier].gradient
              )}>
                <button
                  onClick={() => setSelectedCustomer(null)}
                  className="absolute top-4 right-4 p-2 rounded-lg bg-white/20 hover:bg-white/30 text-white backdrop-blur-sm transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
                <div className="absolute -bottom-8 left-6">
                  <div className="flex h-20 w-20 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-2xl shadow-lg border-4 border-white dark:border-slate-800">
                    {selectedCustomer.avatar}
                  </div>
                </div>
              </div>

              {/* Customer info */}
              <div className="pt-12 px-6 pb-4 border-b border-slate-200 dark:border-slate-700">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                      {selectedCustomer.firstName} {selectedCustomer.lastName}
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{selectedCustomer.email}</p>
                  </div>
                  <div className={cn(
                    'flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium capitalize',
                    tierStyles[selectedCustomer.membershipTier].bg,
                    tierStyles[selectedCustomer.membershipTier].text
                  )}>
                    {(() => {
                      const TierIcon = tierStyles[selectedCustomer.membershipTier].icon;
                      return <TierIcon className="h-4 w-4" />;
                    })()}
                    {selectedCustomer.membershipTier}
                  </div>
                </div>
                {selectedCustomer.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {selectedCustomer.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-slate-100 dark:bg-slate-700 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-400"
                      >
                        <Tag className="h-3 w-3 mr-1" />
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Stats */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-700/50 p-4">
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 mb-1">
                      <DollarSign className="h-4 w-4" />
                      <span className="text-xs font-medium">Total Spent</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">
                      ${selectedCustomer.totalSpent.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      ${selectedCustomer.avgSpendPerVisit} avg per visit
                    </p>
                  </div>
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-700/50 p-4">
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 mb-1">
                      <Star className="h-4 w-4" />
                      <span className="text-xs font-medium">Loyalty Points</span>
                    </div>
                    <p className="text-2xl font-bold text-amber-500">
                      {selectedCustomer.loyaltyPoints.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      {selectedCustomer.totalVisits} total visits
                    </p>
                  </div>
                </div>

                {/* Contact Info */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Contact Information</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 text-sm">
                      <Mail className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">{selectedCustomer.email}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <Phone className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">{selectedCustomer.phone}</span>
                    </div>
                    {selectedCustomer.address && (
                      <div className="flex items-center gap-3 text-sm">
                        <MapPin className="h-4 w-4 text-slate-400" />
                        <span className="text-slate-600 dark:text-slate-300">
                          {selectedCustomer.address.city}, {selectedCustomer.address.state}
                        </span>
                      </div>
                    )}
                    {selectedCustomer.birthDate && (
                      <div className="flex items-center gap-3 text-sm">
                        <Gift className="h-4 w-4 text-slate-400" />
                        <span className="text-slate-600 dark:text-slate-300">
                          Birthday: {new Date(selectedCustomer.birthDate).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-sm">
                      <Calendar className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">
                        Member since {new Date(selectedCustomer.joinDate).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Notes */}
                {selectedCustomer.notes && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Notes</h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                      {selectedCustomer.notes}
                    </p>
                  </div>
                )}

                {/* Recent Bookings */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Recent Bookings</h3>
                  <div className="space-y-2">
                    {selectedCustomer.recentBookings.map((booking) => (
                      <div
                        key={booking.id}
                        className="flex items-center justify-between rounded-lg bg-slate-50 dark:bg-slate-700/50 p-3"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">{booking.venue}</p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            {new Date(booking.date).toLocaleDateString()} - {booking.id}
                          </p>
                        </div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">
                          ${booking.amount}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="border-t border-slate-200 dark:border-slate-700 p-6 flex gap-3">
                <button className="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
                  <MessageSquare className="h-4 w-4" />
                  Send Message
                </button>
                <button className="flex items-center justify-center gap-2 h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                  <Edit className="h-4 w-4" />
                  Edit
                </button>
                <button className="flex items-center justify-center h-10 px-4 rounded-lg border border-red-200 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
