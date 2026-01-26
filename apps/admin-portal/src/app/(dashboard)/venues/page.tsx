/**
 * =============================================================================
 * FILE: (dashboard)/venues/page.tsx
 * PURPOSE: Venue management page with listing, search, and details view
 * =============================================================================
 *
 * This page provides comprehensive venue management functionality:
 * - Grid/List view toggle for venues
 * - Search and filter capabilities
 * - Venue cards with key metrics
 * - Quick actions (edit, delete, view)
 * - Venue details panel
 * - Add new venue functionality
 *
 * FEATURES:
 * - Responsive grid layout
 * - Status indicators (active, inactive, maintenance)
 * - Revenue and booking stats per venue
 * - Operating hours display
 * - Contact information
 *
 * =============================================================================
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  MapPin,
  Phone,
  Mail,
  Clock,
  Users,
  DollarSign,
  Star,
  TrendingUp,
  TrendingDown,
  Grid3X3,
  List,
  MoreVertical,
  Edit,
  Trash2,
  Eye,
  ExternalLink,
  ChevronRight,
  Filter,
  Download,
  Settings,
  Gamepad2,
  X,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';

/**
 * Venue interface
 */
interface Venue {
  id: string;
  name: string;
  description: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  phone: string;
  email: string;
  website?: string;
  status: 'active' | 'inactive' | 'maintenance';
  totalAttractions: number;
  capacity: number;
  todayBookings: number;
  monthlyRevenue: number;
  monthlyGrowth: number;
  rating: number;
  reviewCount: number;
  image: string;
  operatingHours: {
    weekday: string;
    weekend: string;
    sunday: string;
  };
}

/**
 * Mock venue data
 */
const venues: Venue[] = [
  {
    id: '1',
    name: 'FunZone Downtown',
    description: 'Our flagship entertainment center with arcade games, laser tag, and party rooms.',
    address: '123 Main Street',
    city: 'Austin',
    state: 'TX',
    zipCode: '78701',
    phone: '(512) 555-0100',
    email: 'downtown@funzone.com',
    website: 'https://funzone.com/downtown',
    status: 'active',
    totalAttractions: 24,
    capacity: 350,
    todayBookings: 8,
    monthlyRevenue: 45230,
    monthlyGrowth: 15.2,
    rating: 4.8,
    reviewCount: 324,
    image: '🎮',
    operatingHours: {
      weekday: '10:00 AM - 9:00 PM',
      weekend: '10:00 AM - 11:00 PM',
      sunday: '11:00 AM - 8:00 PM',
    },
  },
  {
    id: '2',
    name: 'Adventure Park',
    description: 'Outdoor and indoor attractions including go-karts, mini golf, and climbing walls.',
    address: '456 Oak Avenue',
    city: 'Dallas',
    state: 'TX',
    zipCode: '75201',
    phone: '(214) 555-0200',
    email: 'adventure@funzone.com',
    website: 'https://funzone.com/adventure',
    status: 'active',
    totalAttractions: 32,
    capacity: 500,
    todayBookings: 12,
    monthlyRevenue: 38750,
    monthlyGrowth: 8.5,
    rating: 4.6,
    reviewCount: 256,
    image: '🎢',
    operatingHours: {
      weekday: '10:00 AM - 10:00 PM',
      weekend: '9:00 AM - 11:00 PM',
      sunday: '10:00 AM - 9:00 PM',
    },
  },
  {
    id: '3',
    name: 'FunZone Mall',
    description: 'Family entertainment destination inside the Grand Mall with VR experiences.',
    address: '789 Commerce Blvd',
    city: 'Houston',
    state: 'TX',
    zipCode: '77002',
    phone: '(713) 555-0300',
    email: 'mall@funzone.com',
    status: 'active',
    totalAttractions: 18,
    capacity: 275,
    todayBookings: 5,
    monthlyRevenue: 31200,
    monthlyGrowth: 12.1,
    rating: 4.7,
    reviewCount: 189,
    image: '🎯',
    operatingHours: {
      weekday: '10:00 AM - 9:00 PM',
      weekend: '10:00 AM - 10:00 PM',
      sunday: '12:00 PM - 7:00 PM',
    },
  },
  {
    id: '4',
    name: 'Kids Paradise',
    description: 'Dedicated play area for children ages 2-12 with soft play and toddler zones.',
    address: '321 Family Lane',
    city: 'San Antonio',
    state: 'TX',
    zipCode: '78205',
    phone: '(210) 555-0400',
    email: 'paradise@funzone.com',
    status: 'maintenance',
    totalAttractions: 20,
    capacity: 200,
    todayBookings: 0,
    monthlyRevenue: 28400,
    monthlyGrowth: -2.3,
    rating: 4.4,
    reviewCount: 142,
    image: '🎪',
    operatingHours: {
      weekday: '9:00 AM - 7:00 PM',
      weekend: '9:00 AM - 8:00 PM',
      sunday: '10:00 AM - 6:00 PM',
    },
  },
  {
    id: '5',
    name: 'Splash Zone',
    description: 'Water park and aquatic entertainment center with pools and water slides.',
    address: '555 Water Way',
    city: 'Austin',
    state: 'TX',
    zipCode: '78702',
    phone: '(512) 555-0500',
    email: 'splash@funzone.com',
    status: 'inactive',
    totalAttractions: 15,
    capacity: 400,
    todayBookings: 0,
    monthlyRevenue: 0,
    monthlyGrowth: 0,
    rating: 4.5,
    reviewCount: 98,
    image: '🌊',
    operatingHours: {
      weekday: 'Closed for season',
      weekend: 'Closed for season',
      sunday: 'Closed for season',
    },
  },
];

