from typing import Annotated

from fastapi import Depends

from app.config.settings import Settings, get_settings
from app.db.supabase import SupabaseRestClient
from app.repositories.incidents import IncidentRepository, SupabaseIncidentRepository
from app.services.incidents import IncidentService


def get_incident_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IncidentRepository:
    project_url, api_key = settings.require_supabase()
    return SupabaseIncidentRepository(SupabaseRestClient(project_url, api_key))


def get_incident_service(
    repository: Annotated[IncidentRepository, Depends(get_incident_repository)],
) -> IncidentService:
    return IncidentService(repository)


IncidentServiceDependency = Annotated[IncidentService, Depends(get_incident_service)]

