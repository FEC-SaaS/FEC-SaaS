"""Initial payment gateway tables

Revision ID: 001
Revises:
Create Date: 2024-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE processortype AS ENUM ('stripe', 'square', 'paypal', 'braintree', 'adyen')")
    op.execute("CREATE TYPE paymentmethodtype AS ENUM ('card', 'bank_account', 'digital_wallet', 'buy_now_pay_later')")
    op.execute("CREATE TYPE cardbrand AS ENUM ('visa', 'mastercard', 'amex', 'discover', 'diners', 'jcb', 'unionpay')")
    op.execute("CREATE TYPE transactiontype AS ENUM ('charge', 'authorization', 'capture', 'void', 'refund', 'recurring')")
    op.execute("CREATE TYPE transactionstatus AS ENUM ('pending', 'authorized', 'captured', 'completed', 'failed', 'declined', 'voided', 'refunded', 'partially_refunded', 'disputed', 'fraud_blocked')")
    op.execute("CREATE TYPE refundtype AS ENUM ('full', 'partial')")
    op.execute("CREATE TYPE refundstatus AS ENUM ('pending', 'completed', 'failed')")
    op.execute("CREATE TYPE billinginterval AS ENUM ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')")
    op.execute("CREATE TYPE subscriptionstatus AS ENUM ('pending', 'active', 'paused', 'cancelled', 'expired', 'past_due')")
    op.execute("CREATE TYPE fraudruletype AS ENUM ('velocity', 'amount_threshold', 'geo_location', 'card_bin', 'device_fingerprint', 'ip_address', 'custom')")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE fraudalertstatus AS ENUM ('pending', 'approved', 'rejected', 'escalated')")
    op.execute("CREATE TYPE recommendedaction AS ENUM ('allow', 'flag', 'manual_review', 'block')")
    op.execute("CREATE TYPE disputetype AS ENUM ('chargeback', 'inquiry', 'retrieval', 'fraud', 'duplicate', 'subscription_canceled', 'product_unacceptable', 'product_not_received', 'credit_not_processed', 'general')")
    op.execute("CREATE TYPE disputestatus AS ENUM ('open', 'under_review', 'won', 'lost', 'closed')")
    op.execute("CREATE TYPE compliancestatus AS ENUM ('compliant', 'non_compliant', 'pending_review', 'remediation_required')")

    # Payment Processors table
    op.create_table(
        'payment_processors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('processor_name', sa.String(50), nullable=False),
        sa.Column('processor_type', postgresql.ENUM('stripe', 'square', 'paypal', 'braintree', 'adyen', name='processortype', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('supported_methods', postgresql.JSONB(), default=[]),
        sa.Column('supported_currencies', postgresql.JSONB(), default=[]),
        sa.Column('api_version', sa.String(20)),
        sa.Column('fee_structure', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_payment_processors_type', 'payment_processors', ['processor_type'])

    # Venue Payment Configs table
    op.create_table(
        'venue_payment_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('processor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_processors.id'), nullable=False),
        sa.Column('merchant_id', sa.String(255)),
        sa.Column('api_credentials', postgresql.JSONB()),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('settings', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_venue_payment_configs_venue', 'venue_payment_configs', ['venue_id'])

    # Customer Payment Methods table
    op.create_table(
        'customer_payment_methods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payment_method_type', postgresql.ENUM('card', 'bank_account', 'digital_wallet', 'buy_now_pay_later', name='paymentmethodtype', create_type=False), nullable=False),
        sa.Column('processor_token', sa.Text(), nullable=False),
        sa.Column('processor_customer_id', sa.String(255)),
        sa.Column('card_brand', postgresql.ENUM('visa', 'mastercard', 'amex', 'discover', 'diners', 'jcb', 'unionpay', name='cardbrand', create_type=False)),
        sa.Column('card_last_four', sa.String(4)),
        sa.Column('card_exp_month', sa.Integer()),
        sa.Column('card_exp_year', sa.Integer()),
        sa.Column('card_fingerprint', sa.String(255)),
        sa.Column('billing_address', postgresql.JSONB()),
        sa.Column('nickname', sa.String(100)),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_customer_payment_methods_customer', 'customer_payment_methods', ['customer_id'])
    op.create_index('ix_customer_payment_methods_venue', 'customer_payment_methods', ['venue_id'])

    # Payment Transactions table
    op.create_table(
        'payment_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True)),
        sa.Column('payment_method_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer_payment_methods.id')),
        sa.Column('config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venue_payment_configs.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('transaction_type', postgresql.ENUM('charge', 'authorization', 'capture', 'void', 'refund', 'recurring', name='transactiontype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'authorized', 'captured', 'completed', 'failed', 'declined', 'voided', 'refunded', 'partially_refunded', 'disputed', 'fraud_blocked', name='transactionstatus', create_type=False), default='pending'),
        sa.Column('processor_transaction_id', sa.String(255)),
        sa.Column('authorization_code', sa.String(50)),
        sa.Column('processor_fee', sa.Numeric(10, 2)),
        sa.Column('net_amount', sa.Numeric(12, 2)),
        sa.Column('error_code', sa.String(50)),
        sa.Column('error_message', sa.Text()),
        sa.Column('decline_code', sa.String(50)),
        sa.Column('fraud_score', sa.Numeric(5, 2)),
        sa.Column('fraud_check_passed', sa.Boolean()),
        sa.Column('description', sa.String(500)),
        sa.Column('order_id', postgresql.UUID(as_uuid=True)),
        sa.Column('invoice_id', sa.String(100)),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True)),
        sa.Column('receipt_url', sa.String(500)),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('raw_response', postgresql.JSONB()),
        sa.Column('idempotency_key', sa.String(255)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('device_fingerprint', sa.String(255)),
        sa.Column('initiated_by', postgresql.UUID(as_uuid=True)),
        sa.Column('captured_amount', sa.Numeric(12, 2)),
        sa.Column('refunded_amount', sa.Numeric(12, 2), default=0),
        sa.Column('authorized_at', sa.DateTime(timezone=True)),
        sa.Column('captured_at', sa.DateTime(timezone=True)),
        sa.Column('voided_at', sa.DateTime(timezone=True)),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_payment_transactions_venue', 'payment_transactions', ['venue_id'])
    op.create_index('ix_payment_transactions_customer', 'payment_transactions', ['customer_id'])
    op.create_index('ix_payment_transactions_status', 'payment_transactions', ['status'])
    op.create_index('ix_payment_transactions_created', 'payment_transactions', ['created_at'])
    op.create_index('ix_payment_transactions_processor', 'payment_transactions', ['processor_transaction_id'], unique=True)

    # Payment Refunds table
    op.create_table(
        'payment_refunds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_transactions.id'), nullable=False),
        sa.Column('refund_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('refund_reason', sa.String(100)),
        sa.Column('refund_type', postgresql.ENUM('full', 'partial', name='refundtype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'completed', 'failed', name='refundstatus', create_type=False), default='pending'),
        sa.Column('processor_refund_id', sa.String(255)),
        sa.Column('failure_reason', sa.Text()),
        sa.Column('notes', sa.Text()),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('initiated_by', postgresql.UUID(as_uuid=True)),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_payment_refunds_payment', 'payment_refunds', ['original_payment_id'])

    # Subscription Payments table
    op.create_table(
        'subscription_payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('membership_id', postgresql.UUID(as_uuid=True)),
        sa.Column('payment_method_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customer_payment_methods.id'), nullable=False),
        sa.Column('config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venue_payment_configs.id'), nullable=False),
        sa.Column('processor_subscription_id', sa.String(255)),
        sa.Column('plan_name', sa.String(100), nullable=False),
        sa.Column('billing_interval', postgresql.ENUM('daily', 'weekly', 'monthly', 'quarterly', 'yearly', name='billinginterval', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'paused', 'cancelled', 'expired', 'past_due', name='subscriptionstatus', create_type=False), default='pending'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('current_period_start', sa.Date()),
        sa.Column('current_period_end', sa.Date()),
        sa.Column('next_billing_date', sa.Date()),
        sa.Column('cancelled_at', sa.DateTime(timezone=True)),
        sa.Column('paused_at', sa.DateTime(timezone=True)),
        sa.Column('trial_end_date', sa.Date()),
        sa.Column('failed_payment_count', sa.Integer(), default=0),
        sa.Column('last_payment_date', sa.Date()),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_subscription_payments_customer', 'subscription_payments', ['customer_id'])
    op.create_index('ix_subscription_payments_venue', 'subscription_payments', ['venue_id'])
    op.create_index('ix_subscription_payments_status', 'subscription_payments', ['status'])
    op.create_index('ix_subscription_payments_next_billing', 'subscription_payments', ['next_billing_date'])

    # Fraud Detection Rules table
    op.create_table(
        'fraud_detection_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True)),
        sa.Column('rule_name', sa.String(255), nullable=False),
        sa.Column('rule_type', postgresql.ENUM('velocity', 'amount_threshold', 'geo_location', 'card_bin', 'device_fingerprint', 'ip_address', 'custom', name='fraudruletype', create_type=False), nullable=False),
        sa.Column('rule_conditions', postgresql.JSONB(), nullable=False),
        sa.Column('risk_score_impact', sa.Integer(), default=10),
        sa.Column('description', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=100),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_fraud_rules_venue', 'fraud_detection_rules', ['venue_id'])
    op.create_index('ix_fraud_rules_type', 'fraud_detection_rules', ['rule_type'])

    # Fraud Alerts table
    op.create_table(
        'fraud_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_transactions.id'), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('fraud_score', sa.Numeric(5, 2), nullable=False),
        sa.Column('risk_level', postgresql.ENUM('low', 'medium', 'high', 'critical', name='risklevel', create_type=False), nullable=False),
        sa.Column('triggered_rules', postgresql.JSONB(), default=[]),
        sa.Column('rule_details', postgresql.JSONB()),
        sa.Column('recommended_action', postgresql.ENUM('allow', 'flag', 'manual_review', 'block', name='recommendedaction', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'escalated', name='fraudalertstatus', create_type=False), default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True)),
        sa.Column('review_notes', sa.Text()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_fraud_alerts_payment', 'fraud_alerts', ['payment_id'])
    op.create_index('ix_fraud_alerts_status', 'fraud_alerts', ['status'])
    op.create_index('ix_fraud_alerts_risk', 'fraud_alerts', ['risk_level'])

    # Payment Disputes table
    op.create_table(
        'payment_disputes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_transactions.id'), nullable=False),
        sa.Column('dispute_type', postgresql.ENUM('chargeback', 'inquiry', 'retrieval', 'fraud', 'duplicate', 'subscription_canceled', 'product_unacceptable', 'product_not_received', 'credit_not_processed', 'general', name='disputetype', create_type=False), nullable=False),
        sa.Column('dispute_reason', sa.String(255)),
        sa.Column('dispute_reason_code', sa.String(50)),
        sa.Column('dispute_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('processor_dispute_id', sa.String(255)),
        sa.Column('dispute_date', sa.Date(), nullable=False),
        sa.Column('response_due_date', sa.Date()),
        sa.Column('status', postgresql.ENUM('open', 'under_review', 'won', 'lost', 'closed', name='disputestatus', create_type=False), default='open'),
        sa.Column('evidence_submitted', postgresql.JSONB()),
        sa.Column('evidence_due_date', sa.Date()),
        sa.Column('resolution_date', sa.Date()),
        sa.Column('resolution_notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_payment_disputes_payment', 'payment_disputes', ['payment_id'])
    op.create_index('ix_payment_disputes_status', 'payment_disputes', ['status'])

    # PCI Compliance Logs table
    op.create_table(
        'pci_compliance_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('compliance_check_type', sa.String(100), nullable=False),
        sa.Column('check_date', sa.Date(), nullable=False),
        sa.Column('status', postgresql.ENUM('compliant', 'non_compliant', 'pending_review', 'remediation_required', name='compliancestatus', create_type=False), nullable=False),
        sa.Column('compliance_level', sa.String(50), nullable=False),
        sa.Column('findings', postgresql.JSONB()),
        sa.Column('remediation_required', sa.Boolean(), default=False),
        sa.Column('remediation_deadline', sa.Date()),
        sa.Column('remediation_completed', sa.Boolean(), default=False),
        sa.Column('next_check_date', sa.Date()),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_pci_compliance_logs_venue', 'pci_compliance_logs', ['venue_id'])
    op.create_index('ix_pci_compliance_logs_status', 'pci_compliance_logs', ['status'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('pci_compliance_logs')
    op.drop_table('payment_disputes')
    op.drop_table('fraud_alerts')
    op.drop_table('fraud_detection_rules')
    op.drop_table('subscription_payments')
    op.drop_table('payment_refunds')
    op.drop_table('payment_transactions')
    op.drop_table('customer_payment_methods')
    op.drop_table('venue_payment_configs')
    op.drop_table('payment_processors')

    # Drop enum types
    op.execute('DROP TYPE compliancestatus')
    op.execute('DROP TYPE disputestatus')
    op.execute('DROP TYPE disputetype')
    op.execute('DROP TYPE recommendedaction')
    op.execute('DROP TYPE fraudalertstatus')
    op.execute('DROP TYPE risklevel')
    op.execute('DROP TYPE fraudruletype')
    op.execute('DROP TYPE subscriptionstatus')
    op.execute('DROP TYPE billinginterval')
    op.execute('DROP TYPE refundstatus')
    op.execute('DROP TYPE refundtype')
    op.execute('DROP TYPE transactionstatus')
    op.execute('DROP TYPE transactiontype')
    op.execute('DROP TYPE cardbrand')
    op.execute('DROP TYPE paymentmethodtype')
    op.execute('DROP TYPE processortype')
