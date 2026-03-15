# -*- coding: utf-8 -*-
"""Semantic memory store for Memory V2.

Milestone 2.0 Enhancement:
- Scene storage and retrieval
- Relation storage with graph-like queries
- Cross-scene association

Storage Structure:
- entities.json: All entities
- relations.json: All relations between entities
- scenes.json: Scene records
- semantic_memories.json: Structured memories
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from .models import Entity, EntityType, Relation, RelationType, Scene, SceneType, SemanticMemory, MemoryType

logger = logging.getLogger(__name__)


class SemanticStore:
    """Persistent storage for semantic memory.
    
    Provides CRUD operations for entities, relations, scenes, and memories.
    """
    
    def __init__(self, storage_dir: str | Path = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".copaw" / "semantic_memory"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self.entities_file = self.storage_dir / "entities.json"
        self.relations_file = self.storage_dir / "relations.json"
        self.scenes_file = self.storage_dir / "scenes.json"
        self.memories_file = self.storage_dir / "semantic_memories.json"
        
        # 内存缓存
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}
        self._scenes: dict[str, Scene] = {}
        self._memories: dict[str, SemanticMemory] = {}
        
        # 加载数据
        self._load_all()
    
    def _load_all(self):
        """Load all data from files."""
        self._load_entities()
        self._load_relations()
        self._load_scenes()
        self._load_memories()
    
    def _load_entities(self):
        """Load entities from file."""
        if self.entities_file.exists():
            try:
                with open(self.entities_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entities = {e["id"]: Entity.from_dict(e) for e in data}
            except Exception as e:
                logger.warning(f"Failed to load entities: {e}")
                self._entities = {}
    
    def _load_relations(self):
        """Load relations from file."""
        if self.relations_file.exists():
            try:
                with open(self.relations_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._relations = {r["id"]: Relation.from_dict(r) for r in data}
            except Exception as e:
                logger.warning(f"Failed to load relations: {e}")
                self._relations = {}
    
    def _load_scenes(self):
        """Load scenes from file."""
        if self.scenes_file.exists():
            try:
                with open(self.scenes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._scenes = {s["id"]: Scene.from_dict(s) for s in data}
            except Exception as e:
                logger.warning(f"Failed to load scenes: {e}")
                self._scenes = {}
    
    def _load_memories(self):
        """Load memories from file."""
        if self.memories_file.exists():
            try:
                with open(self.memories_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._memories = {m["id"]: SemanticMemory.from_dict(m) for m in data}
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")
                self._memories = {}
    
    def _save_entities(self):
        """Save entities to file."""
        with open(self.entities_file, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self._entities.values()], f, ensure_ascii=False, indent=2)
    
    def _save_relations(self):
        """Save relations to file."""
        with open(self.relations_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self._relations.values()], f, ensure_ascii=False, indent=2)
    
    def _save_scenes(self):
        """Save scenes to file."""
        with open(self.scenes_file, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self._scenes.values()], f, ensure_ascii=False, indent=2)
    
    def _save_memories(self):
        """Save memories to file."""
        with open(self.memories_file, "w", encoding="utf-8") as f:
            json.dump([m.to_dict() for m in self._memories.values()], f, ensure_ascii=False, indent=2)
    
    # ==================== Entity Operations ====================
    
    def add_entity(self, entity: Entity) -> Entity:
        """Add or update an entity."""
        if entity.id in self._entities:
            # 更新现有实体
            existing = self._entities[entity.id]
            existing.update_mention()
            if entity.description and entity.description != existing.description:
                existing.description = entity.description
            if entity.attributes:
                existing.attributes.update(entity.attributes)
        else:
            entity.update_mention()
            self._entities[entity.id] = entity
        self._save_entities()
        return self._entities[entity.id]
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Get entity by name."""
        name_lower = name.lower()
        for entity in self._entities.values():
            if entity.name.lower() == name_lower:
                return entity
        return None
    
    def get_all_entities(self) -> list[Entity]:
        """Get all entities."""
        return list(self._entities.values())
    
    def search_entities(self, query: str, limit: int = 10) -> list[Entity]:
        """Search entities by name or description."""
        query_lower = query.lower()
        results = []
        for entity in self._entities.values():
            score = 0
            if query_lower in entity.name.lower():
                score += 10
            if query_lower in entity.description.lower():
                score += 5
            if score > 0:
                results.append((score, entity))
        results.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in results[:limit]]
    
    # ==================== Relation Operations ====================
    
    def add_relation(self, relation: Relation) -> Relation:
        """Add a relation."""
        # 检查是否已存在相同的关系
        for existing in self._relations.values():
            if (existing.source_id == relation.source_id and 
                existing.target_id == relation.target_id and
                existing.relation_type == relation.relation_type):
                # 更新置信度
                existing.confidence = max(existing.confidence, relation.confidence)
                existing.updated_at = datetime.now()
                self._save_relations()
                return existing
        
        self._relations[relation.id] = relation
        self._save_relations()
        return relation
    
    def get_relations_for_entity(self, entity_id: str) -> list[Relation]:
        """Get all relations involving an entity."""
        return [
            r for r in self._relations.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]
    
    def get_relations_between(self, entity_id1: str, entity_id2: str) -> list[Relation]:
        """Get relations between two entities."""
        return [
            r for r in self._relations.values()
            if (r.source_id == entity_id1 and r.target_id == entity_id2) or
               (r.source_id == entity_id2 and r.target_id == entity_id1)
        ]
    
    def get_related_entities(self, entity_id: str, relation_type: RelationType = None) -> list[tuple[Entity, Relation]]:
        """Get entities related to an entity."""
        results = []
        for relation in self._relations.values():
            if relation.source_id == entity_id:
                if relation_type is None or relation.relation_type == relation_type:
                    target = self._entities.get(relation.target_id)
                    if target:
                        results.append((target, relation))
            elif relation.target_id == entity_id:
                if relation_type is None or relation.relation_type == relation_type:
                    source = self._entities.get(relation.source_id)
                    if source:
                        results.append((source, relation))
        return results
    
    # ==================== Scene Operations ====================
    
    def add_scene(self, scene: Scene) -> Scene:
        """Add a scene."""
        self._scenes[scene.id] = scene
        self._save_scenes()
        return scene
    
    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """Get scene by ID."""
        return self._scenes.get(scene_id)
    
    def get_active_scene(self) -> Optional[Scene]:
        """Get the most recent active scene."""
        active = [s for s in self._scenes.values() if s.end_time is None]
        if active:
            return max(active, key=lambda s: s.start_time)
        return None
    
    def end_scene(self, scene_id: str) -> Optional[Scene]:
        """End a scene."""
        scene = self._scenes.get(scene_id)
        if scene:
            scene.end_time = datetime.now()
            self._save_scenes()
        return scene
    
    def get_scenes_by_type(self, scene_type: SceneType) -> list[Scene]:
        """Get scenes by type."""
        return [s for s in self._scenes.values() if s.scene_type == scene_type]
    
    def get_scenes_by_entity(self, entity_id: str) -> list[Scene]:
        """Get scenes mentioning an entity."""
        return [s for s in self._scenes.values() if entity_id in s.entities]
    
    # ==================== Memory Operations ====================
    
    def add_memory(self, memory: SemanticMemory) -> SemanticMemory:
        """Add a semantic memory."""
        self._memories[memory.id] = memory
        self._save_memories()
        return memory
    
    def get_memory(self, memory_id: str) -> Optional[SemanticMemory]:
        """Get memory by ID."""
        return self._memories.get(memory_id)
    
    def get_memories_by_scene(self, scene_id: str) -> list[SemanticMemory]:
        """Get memories by scene."""
        return [m for m in self._memories.values() if m.scene_id == scene_id]
    
    # ==================== Query Operations ====================
    
    def get_entity_context(self, entity_name: str, max_chars: int = 2000) -> str:
        """Get context for an entity including relations."""
        entity = self.get_entity_by_name(entity_name)
        if not entity:
            return ""
        
        lines = [f"- {entity.name} ({entity.type.value}): {entity.description}"]
        
        # 添加关系
        relations = self.get_relations_for_entity(entity.id)
        for r in relations[:5]:
            if r.source_id == entity.id:
                target = self.get_entity(r.target_id)
                if target:
                    lines.append(f"  {r.relation_type.value} {target.name}")
            else:
                source = self.get_entity(r.source_id)
                if source:
                    lines.append(f"  {source.name} {r.relation_type.value} (this)")
        
        # 添加时序信息
        if entity.mention_count > 1:
            lines.append(f"  提及 {entity.mention_count} 次")
        
        context = "\n".join(lines)
        if len(context) > max_chars:
            context = context[:max_chars] + "... (truncated)"
        
        return context
    
    def find_cross_scene_relations(self) -> list[dict]:
        """Find entities that appear in multiple scenes."""
        entity_scenes = {}
        for scene in self._scenes.values():
            for entity_id in scene.entities:
                if entity_id not in entity_scenes:
                    entity_scenes[entity_id] = []
                entity_scenes[entity_id].append(scene)
        
        # 返回出现在多个场景的实体
        results = []
        for entity_id, scenes in entity_scenes.items():
            if len(scenes) > 1:
                entity = self._entities.get(entity_id)
                if entity:
                    results.append({
                        "entity": entity,
                        "scenes": scenes,
                        "count": len(scenes),
                    })
        
        return sorted(results, key=lambda x: x["count"], reverse=True)
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        return {
            "entities": len(self._entities),
            "relations": len(self._relations),
            "scenes": len(self._scenes),
            "memories": len(self._memories),
            "entity_types": {t.value: sum(1 for e in self._entities.values() if e.type == t) for t in EntityType},
            "relation_types": {t.value: sum(1 for r in self._relations.values() if r.relation_type == t) for t in RelationType},
            "scene_types": {t.value: sum(1 for s in self._scenes.values() if s.scene_type == t) for t in SceneType},
        }