/**
 * Status badge styles
 */
const statusStyles = {
  active: {
    bg: 'bg-emerald-100 dark:bg-emerald-900/30',
    text: 'text-emerald-700 dark:text-emerald-400',
    dot: 'bg-emerald-500',
  },
  inactive: {
    bg: 'bg-slate-100 dark:bg-slate-700',
    text: 'text-slate-600 dark:text-slate-400',
    dot: 'bg-slate-400',
  },
  maintenance: {
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-400',
    dot: 'bg-amber-500',
  },
};

export default function VenuesPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedVenue, setSelectedVenue] = useState<Venue | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Filter venues
  const filteredVenues = venues.filter((venue) => {
    const matchesSearch =
      venue.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      venue.city.toLowerCase().includes(searchQuery.toLowerCase()) ||
      venue.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || venue.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Calculate stats
  const totalVenues = venues.length;
  const activeVenues = venues.filter((v) => v.status === 'active').length;
  const totalRevenue = venues.reduce((sum, v) => sum + v.monthlyRevenue, 0);
  const todayBookings = venues.reduce((sum, v) => sum + v.todayBookings, 0);

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Total Venues', value: totalVenues, icon: MapPin, color: 'indigo' },
          { label: 'Active Venues', value: activeVenues, icon: Gamepad2, color: 'emerald' },
          { label: 'Monthly Revenue', value: `$${totalRevenue.toLocaleString()}`, icon: DollarSign, color: 'blue' },
          { label: "Today's Bookings", value: todayBookings, icon: Users, color: 'purple' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4"
          >
            <div className="flex items-center gap-3">
              <div className={cn(
                'flex h-10 w-10 items-center justify-center rounded-lg',
                `bg-${stat.color}-100 dark:bg-${stat.color}-900/30`
              )}>
                <stat.icon className={cn('h-5 w-5', `text-${stat.color}-600 dark:text-${stat.color}-400`)} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{stat.value}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
              </div>
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
              placeholder="Search venues..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 pl-10 pr-4 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="maintenance">Maintenance</option>
          </select>
        </div>

        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'flex items-center justify-center h-8 w-8 rounded-md transition-colors',
                viewMode === 'grid'
                  ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
              )}
            >
              <Grid3X3 className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center justify-center h-8 w-8 rounded-md transition-colors',
                viewMode === 'list'
                  ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
              )}
            >
              <List className="h-4 w-4" />
            </button>
          </div>

          {/* Export */}
          <button className="flex items-center gap-2 h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Export</span>
          </button>

          {/* Add venue */}
          <Link
            href="/venues/new"
            className="flex items-center gap-2 h-10 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:from-indigo-600 hover:to-purple-700 shadow-lg shadow-indigo-500/25 transition-all"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Add Venue</span>
          </Link>
        </div>
      </div>

      {/* Venues Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredVenues.map((venue) => (
            <div
              key={venue.id}
              onClick={() => setSelectedVenue(venue)}
              className="group relative overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm hover:shadow-xl hover:border-indigo-300 dark:hover:border-indigo-600 transition-all duration-300 cursor-pointer"
            >
              {/* Header */}
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-700 text-3xl">
                      {venue.image}
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                        {venue.name}
                      </h3>
                      <div className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400">
                        <MapPin className="h-3 w-3" />
                        {venue.city}, {venue.state}
                      </div>
                    </div>
                  </div>
                  <div className={cn(
                    'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
                    statusStyles[venue.status].bg,
                    statusStyles[venue.status].text
                  )}>
                    <div className={cn('h-1.5 w-1.5 rounded-full', statusStyles[venue.status].dot)} />
                    {venue.status}
                  </div>
                </div>

                <p className="mt-3 text-sm text-slate-500 dark:text-slate-400 line-clamp-2">
                  {venue.description}
                </p>

                {/* Stats */}
                <div className="mt-4 grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-lg font-bold text-slate-900 dark:text-white">
                      ${(venue.monthlyRevenue / 1000).toFixed(1)}k
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Revenue</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-slate-900 dark:text-white">
                      {venue.todayBookings}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Bookings</p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Star className="h-4 w-4 text-amber-500 fill-current" />
                      <span className="text-lg font-bold text-slate-900 dark:text-white">
                        {venue.rating}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{venue.reviewCount} reviews</p>
                  </div>
                </div>

                {/* Growth indicator */}
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-slate-500 dark:text-slate-400">Monthly growth</span>
                  <div className={cn(
                    'flex items-center gap-1',
                    venue.monthlyGrowth >= 0 ? 'text-emerald-600' : 'text-red-600'
                  )}>
                    {venue.monthlyGrowth >= 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    <span className="font-medium">
                      {venue.monthlyGrowth >= 0 ? '+' : ''}{venue.monthlyGrowth}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="border-t border-slate-100 dark:border-slate-700 p-4 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
                <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                  <span className="flex items-center gap-1">
                    <Gamepad2 className="h-3.5 w-3.5" />
                    {venue.totalAttractions} attractions
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" />
                    {venue.capacity} capacity
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedVenue(venue);
                  }}
                  className="flex items-center gap-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
                >
                  View details
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Venue
                  </th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Attractions
                  </th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Today
                  </th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Revenue
                  </th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Rating
                  </th>
                  <th className="text-right px-6 py-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {filteredVenues.map((venue) => (
                  <tr
                    key={venue.id}
                    onClick={() => setSelectedVenue(venue)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-700 text-xl">
                          {venue.image}
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">{venue.name}</p>
                          <p className="text-sm text-slate-500 dark:text-slate-400">
                            {venue.city}, {venue.state}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
                        statusStyles[venue.status].bg,
                        statusStyles[venue.status].text
                      )}>
                        <div className={cn('h-1.5 w-1.5 rounded-full', statusStyles[venue.status].dot)} />
                        {venue.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-600 dark:text-slate-300">
                      {venue.totalAttractions}
                    </td>
                    <td className="px-6 py-4 text-slate-600 dark:text-slate-300">
                      {venue.todayBookings} bookings
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          ${venue.monthlyRevenue.toLocaleString()}
                        </p>
                        <div className={cn(
                          'flex items-center gap-1 text-xs',
                          venue.monthlyGrowth >= 0 ? 'text-emerald-600' : 'text-red-600'
                        )}>
                          {venue.monthlyGrowth >= 0 ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          {venue.monthlyGrowth >= 0 ? '+' : ''}{venue.monthlyGrowth}%
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 text-amber-500 fill-current" />
                        <span className="font-medium text-slate-900 dark:text-white">{venue.rating}</span>
                        <span className="text-sm text-slate-500 dark:text-slate-400">
                          ({venue.reviewCount})
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedVenue(venue);
                          }}
                          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-600 text-slate-500 dark:text-slate-400"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => e.stopPropagation()}
                          className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-600 text-slate-500 dark:text-slate-400"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => e.stopPropagation()}
                          className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {filteredVenues.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center mb-4">
            <MapPin className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
            No venues found
          </h3>
          <p className="text-slate-500 dark:text-slate-400 mb-6">
            Try adjusting your search or filter criteria
          </p>
          <Link
            href="/venues/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add New Venue
          </Link>
        </div>
      )}

      {/* Venue Detail Slide-over */}
      {selectedVenue && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedVenue(null)} />
          <div className="absolute inset-y-0 right-0 w-full max-w-lg">
            <div className="h-full bg-white dark:bg-slate-800 shadow-xl flex flex-col overflow-hidden">
              {/* Header */}
              <div className="flex items-start justify-between p-6 border-b border-slate-200 dark:border-slate-700">
                <div className="flex items-center gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-700 text-4xl">
                    {selectedVenue.image}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                      {selectedVenue.name}
                    </h2>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={cn(
                        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
                        statusStyles[selectedVenue.status].bg,
                        statusStyles[selectedVenue.status].text
                      )}>
                        <div className={cn('h-1.5 w-1.5 rounded-full', statusStyles[selectedVenue.status].dot)} />
                        {selectedVenue.status}
                      </span>
                      <div className="flex items-center gap-1 text-sm text-amber-500">
                        <Star className="h-4 w-4 fill-current" />
                        {selectedVenue.rating}
                      </div>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedVenue(null)}
                  className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Description */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">About</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{selectedVenue.description}</p>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-700/50 p-4">
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 mb-1">
                      <DollarSign className="h-4 w-4" />
                      <span className="text-xs font-medium">Monthly Revenue</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">
                      ${selectedVenue.monthlyRevenue.toLocaleString()}
                    </p>
                    <div className={cn(
                      'flex items-center gap-1 text-xs mt-1',
                      selectedVenue.monthlyGrowth >= 0 ? 'text-emerald-600' : 'text-red-600'
                    )}>
                      {selectedVenue.monthlyGrowth >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {selectedVenue.monthlyGrowth >= 0 ? '+' : ''}{selectedVenue.monthlyGrowth}% vs last month
                    </div>
                  </div>
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-700/50 p-4">
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 mb-1">
                      <Users className="h-4 w-4" />
                      <span className="text-xs font-medium">Today&apos;s Bookings</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">
                      {selectedVenue.todayBookings}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      {selectedVenue.capacity} max capacity
                    </p>
                  </div>
                </div>

                {/* Contact Info */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Contact Information</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 text-sm">
                      <MapPin className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">
                        {selectedVenue.address}, {selectedVenue.city}, {selectedVenue.state} {selectedVenue.zipCode}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <Phone className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">{selectedVenue.phone}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <Mail className="h-4 w-4 text-slate-400" />
                      <span className="text-slate-600 dark:text-slate-300">{selectedVenue.email}</span>
                    </div>
                    {selectedVenue.website && (
                      <div className="flex items-center gap-3 text-sm">
                        <ExternalLink className="h-4 w-4 text-slate-400" />
                        <a
                          href={selectedVenue.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                          {selectedVenue.website}
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* Operating Hours */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Operating Hours</h3>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500 dark:text-slate-400">Mon - Thu:</span>
                      <span className="text-slate-900 dark:text-white">{selectedVenue.operatingHours.weekday}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500 dark:text-slate-400">Fri - Sat:</span>
                      <span className="text-slate-900 dark:text-white">{selectedVenue.operatingHours.weekend}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-500 dark:text-slate-400">Sunday:</span>
                      <span className="text-slate-900 dark:text-white">{selectedVenue.operatingHours.sunday}</span>
                    </div>
                  </div>
                </div>

                {/* Attractions */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Attractions</h3>
                  <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <Gamepad2 className="h-4 w-4 text-slate-400" />
                    <span>{selectedVenue.totalAttractions} attractions available</span>
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="border-t border-slate-200 dark:border-slate-700 p-6 flex gap-3">
                <Link
                  href={`/venues/${selectedVenue.id}`}
                  className="flex-1 flex items-center justify-center gap-2 h-10 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
                >
                  <Eye className="h-4 w-4" />
                  View Full Details
                </Link>
                <button className="flex items-center justify-center gap-2 h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                  <Edit className="h-4 w-4" />
                  Edit
                </button>
                <button className="flex items-center justify-center h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                  <Settings className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
