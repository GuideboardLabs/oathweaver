from __future__ import annotations

from pathlib import Path
from typing import Any

from shared_tools.embedding_memory import EmbeddingMemory
from shared_tools.external_requests import ExternalRequestStore, ExternalToolsSettings
from shared_tools.feedback_learning import FeedbackLearningEngine
from shared_tools.model_routing import lane_model_config
from shared_tools.ollama_client import OllamaClient
from shared_tools.project_context_memory import ProjectContextMemory
from shared_tools.project_pipeline import ProjectPipelineStore
from shared_tools.self_reflection import SelfReflectionEngine
from shared_tools.topic_memory import TopicMemory
from shared_tools.general_knowledge_pool import GeneralKnowledgePool
from shared_tools.library_service import LibraryService
from shared_tools.watchtower import WatchtowerEngine
from shared_tools.web_research import WebResearchEngine
from shared_tools.workspace_tools import WorkspaceTools
from infra.tools import ToolRegistry


class OrchestratorInfraRuntime:
    """Lazily provisions heavier orchestrator dependencies.

    The orchestrator historically created many expensive helpers during __init__.
    This runtime lets us keep the public API stable while making startup lighter
    and separating infrastructure concerns from the top-level coordinator.
    """

    def __init__(self, repo_root: Path, ollama: OllamaClient) -> None:
        self.repo_root = repo_root
        self.ollama = ollama
        self._cache: dict[str, Any] = {}

    def reset(self) -> None:
        self._cache.clear()

    def _cfg(self) -> dict[str, Any]:
        return lane_model_config(self.repo_root, "orchestrator_reasoning")

    @property
    def web_engine(self) -> WebResearchEngine:
        if "web_engine" not in self._cache:
            self._cache["web_engine"] = WebResearchEngine(self.repo_root)
        return self._cache["web_engine"]

    @property
    def external_tools_settings(self) -> ExternalToolsSettings:
        if "external_tools_settings" not in self._cache:
            self._cache["external_tools_settings"] = ExternalToolsSettings(self.repo_root)
        return self._cache["external_tools_settings"]

    @property
    def external_request_store(self) -> ExternalRequestStore:
        if "external_request_store" not in self._cache:
            self._cache["external_request_store"] = ExternalRequestStore(self.repo_root)
        return self._cache["external_request_store"]

    @property
    def project_memory(self) -> ProjectContextMemory:
        if "project_memory" not in self._cache:
            self._cache["project_memory"] = ProjectContextMemory(self.repo_root)
        return self._cache["project_memory"]

    @property
    def topic_memory(self) -> TopicMemory:
        if "topic_memory" not in self._cache:
            self._cache["topic_memory"] = TopicMemory(self.repo_root)
        return self._cache["topic_memory"]

    @property
    def pipeline_store(self) -> ProjectPipelineStore:
        if "pipeline_store" not in self._cache:
            self._cache["pipeline_store"] = ProjectPipelineStore(self.repo_root)
        return self._cache["pipeline_store"]

    @property
    def improvement_engine(self) -> FeedbackLearningEngine:
        # Consolidated improvement surface now rides on the learning engine.
        return self.learning_engine

    @property
    def learning_engine(self) -> FeedbackLearningEngine:
        if "learning_engine" not in self._cache:
            self._cache["learning_engine"] = FeedbackLearningEngine(
                self.repo_root,
                client=self.ollama,
                model_cfg=self._cfg(),
            )
        return self._cache["learning_engine"]

    @property
    def reflection_engine(self) -> SelfReflectionEngine:
        if "reflection_engine" not in self._cache:
            self._cache["reflection_engine"] = SelfReflectionEngine(
                self.repo_root,
                client=self.ollama,
                learning_engine=self.learning_engine,
                model_cfg=self._cfg(),
            )
        return self._cache["reflection_engine"]

    @property
    def workspace_tools(self) -> WorkspaceTools:
        if "workspace_tools" not in self._cache:
            self._cache["workspace_tools"] = WorkspaceTools(
                self.repo_root,
                client=self.ollama,
                model_cfg=self._cfg(),
            )
        return self._cache["workspace_tools"]


    def build_tool_registry(self, *, bus=None) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register("ollama", self.ollama, description="Shared Ollama client")
        registry.register("web_engine", self.web_engine, description="Web research engine")
        registry.register(
            "external_tools_settings",
            self.external_tools_settings,
            description="External tools mode/settings",
        )
        registry.register(
            "external_request_store",
            self.external_request_store,
            description="External request persistence store",
        )
        registry.register("project_memory", self.project_memory, description="Project context memory")
        registry.register("topic_memory", self.topic_memory, description="Topic memory")
        registry.register("pipeline_store", self.pipeline_store, description="Project pipeline store")
        registry.register("learning_engine", self.learning_engine, description="Feedback learning engine")
        registry.register("reflection_engine", self.reflection_engine, description="Self reflection engine")
        registry.register("workspace_tools", self.workspace_tools, description="Workspace helper toolkit")
        registry.register("embedding_memory", self.embedding_memory, description="Embedding-backed memory")
        registry.register("library_service", self.library_service, description="Library retrieval service")
        if bus is not None:
            registry.register("bus", bus, description="Activity bus")
        return registry

    @property
    def embedding_memory(self) -> EmbeddingMemory:
        if "embedding_memory" not in self._cache:
            self._cache["embedding_memory"] = EmbeddingMemory(self.repo_root)
        return self._cache["embedding_memory"]

    @property
    def general_pool(self) -> GeneralKnowledgePool:
        if "general_pool" not in self._cache:
            self._cache["general_pool"] = GeneralKnowledgePool(self.repo_root)
        return self._cache["general_pool"]

    @property
    def library_service(self) -> LibraryService:
        if "library_service" not in self._cache:
            self._cache["library_service"] = LibraryService(self.repo_root)
        return self._cache["library_service"]

    @property
    def watchtower(self) -> WatchtowerEngine:
        if "watchtower" not in self._cache:
            self._cache["watchtower"] = WatchtowerEngine(self.repo_root)
        return self._cache["watchtower"]
