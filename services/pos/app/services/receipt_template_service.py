"""
Receipt template service for POS Integration.

This module provides the ReceiptTemplateService class for managing customizable
receipt templates for venues. It supports creating, updating, cloning, and
rendering receipt templates for various output formats including thermal
printers, full-page printers, email, and SMS.
"""

from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ErrorCode,
    ServiceError,
    conflict,
    not_found,
)
from app.models.pos import (
    ReceiptTemplate,
    ReceiptTemplateType,
    Transaction,
    TransactionLineItem,
    Payment,
    PaymentStatus,
)
from app.schemas.pos import ReceiptTemplateCreate, ReceiptTemplateUpdate

logger = structlog.get_logger()


class ReceiptTemplateService:
    """
    Service for managing customizable receipt templates for venues.

    This service handles the full lifecycle of receipt templates including
    creation, retrieval, updates, cloning, and rendering. It supports
    multiple template types (thermal, full_page, email, sms) and allows
    venues to customize their receipt appearance and content.

    Templates can be set as defaults for their type, and the service ensures
    only one default exists per venue/template_type combination.

    Attributes:
        db: AsyncSession for database operations.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the ReceiptTemplateService.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self.db = db

    # ─── Helper Methods ──────────────────────────────────────────────────────

    async def _get_template_by_id(self, template_id: UUID) -> ReceiptTemplate:
        """
        Fetch a receipt template by ID or raise NOT_FOUND.

        Args:
            template_id: UUID of the template to retrieve.

        Returns:
            The ReceiptTemplate object if found.

        Raises:
            ServiceError: If the template is not found (404).
        """
        result = await self.db.execute(
            select(ReceiptTemplate).where(ReceiptTemplate.id == template_id)
        )
        template = result.scalars().first()
        if not template:
            raise not_found(
                ErrorCode.RECEIPT_TEMPLATE_NOT_FOUND,
                f"Receipt template {template_id} not found",
            )
        return template

    async def _check_name_exists(
        self,
        venue_id: UUID,
        name: str,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """
        Check if a template with the given name already exists for the venue.

        Args:
            venue_id: UUID of the venue.
            name: Template name to check.
            exclude_id: Optional template ID to exclude from the check (for updates).

        Returns:
            True if a template with the name exists, False otherwise.
        """
        query = select(ReceiptTemplate).where(
            and_(
                ReceiptTemplate.venue_id == venue_id,
                ReceiptTemplate.name == name,
            )
        )
        if exclude_id:
            query = query.where(ReceiptTemplate.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalars().first() is not None

    async def _clear_other_defaults(
        self,
        venue_id: UUID,
        template_type: str,
        exclude_id: Optional[UUID] = None,
    ) -> None:
        """
        Clear the is_default flag for all other templates of the same type.

        Ensures only one default template exists per venue/template_type combination.

        Args:
            venue_id: UUID of the venue.
            template_type: Type of template (thermal, full_page, email, sms).
            exclude_id: Optional template ID to exclude from the update.
        """
        query = (
            update(ReceiptTemplate)
            .where(
                and_(
                    ReceiptTemplate.venue_id == venue_id,
                    ReceiptTemplate.template_type == template_type,
                    ReceiptTemplate.is_default == True,  # noqa: E712
                )
            )
            .values(is_default=False)
        )
        if exclude_id:
            query = query.where(ReceiptTemplate.id != exclude_id)

        await self.db.execute(query)

    async def _get_transaction(self, transaction_id: UUID) -> Transaction:
        """
        Fetch a transaction by ID or raise NOT_FOUND.

        Args:
            transaction_id: UUID of the transaction to retrieve.

        Returns:
            The Transaction object if found.

        Raises:
            ServiceError: If the transaction is not found (404).
        """
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalars().first()
        if not transaction:
            raise not_found(
                ErrorCode.RECEIPT_TEMPLATE_NOT_FOUND,
                f"Transaction {transaction_id} not found",
            )
        return transaction

    async def _get_line_items(self, transaction_id: UUID) -> List[TransactionLineItem]:
        """
        Get all line items for a transaction.

        Args:
            transaction_id: UUID of the transaction.

        Returns:
            List of TransactionLineItem objects.
        """
        result = await self.db.execute(
            select(TransactionLineItem)
            .where(TransactionLineItem.transaction_id == transaction_id)
            .order_by(TransactionLineItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def _get_payments(self, transaction_id: UUID) -> List[Payment]:
        """
        Get all completed payments for a transaction.

        Args:
            transaction_id: UUID of the transaction.

        Returns:
            List of Payment objects.
        """
        result = await self.db.execute(
            select(Payment)
            .where(
                and_(
                    Payment.transaction_id == transaction_id,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
            .order_by(Payment.created_at.asc())
        )
        return list(result.scalars().all())

    # ─── Core CRUD Methods ───────────────────────────────────────────────────

    async def create_template(
        self,
        venue_id: UUID,
        data: ReceiptTemplateCreate,
    ) -> ReceiptTemplate:
        """
        Create a new receipt template for a venue.

        Creates a receipt template with the specified configuration. Template
        names must be unique within a venue. If is_default is True, any existing
        default templates for the same type will be unset.

        Args:
            venue_id: UUID of the venue creating the template.
            data: ReceiptTemplateCreate schema with template configuration.

        Returns:
            The newly created ReceiptTemplate object.

        Raises:
            ServiceError: If a template with the same name already exists (409).
        """
        # Check for duplicate name
        if await self._check_name_exists(venue_id, data.name):
            logger.warning(
                "receipt_template_name_exists",
                venue_id=str(venue_id),
                name=data.name,
            )
            raise conflict(
                ErrorCode.RECEIPT_TEMPLATE_NAME_EXISTS,
                f"Receipt template '{data.name}' already exists for this venue",
            )

        # Get template_type value
        template_type_value = (
            data.template_type.value
            if hasattr(data.template_type, "value")
            else data.template_type
        )

        # If this is being set as default, clear other defaults
        if data.is_default:
            await self._clear_other_defaults(venue_id, template_type_value)

        # Get barcode_type value
        barcode_type_value = None
        if data.barcode_type:
            barcode_type_value = (
                data.barcode_type.value
                if hasattr(data.barcode_type, "value")
                else data.barcode_type
            )

        template = ReceiptTemplate(
            venue_id=venue_id,
            name=data.name,
            template_type=template_type_value,
            is_default=data.is_default,
            is_active=data.is_active,
            header_logo_url=data.header_logo_url,
            header_text=data.header_text,
            show_itemized=data.show_itemized,
            show_tax_breakdown=data.show_tax_breakdown,
            show_payment_details=data.show_payment_details,
            show_cashier_name=data.show_cashier_name,
            show_transaction_id=data.show_transaction_id,
            show_barcode=data.show_barcode,
            barcode_type=barcode_type_value,
            footer_text=data.footer_text,
            footer_promo=data.footer_promo,
            custom_css=data.custom_css,
            template_data=data.template_data,
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        logger.info(
            "receipt_template_created",
            template_id=str(template.id),
            venue_id=str(venue_id),
            name=data.name,
            template_type=template_type_value,
            is_default=data.is_default,
        )

        return template

    async def get_template(self, template_id: UUID) -> ReceiptTemplate:
        """
        Retrieve a receipt template by its ID.

        Args:
            template_id: UUID of the template to retrieve.

        Returns:
            The ReceiptTemplate object if found.

        Raises:
            ServiceError: If the template is not found (404).
        """
        template = await self._get_template_by_id(template_id)
        logger.debug(
            "receipt_template_retrieved",
            template_id=str(template_id),
            venue_id=str(template.venue_id),
        )
        return template

    async def get_default_template(
        self,
        venue_id: UUID,
        template_type: str,
    ) -> ReceiptTemplate:
        """
        Retrieve the default receipt template for a venue and template type.

        Args:
            venue_id: UUID of the venue.
            template_type: Type of template (thermal, full_page, email, sms).

        Returns:
            The default ReceiptTemplate object for the specified type.

        Raises:
            ServiceError: If no default template is found (404).
        """
        result = await self.db.execute(
            select(ReceiptTemplate).where(
                and_(
                    ReceiptTemplate.venue_id == venue_id,
                    ReceiptTemplate.template_type == template_type,
                    ReceiptTemplate.is_default == True,  # noqa: E712
                    ReceiptTemplate.is_active == True,  # noqa: E712
                )
            )
        )
        template = result.scalars().first()

        if not template:
            # Fallback: try to get any active template of this type
            result = await self.db.execute(
                select(ReceiptTemplate)
                .where(
                    and_(
                        ReceiptTemplate.venue_id == venue_id,
                        ReceiptTemplate.template_type == template_type,
                        ReceiptTemplate.is_active == True,  # noqa: E712
                    )
                )
                .order_by(ReceiptTemplate.created_at.desc())
                .limit(1)
            )
            template = result.scalars().first()

        if not template:
            raise not_found(
                ErrorCode.RECEIPT_TEMPLATE_NOT_FOUND,
                f"No default receipt template found for type '{template_type}'",
            )

        logger.debug(
            "receipt_template_default_retrieved",
            template_id=str(template.id),
            venue_id=str(venue_id),
            template_type=template_type,
        )

        return template

    async def list_templates(
        self,
        venue_id: UUID,
        template_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[ReceiptTemplate]:
        """
        List receipt templates for a venue with optional filtering.

        Args:
            venue_id: UUID of the venue.
            template_type: Optional filter by template type.
            active_only: If True, only return active templates (default: True).

        Returns:
            List of ReceiptTemplate objects matching the criteria.
        """
        query = select(ReceiptTemplate).where(ReceiptTemplate.venue_id == venue_id)

        if template_type:
            query = query.where(ReceiptTemplate.template_type == template_type)

        if active_only:
            query = query.where(ReceiptTemplate.is_active == True)  # noqa: E712

        query = query.order_by(
            ReceiptTemplate.template_type.asc(),
            ReceiptTemplate.is_default.desc(),
            ReceiptTemplate.created_at.desc(),
        )

        result = await self.db.execute(query)
        templates = list(result.scalars().all())

        logger.info(
            "receipt_templates_listed",
            venue_id=str(venue_id),
            template_type=template_type,
            active_only=active_only,
            count=len(templates),
        )

        return templates

    async def update_template(
        self,
        template_id: UUID,
        data: ReceiptTemplateUpdate,
    ) -> ReceiptTemplate:
        """
        Update an existing receipt template.

        Updates the template with the provided fields. Only non-None fields
        in the update data will be modified. If name is changed, it must still
        be unique within the venue. If is_default is set to True, other defaults
        for the same type will be cleared.

        Args:
            template_id: UUID of the template to update.
            data: ReceiptTemplateUpdate schema with fields to update.

        Returns:
            The updated ReceiptTemplate object.

        Raises:
            ServiceError: If the template is not found (404).
            ServiceError: If updating name to one that already exists (409).
        """
        template = await self._get_template_by_id(template_id)

        # Check for duplicate name if name is being updated
        if data.name is not None and data.name != template.name:
            if await self._check_name_exists(template.venue_id, data.name, template_id):
                raise conflict(
                    ErrorCode.RECEIPT_TEMPLATE_NAME_EXISTS,
                    f"Receipt template '{data.name}' already exists for this venue",
                )

        # Get update data
        update_data = data.model_dump(exclude_unset=True)

        # Handle is_default changes
        if update_data.get("is_default") is True:
            template_type = update_data.get("template_type", template.template_type)
            if hasattr(template_type, "value"):
                template_type = template_type.value
            await self._clear_other_defaults(
                template.venue_id, template_type, template_id
            )

        # Update fields
        for field, value in update_data.items():
            if field == "template_type" and value is not None:
                setattr(template, field, value.value if hasattr(value, "value") else value)
            elif field == "barcode_type" and value is not None:
                setattr(template, field, value.value if hasattr(value, "value") else value)
            else:
                setattr(template, field, value)

        await self.db.commit()
        await self.db.refresh(template)

        logger.info(
            "receipt_template_updated",
            template_id=str(template_id),
            venue_id=str(template.venue_id),
            updated_fields=list(update_data.keys()),
        )

        return template

    async def set_as_default(self, template_id: UUID) -> ReceiptTemplate:
        """
        Set a receipt template as the default for its type.

        Clears the is_default flag from any other templates of the same
        type for the venue, then sets this template as the default.

        Args:
            template_id: UUID of the template to set as default.

        Returns:
            The updated ReceiptTemplate object.

        Raises:
            ServiceError: If the template is not found (404).
        """
        template = await self._get_template_by_id(template_id)

        # Clear other defaults for this type
        await self._clear_other_defaults(
            template.venue_id, template.template_type, template_id
        )

        # Set this template as default
        template.is_default = True
        await self.db.commit()
        await self.db.refresh(template)

        logger.info(
            "receipt_template_set_as_default",
            template_id=str(template_id),
            venue_id=str(template.venue_id),
            template_type=template.template_type,
        )

        return template

    async def deactivate_template(self, template_id: UUID) -> ReceiptTemplate:
        """
        Deactivate a receipt template.

        Sets the template's is_active flag to False, preventing it from
        being used for generating receipts. Also clears the is_default
        flag if it was set.

        Args:
            template_id: UUID of the template to deactivate.

        Returns:
            The deactivated ReceiptTemplate object.

        Raises:
            ServiceError: If the template is not found (404).
        """
        template = await self._get_template_by_id(template_id)
        template.is_active = False
        template.is_default = False
        await self.db.commit()
        await self.db.refresh(template)

        logger.info(
            "receipt_template_deactivated",
            template_id=str(template_id),
            venue_id=str(template.venue_id),
        )

        return template

    async def clone_template(
        self,
        template_id: UUID,
        new_name: str,
    ) -> ReceiptTemplate:
        """
        Clone an existing receipt template with a new name.

        Creates a copy of the template with all the same settings but
        with the specified new name. The clone is not set as default
        and is active by default.

        Args:
            template_id: UUID of the template to clone.
            new_name: Name for the cloned template.

        Returns:
            The newly created ReceiptTemplate clone.

        Raises:
            ServiceError: If the template is not found (404).
            ServiceError: If the new name already exists (409).
        """
        original = await self._get_template_by_id(template_id)

        # Check for duplicate name
        if await self._check_name_exists(original.venue_id, new_name):
            raise conflict(
                ErrorCode.RECEIPT_TEMPLATE_NAME_EXISTS,
                f"Receipt template '{new_name}' already exists for this venue",
            )

        # Create the clone
        clone = ReceiptTemplate(
            venue_id=original.venue_id,
            name=new_name,
            template_type=original.template_type,
            is_default=False,  # Clone is never default
            is_active=True,
            header_logo_url=original.header_logo_url,
            header_text=original.header_text,
            show_itemized=original.show_itemized,
            show_tax_breakdown=original.show_tax_breakdown,
            show_payment_details=original.show_payment_details,
            show_cashier_name=original.show_cashier_name,
            show_transaction_id=original.show_transaction_id,
            show_barcode=original.show_barcode,
            barcode_type=original.barcode_type,
            footer_text=original.footer_text,
            footer_promo=original.footer_promo,
            custom_css=original.custom_css,
            template_data=original.template_data.copy() if original.template_data else None,
        )
        self.db.add(clone)
        await self.db.commit()
        await self.db.refresh(clone)

        logger.info(
            "receipt_template_cloned",
            original_id=str(template_id),
            clone_id=str(clone.id),
            venue_id=str(original.venue_id),
            new_name=new_name,
        )

        return clone

    # ─── Rendering Methods ───────────────────────────────────────────────────

    async def render_receipt(
        self,
        template_id: UUID,
        transaction: Transaction,
    ) -> str:
        """
        Render a receipt using the specified template and transaction data.

        Generates the receipt output in the appropriate format based on
        the template type:
        - thermal: Plain text formatted for 40-character thermal printers
        - full_page: HTML formatted for standard printers
        - email: Full HTML with styling for email clients
        - sms: Short text message format

        Args:
            template_id: UUID of the template to use for rendering.
            transaction: The Transaction object to render.

        Returns:
            The rendered receipt as a string (text or HTML depending on type).

        Raises:
            ServiceError: If the template is not found (404).
        """
        template = await self._get_template_by_id(template_id)

        # Get additional transaction data
        line_items = await self._get_line_items(transaction.id)
        payments = await self._get_payments(transaction.id)

        # Build the render context
        context = self._build_render_context(template, transaction, line_items, payments)

        # Render based on template type
        if template.template_type == ReceiptTemplateType.THERMAL.value:
            rendered = self._render_thermal(template, context)
        elif template.template_type == ReceiptTemplateType.SMS.value:
            rendered = self._render_sms(template, context)
        else:
            # full_page and email both use HTML
            rendered = self._render_html(template, context)

        logger.info(
            "receipt_rendered",
            template_id=str(template_id),
            transaction_id=str(transaction.id),
            template_type=template.template_type,
            output_length=len(rendered),
        )

        return rendered

    async def preview_template(
        self,
        template_id: UUID,
        sample_data: Dict[str, Any],
    ) -> str:
        """
        Preview a template with sample data.

        Renders the template using provided sample data instead of an
        actual transaction. Useful for template editing and preview.

        Args:
            template_id: UUID of the template to preview.
            sample_data: Dictionary containing sample transaction data.

        Returns:
            The rendered preview as a string (text or HTML depending on type).

        Raises:
            ServiceError: If the template is not found (404).
        """
        template = await self._get_template_by_id(template_id)

        # Build context from sample data
        context = self._build_preview_context(template, sample_data)

        # Render based on template type
        if template.template_type == ReceiptTemplateType.THERMAL.value:
            rendered = self._render_thermal(template, context)
        elif template.template_type == ReceiptTemplateType.SMS.value:
            rendered = self._render_sms(template, context)
        else:
            rendered = self._render_html(template, context)

        logger.info(
            "receipt_template_preview",
            template_id=str(template_id),
            template_type=template.template_type,
        )

        return rendered

    def _build_render_context(
        self,
        template: ReceiptTemplate,
        transaction: Transaction,
        line_items: List[TransactionLineItem],
        payments: List[Payment],
    ) -> Dict[str, Any]:
        """
        Build the rendering context from transaction data.

        Args:
            template: The receipt template.
            transaction: The transaction being rendered.
            line_items: List of line items.
            payments: List of completed payments.

        Returns:
            Dictionary with all context data for rendering.
        """
        return {
            "template": template,
            "transaction": {
                "id": str(transaction.id),
                "venue_id": str(transaction.venue_id),
                "transaction_type": transaction.transaction_type,
                "status": transaction.status,
                "subtotal": transaction.subtotal,
                "tax_amount": transaction.tax_amount,
                "tip_amount": transaction.tip_amount,
                "discount_amount": transaction.discount_amount,
                "total_amount": transaction.total_amount,
                "currency": transaction.currency,
                "created_at": transaction.created_at,
                "cashier_id": str(transaction.cashier_id) if transaction.cashier_id else None,
            },
            "line_items": [
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.subtotal,
                    "discount_amount": item.discount_amount,
                    "tax_amount": item.tax_amount,
                    "total": item.total,
                }
                for item in line_items
            ],
            "payments": [
                {
                    "payment_method": payment.payment_method,
                    "amount": payment.amount,
                    "card_last_four": payment.card_last_four,
                    "card_brand": payment.card_brand,
                }
                for payment in payments
            ],
            "timestamp": datetime.utcnow(),
        }

    def _build_preview_context(
        self,
        template: ReceiptTemplate,
        sample_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the rendering context from sample data for preview.

        Args:
            template: The receipt template.
            sample_data: Sample data dictionary.

        Returns:
            Dictionary with all context data for rendering.
        """
        # Use provided sample data or generate defaults
        default_items = [
            {
                "product_name": "Sample Item 1",
                "quantity": 2,
                "unit_price": Decimal("10.00"),
                "subtotal": Decimal("20.00"),
                "discount_amount": Decimal("0.00"),
                "tax_amount": Decimal("1.60"),
                "total": Decimal("21.60"),
            },
            {
                "product_name": "Sample Item 2",
                "quantity": 1,
                "unit_price": Decimal("15.50"),
                "subtotal": Decimal("15.50"),
                "discount_amount": Decimal("0.00"),
                "tax_amount": Decimal("1.24"),
                "total": Decimal("16.74"),
            },
        ]

        default_payments = [
            {
                "payment_method": "credit_card",
                "amount": Decimal("38.34"),
                "card_last_four": "4242",
                "card_brand": "Visa",
            },
        ]

        return {
            "template": template,
            "transaction": sample_data.get("transaction", {
                "id": "00000000-0000-0000-0000-000000000000",
                "venue_id": str(template.venue_id),
                "transaction_type": "retail",
                "status": "completed",
                "subtotal": Decimal("35.50"),
                "tax_amount": Decimal("2.84"),
                "tip_amount": Decimal("0.00"),
                "discount_amount": Decimal("0.00"),
                "total_amount": Decimal("38.34"),
                "currency": "USD",
                "created_at": datetime.utcnow(),
                "cashier_id": "Sample Cashier",
            }),
            "line_items": sample_data.get("line_items", default_items),
            "payments": sample_data.get("payments", default_payments),
            "timestamp": datetime.utcnow(),
        }

    def _render_thermal(
        self,
        template: ReceiptTemplate,
        context: Dict[str, Any],
    ) -> str:
        """
        Render a thermal printer receipt (40 characters wide).

        Generates plain text formatted for standard thermal receipt printers.
        Uses fixed-width formatting and ASCII line separators.

        Args:
            template: The receipt template configuration.
            context: The rendering context with transaction data.

        Returns:
            Plain text receipt formatted for thermal printers.
        """
        width = 40
        lines = []

        def center(text: str) -> str:
            return text.center(width)

        def divider(char: str = "-") -> str:
            return char * width

        # Header
        if template.header_text:
            for line in template.header_text.split("\n"):
                lines.append(center(line.strip()))
        lines.append(divider("="))

        # Transaction ID
        if template.show_transaction_id:
            txn = context["transaction"]
            lines.append(f"Trans: {txn['id'][:18]}")

        # Timestamp
        timestamp = context["timestamp"]
        lines.append(f"Date: {timestamp.strftime('%m/%d/%Y %I:%M %p')}")

        # Cashier
        if template.show_cashier_name and context["transaction"].get("cashier_id"):
            lines.append(f"Cashier: {context['transaction']['cashier_id'][:20]}")

        lines.append(divider())

        # Line items
        if template.show_itemized and context["line_items"]:
            for item in context["line_items"]:
                name = item["product_name"][:25]
                qty = item["quantity"]
                total = item["total"]
                lines.append(f"{name}")
                lines.append(f"  {qty} x ${item['unit_price']:.2f}".ljust(30) + f"${total:.2f}".rjust(10))

            lines.append(divider())

        # Totals
        txn = context["transaction"]
        lines.append("SUBTOTAL".ljust(30) + f"${txn['subtotal']:.2f}".rjust(10))

        if template.show_tax_breakdown and txn["tax_amount"]:
            lines.append("TAX".ljust(30) + f"${txn['tax_amount']:.2f}".rjust(10))

        if txn["discount_amount"]:
            lines.append("DISCOUNT".ljust(30) + f"-${txn['discount_amount']:.2f}".rjust(10))

        if txn["tip_amount"]:
            lines.append("TIP".ljust(30) + f"${txn['tip_amount']:.2f}".rjust(10))

        lines.append(divider("="))
        lines.append("TOTAL".ljust(30) + f"${txn['total_amount']:.2f}".rjust(10))
        lines.append(divider("="))

        # Payment details
        if template.show_payment_details and context["payments"]:
            lines.append("")
            lines.append("PAYMENT:")
            for payment in context["payments"]:
                method = payment["payment_method"].upper()
                if payment.get("card_brand") and payment.get("card_last_four"):
                    method = f"{payment['card_brand']} ****{payment['card_last_four']}"
                lines.append(f"  {method}".ljust(30) + f"${payment['amount']:.2f}".rjust(10))

        # Barcode placeholder (text representation)
        if template.show_barcode:
            lines.append("")
            lines.append(center("[BARCODE]"))
            lines.append(center(txn['id'][:20]))

        # Footer
        lines.append("")
        if template.footer_text:
            for line in template.footer_text.split("\n"):
                lines.append(center(line.strip()))

        if template.footer_promo:
            lines.append("")
            lines.append(divider("-"))
            for line in template.footer_promo.split("\n"):
                lines.append(center(line.strip()))

        lines.append("")
        lines.append("")

        return "\n".join(lines)

    def _render_sms(
        self,
        template: ReceiptTemplate,
        context: Dict[str, Any],
    ) -> str:
        """
        Render an SMS receipt (short text format).

        Generates a compact text message with essential receipt information.
        Limited to key details due to SMS character limits.

        Args:
            template: The receipt template configuration.
            context: The rendering context with transaction data.

        Returns:
            Short text receipt suitable for SMS.
        """
        txn = context["transaction"]
        lines = []

        # Header (venue name if in header_text)
        if template.header_text:
            venue_name = template.header_text.split("\n")[0].strip()
            lines.append(venue_name)

        # Total and date
        lines.append(f"Total: ${txn['total_amount']:.2f}")
        lines.append(f"Date: {context['timestamp'].strftime('%m/%d/%y')}")

        # Transaction reference
        if template.show_transaction_id:
            lines.append(f"Ref: {txn['id'][:8]}")

        # Footer (short version)
        if template.footer_text:
            footer_line = template.footer_text.split("\n")[0].strip()
            if len(footer_line) > 50:
                footer_line = footer_line[:47] + "..."
            lines.append(footer_line)

        return " | ".join(lines)

    def _render_html(
        self,
        template: ReceiptTemplate,
        context: Dict[str, Any],
    ) -> str:
        """
        Render an HTML receipt (for email or full-page printing).

        Generates a full HTML document with inline CSS styling.
        Suitable for email clients or printing to standard printers.

        Args:
            template: The receipt template configuration.
            context: The rendering context with transaction data.

        Returns:
            Full HTML document as a string.
        """
        txn = context["transaction"]

        # Build custom CSS
        custom_css = template.custom_css or ""

        # Build HTML
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "<style>",
            """
            body {
                font-family: Arial, sans-serif;
                max-width: 400px;
                margin: 0 auto;
                padding: 20px;
                color: #333;
            }
            .header {
                text-align: center;
                margin-bottom: 20px;
            }
            .header img {
                max-width: 150px;
                height: auto;
            }
            .header-text {
                white-space: pre-line;
                margin-top: 10px;
            }
            .divider {
                border-top: 1px dashed #ccc;
                margin: 15px 0;
            }
            .transaction-info {
                font-size: 12px;
                color: #666;
            }
            .line-items {
                width: 100%;
                border-collapse: collapse;
            }
            .line-items th {
                text-align: left;
                border-bottom: 1px solid #333;
                padding: 5px 0;
            }
            .line-items td {
                padding: 5px 0;
                vertical-align: top;
            }
            .line-items .amount {
                text-align: right;
            }
            .totals {
                margin-top: 15px;
            }
            .totals-row {
                display: flex;
                justify-content: space-between;
                padding: 3px 0;
            }
            .totals-row.grand-total {
                font-weight: bold;
                font-size: 18px;
                border-top: 2px solid #333;
                border-bottom: 2px solid #333;
                padding: 10px 0;
                margin: 10px 0;
            }
            .payments {
                margin-top: 15px;
            }
            .payment-row {
                display: flex;
                justify-content: space-between;
                padding: 3px 0;
            }
            .barcode {
                text-align: center;
                margin: 20px 0;
            }
            .footer {
                text-align: center;
                margin-top: 20px;
                font-size: 12px;
                color: #666;
            }
            .promo {
                background: #f5f5f5;
                padding: 10px;
                margin-top: 15px;
                text-align: center;
                border-radius: 5px;
            }
            """,
            custom_css,
            "</style>",
            "</head>",
            "<body>",
        ]

        # Header
        html_parts.append("<div class='header'>")
        if template.header_logo_url:
            html_parts.append(f"<img src='{escape(template.header_logo_url)}' alt='Logo'>")
        if template.header_text:
            html_parts.append(f"<div class='header-text'>{escape(template.header_text)}</div>")
        html_parts.append("</div>")

        html_parts.append("<div class='divider'></div>")

        # Transaction info
        html_parts.append("<div class='transaction-info'>")
        if template.show_transaction_id:
            html_parts.append(f"<div>Transaction: {escape(txn['id'])}</div>")
        html_parts.append(f"<div>Date: {context['timestamp'].strftime('%B %d, %Y %I:%M %p')}</div>")
        if template.show_cashier_name and txn.get("cashier_id"):
            html_parts.append(f"<div>Cashier: {escape(str(txn['cashier_id']))}</div>")
        html_parts.append("</div>")

        # Line items
        if template.show_itemized and context["line_items"]:
            html_parts.append("<div class='divider'></div>")
            html_parts.append("<table class='line-items'>")
            html_parts.append("<tr><th>Item</th><th>Qty</th><th class='amount'>Amount</th></tr>")
            for item in context["line_items"]:
                html_parts.append("<tr>")
                html_parts.append(f"<td>{escape(item['product_name'])}</td>")
                html_parts.append(f"<td>{item['quantity']}</td>")
                html_parts.append(f"<td class='amount'>${item['total']:.2f}</td>")
                html_parts.append("</tr>")
            html_parts.append("</table>")

        # Totals
        html_parts.append("<div class='totals'>")
        html_parts.append(f"<div class='totals-row'><span>Subtotal</span><span>${txn['subtotal']:.2f}</span></div>")

        if template.show_tax_breakdown and txn["tax_amount"]:
            html_parts.append(f"<div class='totals-row'><span>Tax</span><span>${txn['tax_amount']:.2f}</span></div>")

        if txn["discount_amount"]:
            html_parts.append(f"<div class='totals-row'><span>Discount</span><span>-${txn['discount_amount']:.2f}</span></div>")

        if txn["tip_amount"]:
            html_parts.append(f"<div class='totals-row'><span>Tip</span><span>${txn['tip_amount']:.2f}</span></div>")

        html_parts.append(f"<div class='totals-row grand-total'><span>TOTAL</span><span>${txn['total_amount']:.2f}</span></div>")
        html_parts.append("</div>")

        # Payment details
        if template.show_payment_details and context["payments"]:
            html_parts.append("<div class='payments'>")
            html_parts.append("<strong>Payment</strong>")
            for payment in context["payments"]:
                method = payment["payment_method"].replace("_", " ").title()
                if payment.get("card_brand") and payment.get("card_last_four"):
                    method = f"{payment['card_brand']} ****{payment['card_last_four']}"
                html_parts.append(f"<div class='payment-row'><span>{escape(method)}</span><span>${payment['amount']:.2f}</span></div>")
            html_parts.append("</div>")

        # Barcode
        if template.show_barcode:
            html_parts.append("<div class='barcode'>")
            barcode_type = template.barcode_type or "qr"
            html_parts.append(f"<div>[{barcode_type.upper()} CODE]</div>")
            html_parts.append(f"<div style='font-size: 10px;'>{escape(txn['id'])}</div>")
            html_parts.append("</div>")

        # Footer
        html_parts.append("<div class='footer'>")
        if template.footer_text:
            html_parts.append(f"<div>{escape(template.footer_text)}</div>")
        html_parts.append("</div>")

        # Promo
        if template.footer_promo:
            html_parts.append(f"<div class='promo'>{escape(template.footer_promo)}</div>")

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)
