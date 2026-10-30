from datetime import datetime, timezone

from data.seed import seed
from app.core.entities import (
    Company,
    Customer,
    Document,
    Product,
    Supplier,
    Task,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.event_bus import build_event_bus


def test_create_core_entities_and_relations(db_session):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()

    supplier = Supplier(company_id=company.id, name="Test Supplier")
    db_session.add(supplier)
    db_session.flush()

    product = Product(company_id=company.id, supplier_id=supplier.id, name="Widget", sku="W-1", unit_cost=10.0)
    db_session.add(product)
    db_session.flush()

    transaction = Transaction(
        company_id=company.id,
        supplier_id=supplier.id,
        product_id=product.id,
        type=TransactionType.PURCHASE_ORDER,
        status=TransactionStatus.CONFIRMED,
        amount=100.0,
        currency="EUR",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(transaction)
    db_session.commit()

    assert db_session.query(Company).count() == 1
    assert supplier.company_id == company.id
    assert product.supplier_id == supplier.id
    assert transaction.supplier_id == supplier.id
    assert transaction.product_id == product.id
    assert supplier in company.suppliers
    assert product in supplier.products


# --- Step 20 audit: Supplier/Product/Customer <-> Transaction relationships --
# (Supplier/Customer already had the ORM relationship; Product did not --
# see brain/data_core.md decision on why it was added.)


def test_supplier_to_transaction_relationship(db_session):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Test Supplier")
    db_session.add(supplier)
    db_session.flush()
    transaction = Transaction(
        company_id=company.id, supplier_id=supplier.id,
        type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
        amount=50.0, currency="EUR", occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(transaction)
    db_session.commit()

    assert transaction in supplier.transactions
    assert transaction.supplier is supplier


def test_product_to_transaction_relationship(db_session):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Test Supplier")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Widget", sku="W-1")
    db_session.add(product)
    db_session.flush()
    transaction = Transaction(
        company_id=company.id, supplier_id=supplier.id, product_id=product.id,
        type=TransactionType.PURCHASE_ORDER, status=TransactionStatus.CONFIRMED,
        amount=50.0, currency="EUR", occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(transaction)
    db_session.commit()

    assert transaction in product.transactions
    assert transaction.product is product


def test_customer_to_transaction_relationship(db_session):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()
    customer = Customer(company_id=company.id, name="Test Customer")
    db_session.add(customer)
    db_session.flush()
    transaction = Transaction(
        company_id=company.id, customer_id=customer.id,
        type=TransactionType.SALES_ORDER, status=TransactionStatus.CONFIRMED,
        amount=50.0, currency="EUR", occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(transaction)
    db_session.commit()

    assert transaction in customer.transactions
    assert transaction.customer is customer


# --- Step 20 audit: no orphaned foreign keys on the real seeded dataset -----


def test_seed_data_has_no_orphaned_foreign_keys(db_session, session_factory):
    seed(db_session, build_event_bus(session_factory))

    supplier_ids = {s.id for s in db_session.query(Supplier).all()}
    customer_ids = {c.id for c in db_session.query(Customer).all()}
    product_ids = {p.id for p in db_session.query(Product).all()}

    for transaction in db_session.query(Transaction).all():
        if transaction.supplier_id is not None:
            assert transaction.supplier_id in supplier_ids
        if transaction.customer_id is not None:
            assert transaction.customer_id in customer_ids
        if transaction.product_id is not None:
            assert transaction.product_id in product_ids
        # Every transaction attaches to a supplier (purchase side) or a
        # customer (sales side) -- never neither, per the seed's own design.
        assert transaction.supplier_id is not None or transaction.customer_id is not None

    for product in db_session.query(Product).all():
        if product.supplier_id is not None:
            assert product.supplier_id in supplier_ids

    for document in db_session.query(Document).all():
        if document.related_entity_id is not None:
            assert document.related_entity_id in supplier_ids | customer_ids | product_ids

    for task in db_session.query(Task).all():
        if task.related_entity_id is not None:
            assert task.related_entity_id in supplier_ids | customer_ids | product_ids
