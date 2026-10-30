"""Risk detection: listens for SupplierCostIncreased, applies a deterministic
threshold rule, and materializes Risk records in the Data Core, publishing
RiskCreated for whatever downstream layer reacts to it next."""
