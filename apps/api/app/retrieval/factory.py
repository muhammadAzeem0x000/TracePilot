from app.ai.embeddings import GeminiEmbeddingProvider
from app.ai.provider import OpenAICompatibleLLMProvider
from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.repositories.knowledge import SupabaseKnowledgeRepository
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker
from app.retrieval.service import KnowledgeRetrievalService


def build_retrieval_service(settings: Settings) -> KnowledgeRetrievalService:
    supabase_url, supabase_key = settings.require_supabase()
    embedding_url, embedding_key, embedding_model, dimensions = settings.require_embedding()
    reranker = None
    if settings.knowledge_rerank_enabled:
        llm_url, llm_key, llm_model = settings.require_llm()
        reranker = KnowledgeReranker(OpenAICompatibleLLMProvider(llm_url, llm_key, llm_model))
    return KnowledgeRetrievalService(
        SupabaseKnowledgeRepository(SupabaseRestClient(supabase_url, supabase_key)),
        GeminiEmbeddingProvider(embedding_url, embedding_key, embedding_model, dimensions),
        ContextAssembler(settings.knowledge_context_budget_tokens),
        candidate_limit=settings.knowledge_candidate_limit,
        reranker=reranker,
    )
