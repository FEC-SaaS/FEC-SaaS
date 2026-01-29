"""
Receipt Template API Routes.

This module provides API endpoints for managing customizable receipt templates
for POS transactions. Receipt templates define the structure, styling, and
content of receipts generated for various output formats including thermal
printers, full-page printers, email, and SMS.

Endpoints:
    POST   /pos/receipt-templates              - Create a new receipt template
    GET    /pos/receipt-templates              - List receipt templates for a venue
    GET    /pos/receipt-templates/{id}         - Get a specific template by ID
    GET    /pos/receipt-templates/default/{type} - Get the default template for a type
    PATCH  /pos/receipt-templates/{id}         - Update a receipt template
    POST   /pos/receipt-templates/{id}/set-default - Set template as default
    POST   /pos/receipt-templates/{id}/deactivate  - Deactivate a template
    POST   /pos/receipt-templates/{id}/clone       - Clone a template
    POST   /pos/receipt-templates/{id}/preview     - Preview with sample data
    POST   /pos/receipt-templates/{id}/render/{txn_id} - Render for a transaction
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.pos import Transaction
from app.schemas.pos import (
    ReceiptTemplateCreate,
    ReceiptTemplateResponse,
    ReceiptTemplateUpdate,
)
from app.services.receipt_template_service import ReceiptTemplateService

router = APIRouter(prefix="/pos/receipt-templates")


def _get_service(db: AsyncSession = Depends(get_db)) -> ReceiptTemplateService:
    """
    Dependency injection factory for ReceiptTemplateService.

    Creates a new ReceiptTemplateService instance with the provided
    database session for handling receipt template operations.

    Args:
        db: SQLAlchemy async database session from dependency injection.

    Returns:
        ReceiptTemplateService: Configured service instance for template operations.
    """
    return ReceiptTemplateService(db)


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates — create a new receipt template
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=ReceiptTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a receipt template",
    responses={
        201: {"description": "Receipt template created successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        409: {"description": "Conflict - template name already exists for venue"},
        422: {"description": "Validation error in request body"},
    },
)
async def create_template(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to create the template for. The template "
        "will be associated with this venue and only accessible by users with "
        "permissions for this venue.",
    ),
    data: ReceiptTemplateCreate = Body(
        ...,
        description="Receipt template configuration including name, type, "
        "header/footer content, display options, and styling.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Create a new receipt template for a venue.

    Creates a customizable receipt template that defines how receipts are
    formatted and rendered for POS transactions. Each venue can have multiple
    templates of different types (thermal, full_page, email, sms) with one
    default per type.

    Template configuration includes:
    - **Header**: Logo URL, venue name, address, contact info
    - **Content**: Line item display, tax breakdown, payment details visibility
    - **Footer**: Thank you message, return policy, promotional content
    - **Barcode**: QR code or barcode for receipt identification
    - **Styling**: Custom CSS for HTML-based outputs (email, full_page)

    If `is_default` is set to True, any existing default template of the
    same type for this venue will be automatically unset.

    Args:
        venue_id: UUID of the venue creating the template.
        data: ReceiptTemplateCreate schema containing template configuration.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The newly created template with all fields
            including the generated ID and timestamps.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 409: If a template with the same name already exists.
        HTTPException 422: If request body validation fails.
    """
    template = await service.create_template(venue_id, data)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# GET /pos/receipt-templates/{template_id} — get template by ID
