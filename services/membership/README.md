# Membership Service

A comprehensive membership management microservice for the FEC SaaS platform. This service handles subscriptions, loyalty programs, rewards, family memberships, corporate subscriptions, and referral programs.

## Key Business Metrics Targets

- **Reduce Churn**: From 68% to 31%
- **Increase LTV**: From $340 to $1,240
- **Subscription Retention**: 87%
- **MRR Growth**: Target $180K

## Features

### Subscription Management
- Multiple subscription plans per venue
- Flexible billing intervals (weekly, monthly, quarterly, semi-annual, annual)
- Trial periods with automatic conversion
- Subscription pause/resume functionality
- Upgrade/downgrade with proration
- Usage-based limits and tracking
- Automated renewal processing
- Dunning for failed payments

### Loyalty Programs
- Points earning based on spend
- Tier multipliers for bonus points
- Points expiration management
- Tier progression tracking
- Point transfers between accounts
- Birthday and promotional bonuses

### Rewards Catalog
- Multiple reward types (discounts, free items, experiences)
- Points-based redemption
- Quantity limits and availability tracking
- Tier-restricted rewards
- Redemption code generation
- Expiration management

### Family Memberships
- Shared subscription plans
- Family member management
- Shared points pool
- Primary member transfer

### Corporate Subscriptions
- Company-wide plans
- Employee management
- Bulk employee onboarding
- Volume discounts
- Contract management

### Referral Program
- Unique referral codes
- Dual-sided rewards
- Referral tracking and completion
- Leaderboards
- Expiration management

### Analytics
- MRR (Monthly Recurring Revenue)
- Churn rate tracking
- Customer Lifetime Value (LTV)
- Loyalty program metrics
- Rewards redemption analytics
- Referral performance

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Cache**: Redis
- **Message Queue**: RabbitMQ
- **Authentication**: JWT tokens
- **Migrations**: Alembic

## Project Structure

```
services/membership/
├── alembic/                 # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── subscriptions.py
│   │       ├── loyalty.py
│   │       ├── rewards.py
│   │       ├── family.py
│   │       ├── corporate.py
│   │       ├── referrals.py
│   │       ├── analytics.py
│   │       └── tiers.py
│   ├── core/
│   │   ├── auth.py
│   │   └── database.py
│   ├── models/
│   │   ├── base.py
│   │   └── membership.py
│   ├── schemas/
│   │   └── membership.py
│   ├── services/
│   │   ├── subscription_service.py
│   │   ├── loyalty_service.py
│   │   ├── rewards_service.py
│   │   ├── family_service.py
│   │   ├── corporate_service.py
│   │   ├── referral_service.py
│   │   └── event_publisher.py
│   ├── config.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_subscriptions.py
│   ├── test_loyalty.py
│   └── test_api.py
├── .env.example
├── alembic.ini
├── pyproject.toml
├── README.md
├── SETUP_GUIDE.md
└── TESTING_GUIDE.md
```

## Database Models (17 Tables)

1. **MembershipTier** - Membership levels (Bronze, Silver, Gold, etc.)
2. **SubscriptionPlan** - Available subscription plans
3. **CustomerSubscription** - Customer subscriptions
4. **SubscriptionInvoice** - Billing invoices
5. **SubscriptionUsageLimit** - Plan usage limits
6. **SubscriptionPause** - Pause history
7. **DunningAttempt** - Failed payment retries
8. **LoyaltyProgram** - Loyalty program configuration
9. **CustomerLoyaltyAccount** - Customer loyalty accounts
10. **LoyaltyTransaction** - Points transactions
11. **RewardsCatalog** - Available rewards
12. **RewardRedemption** - Reward redemptions
13. **FamilyMembership** - Family plans
14. **FamilyMembershipMember** - Family members
15. **CorporateSubscription** - Corporate plans
16. **CorporateSubscriptionEmployee** - Corporate employees
17. **ReferralReward** - Referral tracking

## API Endpoints

### Subscriptions
- `POST /api/v1/subscriptions/plans` - Create subscription plan
- `GET /api/v1/subscriptions/plans` - List plans
- `POST /api/v1/subscriptions` - Subscribe customer
- `POST /api/v1/subscriptions/{id}/pause` - Pause subscription
- `POST /api/v1/subscriptions/{id}/resume` - Resume subscription
- `POST /api/v1/subscriptions/{id}/cancel` - Cancel subscription
- `POST /api/v1/subscriptions/{id}/change-plan` - Upgrade/downgrade

### Loyalty
- `POST /api/v1/loyalty/programs` - Create loyalty program
- `POST /api/v1/loyalty/accounts/enroll` - Enroll in program
- `POST /api/v1/loyalty/accounts/{id}/earn` - Earn points
- `POST /api/v1/loyalty/accounts/{id}/redeem` - Redeem points
- `GET /api/v1/loyalty/accounts/{id}/transactions` - Transaction history

### Rewards
- `POST /api/v1/rewards/catalog` - Add reward to catalog
- `GET /api/v1/rewards/catalog` - List rewards
- `POST /api/v1/rewards/redeem` - Redeem reward
- `POST /api/v1/rewards/redemptions/{id}/fulfill` - Fulfill redemption

### Family
- `POST /api/v1/family` - Create family membership
- `POST /api/v1/family/{id}/members` - Add family member
- `POST /api/v1/family/{id}/points-pool/contribute` - Contribute to pool

### Corporate
- `POST /api/v1/corporate` - Create corporate subscription
- `POST /api/v1/corporate/{id}/employees` - Add employee
- `POST /api/v1/corporate/{id}/employees/bulk` - Bulk add employees
- `GET /api/v1/corporate/check-access/{email}` - Check employee access

### Referrals
- `POST /api/v1/referrals/code` - Create referral code
- `POST /api/v1/referrals/use` - Use referral code
- `GET /api/v1/referrals/validate/{code}` - Validate code
- `GET /api/v1/referrals/venue/{id}/leaderboard` - Referral leaderboard

### Analytics
- `GET /api/v1/analytics/mrr` - MRR metrics
- `GET /api/v1/analytics/churn` - Churn analytics
- `GET /api/v1/analytics/ltv` - LTV metrics
- `GET /api/v1/analytics/dashboard` - Summary dashboard

## Quick Start

```bash
# Clone and navigate
cd services/membership

# Install dependencies
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Run migrations
alembic upgrade head

# Start service
poetry run uvicorn app.main:app --reload --port 8005
```

## Events Published

The service publishes events to RabbitMQ for integration with other services:

- `subscription.created`, `subscription.activated`, `subscription.cancelled`
- `invoice.created`, `invoice.paid`, `invoice.failed`
- `loyalty.points_earned`, `loyalty.points_redeemed`
- `tier.upgraded`, `tier.downgraded`
- `reward.redeemed`, `reward.fulfilled`
- `referral.created`, `referral.completed`
- `dunning.started`, `dunning.recovered`, `dunning.failed`

## Integration Points

- **Payment Gateway Service**: For processing subscription payments
- **Customer Service**: For customer data
- **Notification Service**: For sending alerts and reminders
- **AI Services**: For churn prediction integration

## Environment Variables

See `.env.example` for all configuration options.

## Documentation

- **Setup Guide**: See [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- **Testing Guide**: See [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **API Docs**: Available at `/docs` when running
