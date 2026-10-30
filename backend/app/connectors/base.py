"""Shared, provider-agnostic pieces of the External Connectivity Layer.

    EXTERNAL SYSTEM -> CONNECTOR (Provider) -> NORMALIZED EXTERNAL OBJECT
        -> INGESTION / MAPPING -> DATA CORE -> Business/Intelligence/AI

A Provider (app.connectors.email/calendar/website.base) is the interface a
real integration (Gmail, Outlook, Google Calendar, ...) would implement
later; a Mock Provider implements the exact same interface today with
realistic, static in-memory data. Nothing above the Provider interface
(the registry, the ingestion functions, the router) needs to know or care
which one it's talking to -- see brain/connectors.md.

Connectors contain no business intelligence: they fetch and normalize,
nothing more. Classifying, prioritizing or deciding anything about an
imported Communication is Observation/Interpretation/Decision's job, not
this layer's -- deliberately not built here (see the step 21 brief).
"""

from dataclasses import dataclass

ConnectorType = str  # "email" | "calendar" | "website" -- open for a future connector type


@dataclass(frozen=True)
class SyncResult:
    """What every connector's sync returns, provider-agnostic on purpose so
    `POST /connectors/{type}/sync` has one uniform response shape."""

    connector: ConnectorType
    fetched: int
    created: int
    updated: int
    skipped: int
