"""Company identity (name, industry) -- read/update only. Single-company MVP:
every route here operates on `db.query(Company).first()`, the same assumption
every other router already makes. No multi-tenancy, no company creation
endpoint (Company is still only ever created by data/seed.py)."""
