import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.ask_ai.schemas import AskAIRequest, AskAIResponse
from app.ai.capabilities import capability_registry
from app.ai.llm import LLMClient, get_llm_client
from app.ai.orchestrator import AIOrchestrator, OrchestratorError
from app.core.events.bus import EventBus
from app.database import get_db
from app.dependencies import get_event_bus

router = APIRouter(prefix="/ai", tags=["ai"])

# The assistant only explains the company's own data. A request to watch a
# site, a competitor or a fair, or to look something up on the web, belongs to
# the Veilleur: say so instead of answering with an unrelated customer summary.
_WEB_REQUEST = re.compile(r"https?://|www\.|\.com\b|surveill|veille|cherch\w* sur (le )?(web|internet)|recherche web|concurrent|salon|exposant", re.IGNORECASE)


@router.post("/ask", response_model=AskAIResponse)
def ask_ai(
    payload: AskAIRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    event_bus: EventBus = Depends(get_event_bus),
) -> AskAIResponse:
    if payload.object_type is None and _WEB_REQUEST.search(payload.question):
        return AskAIResponse(
            answer=(
                "Cette demande ressemble à une recherche ou à une veille sur le web (un site, un concurrent, un salon). "
                "Je ne réponds qu'aux questions sur les données de votre entreprise. "
                "Adressez-la au Veilleur dans la rubrique « Agents IA » : il cherche sur le web, cite ses sources et peut suivre le sujet dans la durée."
            ),
            agent="assistant", capabilities_used=[], context={}, requires_human_validation=False, action_result=None,
        )
    orchestrator = AIOrchestrator(db, capability_registry, llm, event_bus)
    try:
        result = orchestrator.ask(payload.question, object_type=payload.object_type, object_id=payload.object_id)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AskAIResponse(
        answer=result.answer,
        agent=result.agent,
        capabilities_used=result.capabilities_used,
        context=result.context,
        requires_human_validation=result.requires_human_validation,
        action_result=result.action_result,
    )