# ---------------------------------------------------------------------------
@router.get(
    "/{template_id}",
    response_model=ReceiptTemplateResponse,
    summary="Get a receipt template by ID",
    responses={
        200: {"description": "Receipt template retrieved successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Receipt template not found"},
    },
)
async def get_template(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to retrieve.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Retrieve a receipt template by its unique identifier.

    Fetches the complete template configuration including all header, content,
    footer, and styling settings. Use this endpoint to view or edit a specific
    template's configuration.

    Args:
        template_id: UUID of the template to retrieve.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: Complete template configuration with all
            fields including venue_id, name, type, display options, and styling.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists with the given ID.
    """
    template = await service.get_template(template_id)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# GET /pos/receipt-templates — list templates for a venue
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[ReceiptTemplateResponse],
    summary="List receipt templates for a venue",
    responses={
        200: {"description": "List of receipt templates retrieved successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
    },
)
async def list_templates(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to list templates for. Returns all "
        "templates associated with this venue.",
    ),
    template_type: Optional[str] = Query(
        None,
        description="Filter by template type. Valid values are: 'thermal', "
        "'full_page', 'email', 'sms'. If not provided, returns all types.",
    ),
    active_only: bool = Query(
        True,
        description="If True (default), only return active templates. Set to "
        "False to include deactivated templates in the results.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> List[ReceiptTemplateResponse]:
    """
    List all receipt templates for a venue with optional filtering.

    Returns a list of receipt templates associated with the specified venue.
    Results can be filtered by template type and active status. Templates
    are sorted by type (alphabetically), then by default status (defaults
    first), then by creation date (newest first).

    Template types:
    - **thermal**: Formatted for 40-character thermal receipt printers
    - **full_page**: HTML formatted for standard A4/Letter printers
    - **email**: Full HTML with styling optimized for email clients
    - **sms**: Short text format for SMS delivery

    Args:
        venue_id: UUID of the venue to list templates for.
        template_type: Optional filter for specific template type.
        active_only: Whether to exclude deactivated templates (default: True).
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        List[ReceiptTemplateResponse]: List of templates matching the criteria.
            Returns an empty list if no templates match the filters.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
    """
    templates = await service.list_templates(venue_id, template_type, active_only)
    return [ReceiptTemplateResponse.model_validate(t) for t in templates]


# ---------------------------------------------------------------------------
# GET /pos/receipt-templates/default/{template_type} — get default template
# ---------------------------------------------------------------------------
@router.get(
    "/default/{template_type}",
    response_model=ReceiptTemplateResponse,
    summary="Get the default template for a template type",
    responses={
        200: {"description": "Default template retrieved successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "No default template found for the specified type"},
    },
)
async def get_default_template(
    venue_id: UUID = Query(
        ...,
        description="UUID of the venue to get the default template for.",
    ),
    template_type: str = Path(
        ...,
        description="Template type to get the default for. Valid values: "
        "'thermal', 'full_page', 'email', 'sms'.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Get the default receipt template for a specific type.

    Retrieves the template marked as default for the specified type and venue.
    Each venue can have one default template per type (thermal, full_page,
    email, sms). The default template is automatically used when generating
    receipts if no specific template is specified.

    If no template is explicitly marked as default, the service will fall back
    to the most recently created active template of that type.

    Args:
        venue_id: UUID of the venue to get the default template for.
        template_type: Type of template ('thermal', 'full_page', 'email', 'sms').
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The default template for the specified type.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists for the specified type.
    """
    template = await service.get_default_template(venue_id, template_type)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# PATCH /pos/receipt-templates/{template_id} — update template
# ---------------------------------------------------------------------------
@router.patch(
    "/{template_id}",
    response_model=ReceiptTemplateResponse,
    summary="Update a receipt template",
    responses={
        200: {"description": "Receipt template updated successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Receipt template not found"},
        409: {"description": "Conflict - template name already exists for venue"},
        422: {"description": "Validation error in request body"},
    },
)
async def update_template(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to update.",
    ),
    data: ReceiptTemplateUpdate = Body(
        ...,
        description="Fields to update. Only provided fields will be modified; "
        "omitted fields retain their current values.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Update an existing receipt template.

    Performs a partial update of the template configuration. Only fields
    included in the request body will be modified; all other fields retain
    their current values. This allows updating individual settings without
    affecting the rest of the template.

    Updatable fields include:
    - **name**: Template name (must be unique within venue)
    - **template_type**: Output format type
    - **is_default**: Default status for the type
    - **is_active**: Active/inactive status
    - **Header settings**: logo_url, header_text
    - **Content settings**: show_itemized, show_tax_breakdown, etc.
    - **Footer settings**: footer_text, footer_promo
    - **Barcode settings**: show_barcode, barcode_type
    - **Styling**: custom_css, template_data

    If setting `is_default` to True, other default templates of the same
    type will be automatically unset to maintain one default per type.

    Args:
        template_id: UUID of the template to update.
        data: ReceiptTemplateUpdate schema with fields to modify.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The updated template with all current values.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists with the given ID.
        HTTPException 409: If updating name to one that already exists.
        HTTPException 422: If request body validation fails.
    """
    template = await service.update_template(template_id, data)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates/{template_id}/set-default — set as default
# ---------------------------------------------------------------------------
@router.post(
    "/{template_id}/set-default",
    response_model=ReceiptTemplateResponse,
    summary="Set a template as the default for its type",
    responses={
        200: {"description": "Template set as default successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Receipt template not found"},
    },
)
async def set_as_default(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to set as default.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Set a receipt template as the default for its type.

    Marks the specified template as the default for its template type within
    its venue. Any other template previously marked as default for the same
    type will be automatically unset.

    The default template is used when generating receipts without explicitly
    specifying a template ID. Each venue maintains one default per template
    type (thermal, full_page, email, sms).

    Args:
        template_id: UUID of the template to set as default.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The updated template with is_default=True.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists with the given ID.
    """
    template = await service.set_as_default(template_id)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates/{template_id}/deactivate — deactivate template
# ---------------------------------------------------------------------------
@router.post(
    "/{template_id}/deactivate",
    response_model=ReceiptTemplateResponse,
    summary="Deactivate a receipt template",
    responses={
        200: {"description": "Template deactivated successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Receipt template not found"},
    },
)
async def deactivate_template(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to deactivate.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Deactivate a receipt template.

    Sets the template's active status to False, preventing it from being
    used for generating receipts. If the template was marked as default,
    the default flag is also cleared.

    Deactivated templates:
    - Are excluded from list queries when active_only=True (default)
    - Cannot be used for rendering receipts
    - Can be reactivated by updating is_active to True
    - Retain all configuration for potential reactivation

    Use this endpoint to retire templates without permanently deleting them,
    preserving the configuration for potential future use or audit purposes.

    Args:
        template_id: UUID of the template to deactivate.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The deactivated template with is_active=False
            and is_default=False.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists with the given ID.
    """
    template = await service.deactivate_template(template_id)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates/{template_id}/clone — clone template
# ---------------------------------------------------------------------------
@router.post(
    "/{template_id}/clone",
    response_model=ReceiptTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone an existing template with a new name",
    responses={
        201: {"description": "Template cloned successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Source template not found"},
        409: {"description": "Conflict - new name already exists for venue"},
    },
)
async def clone_template(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to clone.",
    ),
    new_name: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Name for the cloned template. Must be unique within "
        "the venue and between 1-100 characters.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> ReceiptTemplateResponse:
    """
    Clone an existing receipt template with a new name.

    Creates a complete copy of the specified template with all settings
    preserved but with a new unique name. The cloned template:
    - Copies all header, content, footer, and styling settings
    - Is created as active (is_active=True)
    - Is NOT set as default (is_default=False)
    - Belongs to the same venue as the source template

    Use this endpoint to create variations of existing templates without
    starting from scratch, such as seasonal variations or templates for
    different receipt formats based on a proven design.

    Args:
        template_id: UUID of the template to clone.
        new_name: Unique name for the cloned template.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        ReceiptTemplateResponse: The newly created clone with a new ID
            and the specified name.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If the source template does not exist.
        HTTPException 409: If the new name already exists for the venue.
    """
    template = await service.clone_template(template_id, new_name)
    return ReceiptTemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates/{template_id}/preview — preview with sample data
# ---------------------------------------------------------------------------
@router.post(
    "/{template_id}/preview",
    summary="Preview a template with sample data",
    responses={
        200: {"description": "Template preview generated successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Receipt template not found"},
    },
)
async def preview_template(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to preview.",
    ),
    sample_data: Dict[str, Any] = Body(
        default={},
        description="Sample transaction data for the preview. If empty or "
        "partially provided, default sample data will be used for missing "
        "fields. Supports 'transaction', 'line_items', and 'payments' keys.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> Dict[str, str]:
    """
    Preview a receipt template with sample transaction data.

    Generates a preview of the receipt without requiring an actual transaction.
    This is useful for testing template designs and visualizing changes before
    saving them. Sample data can be provided to customize the preview content.

    The output format depends on the template type:
    - **thermal**: Plain text formatted for 40-character width
    - **full_page**: Full HTML document with inline CSS
    - **email**: Full HTML document optimized for email clients
    - **sms**: Short text message format

    Sample data structure (all fields optional):
    ```json
    {
        "transaction": {
            "id": "uuid-string",
            "transaction_type": "retail",
            "status": "completed",
            "subtotal": 35.50,
            "tax_amount": 2.84,
            "tip_amount": 5.00,
            "discount_amount": 0.00,
            "total_amount": 43.34,
            "currency": "USD",
            "cashier_id": "John Smith"
        },
        "line_items": [
            {"product_name": "Item 1", "quantity": 2, "unit_price": 10.00, "total": 21.60}
        ],
        "payments": [
            {"payment_method": "credit_card", "amount": 43.34, "card_last_four": "4242", "card_brand": "Visa"}
        ]
    }
    ```

    Args:
        template_id: UUID of the template to preview.
        sample_data: Optional dictionary with sample transaction data.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        Dict containing 'rendered' key with the preview output as a string.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If no template exists with the given ID.
    """
    rendered = await service.preview_template(template_id, sample_data)
    return {"rendered": rendered}


# ---------------------------------------------------------------------------
# POST /pos/receipt-templates/{template_id}/render/{transaction_id}
# ---------------------------------------------------------------------------
@router.post(
    "/{template_id}/render/{transaction_id}",
    summary="Render a receipt for a specific transaction",
    responses={
        200: {"description": "Receipt rendered successfully"},
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Template or transaction not found"},
    },
)
async def render_receipt(
    template_id: UUID = Path(
        ...,
        description="UUID of the receipt template to use for rendering.",
    ),
    transaction_id: UUID = Path(
        ...,
        description="UUID of the transaction to generate the receipt for.",
    ),
    current_user: dict = Depends(get_current_user),
    service: ReceiptTemplateService = Depends(_get_service),
) -> Dict[str, str]:
    """
    Render a receipt for a specific transaction using a template.

    Generates a complete receipt by combining the template configuration
    with actual transaction data including line items and payment details.
    The output format is determined by the template type.

    Output formats by template type:
    - **thermal**: Plain text receipt formatted for 40-character thermal
      printers with ASCII line separators and fixed-width columns
    - **full_page**: Complete HTML document with inline CSS, suitable for
      printing on standard A4/Letter paper
    - **email**: Full HTML document with email-client-compatible styling
      for sending via email
    - **sms**: Compact text format with essential receipt information,
      suitable for SMS delivery

    The rendered receipt includes:
    - Header content (logo, venue info) from template
    - Transaction metadata (ID, date, cashier if enabled)
    - Line items with quantities and prices (if show_itemized=True)
    - Tax breakdown (if show_tax_breakdown=True)
    - Payment details (if show_payment_details=True)
    - Barcode/QR code (if show_barcode=True)
    - Footer content (thank you message, promotions) from template

    Args:
        template_id: UUID of the template to use.
        transaction_id: UUID of the transaction to render.
        current_user: Authenticated user information from JWT token.
        service: Injected ReceiptTemplateService instance.

    Returns:
        Dict containing 'rendered' key with the receipt content as a string.
        The content type (text or HTML) depends on the template type.

    Raises:
        HTTPException 401: If authentication token is invalid or missing.
        HTTPException 404: If the template or transaction is not found.
    """
    # Get the transaction using the service's internal method
    transaction = await service._get_transaction(transaction_id)

    # Render the receipt
    rendered = await service.render_receipt(template_id, transaction)
    return {"rendered": rendered}
