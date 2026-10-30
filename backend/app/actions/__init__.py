"""Insight-to-action layer: Tasks, Emails, Workflows, Automations. Currently
implements Task creation from RiskCreated, gated behind pending_validation --
no automatic execution, no external side effects. Knows nothing about
Intelligence's internals, only the Risk record and the event it consumes."""
