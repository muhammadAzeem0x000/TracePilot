import json
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError


class ModelPricing(BaseModel):
    input_usd_per_million_tokens: Decimal = Field(ge=0)
    output_usd_per_million_tokens: Decimal = Field(ge=0)


@dataclass(frozen=True)
class PricingRegistry:
    models: dict[str, ModelPricing]
    source_date: str | None

    @classmethod
    def from_json(cls, raw: str | None, source_date: str | None) -> "PricingRegistry":
        if not raw:
            return cls({}, source_date)
        try:
            parsed: object = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("pricing must be an object")
            models = {
                str(name): ModelPricing.model_validate(value) for name, value in parsed.items()
            }
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError("AI_PRICING_JSON is invalid") from exc
        return cls(models, source_date)

    def estimate(
        self,
        model: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> float | None:
        if model is None or input_tokens is None or output_tokens is None:
            return None
        pricing = self.models.get(model)
        if pricing is None:
            return None
        million = Decimal(1_000_000)
        cost = (
            Decimal(input_tokens) * pricing.input_usd_per_million_tokens / million
            + Decimal(output_tokens) * pricing.output_usd_per_million_tokens / million
        )
        return float(cost)
