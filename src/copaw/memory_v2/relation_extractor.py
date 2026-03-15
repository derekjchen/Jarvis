# -*- coding: utf-8 -*-
"""Relation extractor for Memory V2 Milestone 2.0.

Extracts relationships between entities from conversation text.
Supports relation types: belongs_to, participates, likes, uses, knows, creates, depends_on, related_to
"""

import re
from typing import Optional
from .models import Entity, Relation, RelationType, EntityType


class RelationExtractor:
    """Extract relationships between entities.
    
    Uses pattern matching and linguistic analysis to identify
    how entities are related to each other.
    """
    
    # 关系模式字典
    RELATION_PATTERNS = {
        RelationType.BELONGS_TO: [
            r"(.+?)属于(.+)",
            r"(.+?)是(.+?)的",
            r"(.+?)在(.+?)下",
            r"(.+?)\s+belongs\s+to\s+(.+)",
            r"(.+?)\s+is\s+part\s+of\s+(.+)",
        ],
        RelationType.PARTICIPATES: [
            r"(.+?)参与(.+)",
            r"(.+?)加入(.+)",
            r"(.+?)在(.+?)工作",
            r"(.+?)\s+participates?\s+in\s+(.+)",
            r"(.+?)\s+joins?\s+(.+)",
            r"(.+?)\s+works\s+on\s+(.+)",
        ],
        RelationType.LIKES: [
            r"(.+?)喜欢(.+)",
            r"(.+?)偏爱(.+)",
            r"(.+?)偏好(.+)",
            r"(.+?)\s+likes?\s+(.+)",
            r"(.+?)\s+prefers?\s+(.+)",
        ],
        RelationType.USES: [
            r"(.+?)使用(.+)",
            r"(.+?)用(.+)",
            r"(.+?)采用(.+)",
            r"(.+?)\s+uses?\s+(.+)",
            r"(.+?)\s+with\s+(.+)",
            r"(.+?)\s+built\s+with\s+(.+)",
        ],
        RelationType.KNOWS: [
            r"(.+?)认识(.+)",
            r"(.+?)了解(.+)",
            r"(.+?)和(.+?)是",
            r"(.+?)\s+knows?\s+(.+)",
        ],
        RelationType.CREATES: [
            r"(.+?)创建(.+)",
            r"(.+?)开发(.+)",
            r"(.+?)设计(.+)",
            r"(.+?)建立了?(.+)",
            r"(.+?)\s+creates?\s+(.+)",
            r"(.+?)\s+develops?\s+(.+)",
            r"(.+?)\s+founds?\s+(.+)",
        ],
        RelationType.DEPENDS_ON: [
            r"(.+?)依赖(.+)",
            r"(.+?)需要(.+)",
            r"(.+?)基于(.+)",
            r"(.+?)\s+depends?\s+on\s+(.+)",
            r"(.+?)\s+requires?\s+(.+)",
            r"(.+?)\s+based\s+on\s+(.+)",
        ],
    }
    
    # 用于过滤的停用词
    STOPWORDS = {"我", "你", "他", "她", "它", "这", "那", "这个", "那个", "什么", "怎么", "如何",
                 "i", "you", "he", "she", "it", "this", "that", "what", "how", "the", "a", "an"}
    
    def __init__(self):
        pass
    
    def extract_relations(
        self, 
        text: str, 
        entities: list[Entity]
    ) -> list[Relation]:
        """Extract relations from text given known entities.
        
        Args:
            text: Source text
            entities: List of known entities in the text
            
        Returns:
            List of extracted relations
        """
        relations = []
        entity_map = {e.name.lower(): e for e in entities}
        
        for relation_type, patterns in self.RELATION_PATTERNS.items():
            for pattern in patterns:
                try:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        source_text = match.group(1).strip()
                        target_text = match.group(2).strip()
                        
                        # 查找匹配的实体
                        source_entity = self._find_matching_entity(source_text, entity_map)
                        target_entity = self._find_matching_entity(target_text, entity_map)
                        
                        if source_entity and target_entity and source_entity.id != target_entity.id:
                            relation = Relation(
                                source_id=source_entity.id,
                                target_id=target_entity.id,
                                relation_type=relation_type,
                                description=f"{source_entity.name} {relation_type.value} {target_entity.name}",
                                evidence=match.group(0),
                                confidence=0.8,
                            )
                            relations.append(relation)
                except Exception:
                    continue
        
        return self._deduplicate_relations(relations)
    
    def extract_from_entity_context(
        self,
        entity: Entity,
        context: str,
        other_entities: list[Entity]
    ) -> list[Relation]:
        """Extract relations for a specific entity.
        
        Args:
            entity: Target entity
            context: Context text
            other_entities: Other entities that might be related
            
        Returns:
            List of relations involving the target entity
        """
        relations = []
        
        # 检查实体类型与关系类型的关联
        if entity.type == EntityType.PERSON:
            # 人可能：参与项目、使用技术、创建项目、喜欢某物
            relation_hints = [
                RelationType.PARTICIPATES,
                RelationType.USES,
                RelationType.CREATES,
                RelationType.LIKES,
                RelationType.KNOWS,
            ]
        elif entity.type == EntityType.PROJECT:
            # 项目可能：属于组织、使用技术、依赖其他项目
            relation_hints = [
                RelationType.BELONGS_TO,
                RelationType.USES,
                RelationType.DEPENDS_ON,
            ]
        elif entity.type == EntityType.ORGANIZATION:
            # 组织：人属于它
            relation_hints = [RelationType.BELONGS_TO]
        elif entity.type == EntityType.TECHNOLOGY:
            # 技术：被使用、被喜欢
            relation_hints = [RelationType.USES, RelationType.LIKES]
        else:
            relation_hints = list(RelationType)
        
        for other in other_entities:
            if other.id == entity.id:
                continue
            
            # 检查上下文中是否同时提到这两个实体
            if entity.name.lower() in context.lower() and other.name.lower() in context.lower():
                # 尝试推断关系类型
                inferred_type = self._infer_relation_type(
                    entity, other, context, relation_hints
                )
                if inferred_type:
                    relations.append(Relation(
                        source_id=entity.id,
                        target_id=other.id,
                        relation_type=inferred_type,
                        description=f"{entity.name} {inferred_type.value} {other.name}",
                        evidence=context[:100],
                        confidence=0.6,  # 推断的关系置信度较低
                    ))
        
        return relations
    
    def _find_matching_entity(
        self, 
        text: str, 
        entity_map: dict
    ) -> Optional[Entity]:
        """Find entity matching the text."""
        text_lower = text.lower()
        
        # 精确匹配
        if text_lower in entity_map:
            return entity_map[text_lower]
        
        # 部分匹配
        for name, entity in entity_map.items():
            if name in text_lower or text_lower in name:
                return entity
        
        # 过滤停用词
        if text_lower in self.STOPWORDS:
            return None
        
        return None
    
    def _infer_relation_type(
        self,
        source: Entity,
        target: Entity,
        context: str,
        hints: list[RelationType]
    ) -> Optional[RelationType]:
        """Infer relation type based on entity types and context."""
        context_lower = context.lower()
        
        # 基于实体类型组合推断
        type_combination = (source.type, target.type)
        
        # 人 -> 项目: 可能是参与或创建
        if type_combination == (EntityType.PERSON, EntityType.PROJECT):
            if any(kw in context_lower for kw in ["创建", "开发", "建立", "create", "found"]):
                return RelationType.CREATES
            return RelationType.PARTICIPATES
        
        # 人 -> 技术: 使用或喜欢
        elif type_combination == (EntityType.PERSON, EntityType.TECHNOLOGY):
            if any(kw in context_lower for kw in ["喜欢", "偏好", "like", "prefer"]):
                return RelationType.LIKES
            return RelationType.USES
        
        # 人 -> 组织: 属于
        elif type_combination == (EntityType.PERSON, EntityType.ORGANIZATION):
            return RelationType.BELONGS_TO
        
        # 项目 -> 技术: 使用
        elif type_combination == (EntityType.PROJECT, EntityType.TECHNOLOGY):
            return RelationType.USES
        
        # 项目 -> 组织: 属于
        elif type_combination == (EntityType.PROJECT, EntityType.ORGANIZATION):
            return RelationType.BELONGS_TO
        
        # 技术 -> 技术: 依赖
        elif type_combination == (EntityType.TECHNOLOGY, EntityType.TECHNOLOGY):
            if any(kw in context_lower for kw in ["依赖", "需要", "depend", "require"]):
                return RelationType.DEPENDS_ON
            return RelationType.RELATED_TO
        
        # 人 -> 人: 认识
        elif type_combination == (EntityType.PERSON, EntityType.PERSON):
            return RelationType.KNOWS
        
        return RelationType.RELATED_TO
    
    def _deduplicate_relations(self, relations: list[Relation]) -> list[Relation]:
        """Remove duplicate relations."""
        seen = set()
        unique = []
        for r in relations:
            key = (r.source_id, r.target_id, r.relation_type)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique


def extract_relations(
    text: str, 
    entities: list[Entity]
) -> list[Relation]:
    """Convenience function for relation extraction."""
    extractor = RelationExtractor()
    return extractor.extract_relations(text, entities)

