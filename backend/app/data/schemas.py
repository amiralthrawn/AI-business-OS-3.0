"""Response shapes for the Business Domain read APIs (Step 23B).

These wrap, never recompute, what already exists: `app.core.entity_context`
for the relational structure, `HomeService.get_ai_priorities` for the AI
signals, and `app.core.analytics`'s existing trend functions for the one
domain-specific metric each entity type gets (margin for Product, delivery
performance for Supplier, revenue trend for Customer). No new business
logic lives in this file, only field shapes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class IntelligenceSignal(BaseModel):
    """One Business State Snapshot `material_area` concerning this entity --
    identical shape to Home's own "AI Priorities" (see
    app.home.service.HomeService.get_ai_priorities), just pre-filtered to
    one entity instead of the whole company."""

    kind: str
    interpretation_type: str | None
    domain: str
    title: str
    impact: str
    urgency: str
    confidence: str
    explanation: str | None
    recommendation: str | None
    decision_options: list[dict] | None
    detail_kind: str | None
    detail_id: uuid.UUID | None


class LinkedProduct(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None


class LinkedSupplier(BaseModel):
    id: uuid.UUID
    name: str


class LinkedTransaction(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount: float
    currency: str
    occurred_at: datetime


class LinkedRisk(BaseModel):
    id: uuid.UUID
    title: str
    severity: str


class LinkedOpportunity(BaseModel):
    id: uuid.UUID
    title: str


class LinkedTask(BaseModel):
    id: uuid.UUID
    title: str
    status: str


class LinkedDocument(BaseModel):
    id: uuid.UUID
    title: str
    document_type: str | None


class LinkedCommunication(BaseModel):
    id: uuid.UUID
    channel: str
    direction: str
    subject: str | None


class LinkedContact(BaseModel):
    """A real person at this Supplier/Customer (Step 27) -- always sourced
    from `Contact`, never invented. `email`/`phone` are `None` when the
    contact record itself has none, never a placeholder."""

    id: uuid.UUID
    name: str
    role: str | None
    email: str | None
    phone: str | None


class MonthlyPointRead(BaseModel):
    """Mirrors app.core.analytics.MonthlyPoint -- a real, zero-filled
    month total, never an estimate (Step 29 point 11)."""

    month: str
    total_amount: float
    transaction_count: int


class ContactCommunicationRead(BaseModel):
    id: uuid.UUID
    channel: str
    channel_detail: str | None
    direction: str
    subject: str | None
    occurred_at: datetime


class ContactListItem(BaseModel):
    """A real person (Step 28's Contacts communication center) -- always
    sourced from `Contact`, never invented. `related_entity_name`/
    `last_communication` come from the same `related_entity_type`/
    `related_entity_id` pointer the Contact and its Communications share,
    never a new join table."""

    id: uuid.UUID
    name: str
    role: str | None
    email: str | None
    phone: str | None
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    related_entity_name: str | None
    last_communication: ContactCommunicationRead | None


class SupplierListItem(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    product_count: int
    transaction_count: int
    signal_count: int
    top_signal: IntelligenceSignal | None


class SupplierDetail(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    products: list[LinkedProduct]
    transactions: list[LinkedTransaction]
    communications: list[LinkedCommunication]
    contacts: list[LinkedContact]
    documents: list[LinkedDocument]
    tasks: list[LinkedTask]
    open_risks: list[LinkedRisk]
    open_opportunities: list[LinkedOpportunity]
    intelligence: list[IntelligenceSignal]
    # From app.core.analytics.compute_supplier_delivery_performance -- reused, not recomputed.
    delivery_trend: str
    baseline_avg_delay_days: float | None
    recent_avg_delay_days: float | None
    # From app.core.analytics.compute_unanswered_message_age (step 22) -- reused, not recomputed.
    unanswered_message_age_days: float | None


class CustomerListItem(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    transaction_count: int
    recent_revenue: float | None
    signal_count: int
    top_signal: IntelligenceSignal | None


class CustomerDetail(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    transactions: list[LinkedTransaction]
    communications: list[LinkedCommunication]
    contacts: list[LinkedContact]
    documents: list[LinkedDocument]
    tasks: list[LinkedTask]
    open_risks: list[LinkedRisk]
    open_opportunities: list[LinkedOpportunity]
    intelligence: list[IntelligenceSignal]
    # From app.core.analytics.compute_customer_value_trend -- reused, not recomputed.
    revenue_trend: str
    baseline_revenue: float | None
    recent_revenue: float | None
    variation_pct: float | None
    unanswered_message_age_days: float | None


class ProductListItem(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None
    unit_cost: float | None
    supplier: LinkedSupplier | None
    transaction_count: int
    signal_count: int


class ProductDetail(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None
    unit_cost: float | None
    supplier: LinkedSupplier | None
    transactions: list[LinkedTransaction]
    open_risks: list[LinkedRisk]
    open_opportunities: list[LinkedOpportunity]
    intelligence: list[IntelligenceSignal]
    # From app.core.analytics.compute_margin_trend -- reused, not recomputed.
    margin_trend: str
    baseline_margin_pct: float | None
    recent_margin_pct: float | None


class TransactionRead(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount: float
    currency: str
    occurred_at: datetime
    expected_at: datetime | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None
    product_id: uuid.UUID | None
    product_name: str | None
