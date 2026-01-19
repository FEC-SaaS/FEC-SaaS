"""Add industry-leading features.

Revision ID: 005
Revises: 004
Create Date: 2025-01-18

Features added:
- Family account linking (Embed/Sacoa)
- Loyalty tier system (Intercard)
- Parental controls (Embed)
- Membership system (Omnify)
- User preferences (Toast/Sacoa)
- Card protection (Embed)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (with IF NOT EXISTS via DO block for PostgreSQL)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE loyalty_tier_enum AS ENUM ('BRONZE', 'SILVER', 'GOLD', 'PLATINUM');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE membership_status_enum AS ENUM ('ACTIVE', 'FROZEN', 'CANCELLED', 'EXPIRED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE family_role_enum AS ENUM ('PARENT', 'GUARDIAN', 'CHILD', 'DEPENDENT');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Add new columns to users table (idempotent)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN date_of_birth TIMESTAMP;
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en';
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN preferred_currency VARCHAR(3) DEFAULT 'USD';
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN loyalty_tier loyalty_tier_enum DEFAULT 'BRONZE';
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN loyalty_points INTEGER DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN lifetime_points INTEGER DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN accessibility_needs JSONB;
        EXCEPTION WHEN duplicate_column THEN null; END $$;
    """)

    # Create tables using raw SQL with IF NOT EXISTS
    op.execute("""
        CREATE TABLE IF NOT EXISTS family_groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            primary_contact_id UUID NOT NULL,
            shared_rewards_enabled BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            family_id UUID NOT NULL REFERENCES family_groups(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            family_role family_role_enum DEFAULT 'DEPENDENT',
            nickname VARCHAR(50),
            can_manage_family BOOLEAN DEFAULT false,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_family_user UNIQUE (family_id, user_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS parental_controls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            child_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            daily_spend_limit DECIMAL(10, 2),
            hourly_spend_limit DECIMAL(10, 2),
            total_balance_limit DECIMAL(10, 2),
            allowed_play_start TIME,
            allowed_play_end TIME,
            blackout_dates JSONB,
            restricted_game_types JSONB,
            age_restriction_override BOOLEAN DEFAULT false,
            activity_notifications BOOLEAN DEFAULT true,
            low_balance_alerts BOOLEAN DEFAULT true,
            spend_alerts BOOLEAN DEFAULT true,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_parent_child UNIQUE (parent_id, child_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS membership_plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            venue_id UUID,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            plan_type VARCHAR(50) NOT NULL,
            billing_period VARCHAR(20) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            free_games_per_period INTEGER DEFAULT 0,
            discount_percentage DECIMAL(5, 2) DEFAULT 0,
            priority_booking BOOLEAN DEFAULT false,
            guest_passes_per_period INTEGER DEFAULT 0,
            bonus_points_multiplier DECIMAL(3, 2) DEFAULT 1.0,
            max_freezes_per_year INTEGER DEFAULT 2,
            freeze_duration_days INTEGER DEFAULT 30,
            min_commitment_months INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID NOT NULL REFERENCES membership_plans(id),
            venue_id UUID,
            status membership_status_enum DEFAULT 'ACTIVE',
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP,
            next_billing_date TIMESTAMP,
            freeze_start_date TIMESTAMP,
            freeze_end_date TIMESTAMP,
            freezes_used_this_year INTEGER DEFAULT 0,
            games_used_this_period INTEGER DEFAULT 0,
            guest_passes_used_this_period INTEGER DEFAULT 0,
            auto_renew BOOLEAN DEFAULT true,
            cancellation_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            preference_key VARCHAR(100) NOT NULL,
            preference_value JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_user_preference UNIQUE (user_id, preference_key)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS card_protections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_identifier VARCHAR(100) NOT NULL,
            card_type VARCHAR(50) DEFAULT 'GAME_CARD',
            is_active BOOLEAN DEFAULT true,
            is_frozen BOOLEAN DEFAULT false,
            frozen_at TIMESTAMP,
            frozen_reason TEXT,
            reported_lost_at TIMESTAMP,
            balance_at_loss DECIMAL(10, 2),
            balance_transferred BOOLEAN DEFAULT false,
            transferred_to_card VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes (IF NOT EXISTS)
    op.execute("CREATE INDEX IF NOT EXISTS idx_family_members_family_id ON family_members(family_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_family_members_user_id ON family_members(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parental_controls_parent_id ON parental_controls(parent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parental_controls_child_id ON parental_controls(child_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON memberships(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memberships_status ON memberships(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_card_protections_user_id ON card_protections(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_loyalty_tier ON users(loyalty_tier)")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_users_loyalty_tier', table_name='users')
    op.drop_index('idx_card_protections_user_id', table_name='card_protections')
    op.drop_index('idx_user_preferences_user_id', table_name='user_preferences')
    op.drop_index('idx_memberships_status', table_name='memberships')
    op.drop_index('idx_memberships_user_id', table_name='memberships')
    op.drop_index('idx_parental_controls_child_id', table_name='parental_controls')
    op.drop_index('idx_parental_controls_parent_id', table_name='parental_controls')
    op.drop_index('idx_family_members_user_id', table_name='family_members')
    op.drop_index('idx_family_members_family_id', table_name='family_members')

    # Drop tables
    op.drop_table('card_protections')
    op.drop_table('user_preferences')
    op.drop_table('memberships')
    op.drop_table('membership_plans')
    op.drop_table('parental_controls')
    op.drop_table('family_members')
    op.drop_table('family_groups')

    # Drop columns from users
    op.drop_column('users', 'accessibility_needs')
    op.drop_column('users', 'lifetime_points')
    op.drop_column('users', 'loyalty_points')
    op.drop_column('users', 'loyalty_tier')
    op.drop_column('users', 'preferred_currency')
    op.drop_column('users', 'preferred_language')
    op.drop_column('users', 'date_of_birth')

    # Drop enum types
    op.execute("DROP TYPE family_role_enum")
    op.execute("DROP TYPE membership_status_enum")
    op.execute("DROP TYPE loyalty_tier_enum")
