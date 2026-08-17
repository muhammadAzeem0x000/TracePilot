from pydantic import BaseModel, ConfigDict, Field


class GetSentryIssueArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(
        min_length=1,
        max_length=100,
        description="Sentry issue identifier or slug",
    )


class GetKubernetesEventsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(
        default="default",
        min_length=1,
        max_length=63,
        description="Kubernetes namespace",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of cluster events to return",
    )
