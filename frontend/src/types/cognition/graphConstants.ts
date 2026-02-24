/**
 * ECTA Quest Graph Constants
 * Based on knowledge_graph/ontology/quest.ttl
 * RDF predicates and classes for Oxigraph graph routing.
 */

// Namespace
export const ECTA_KG_NS = 'http://ecta-quest.org/schema/';
export const ECTA_INST_NS = 'http://ecta-quest.org/instance/';

// ============================================================================
// RDF CLASSES (from quest.ttl)
// ============================================================================

export const ECTA_CLASSES = {
  TeachingTask: `${ECTA_KG_NS}TeachingTask`,
  Concept: `${ECTA_KG_NS}Concept`,
  Quest: `${ECTA_KG_NS}Quest`,
} as const;

// ============================================================================
// OBJECT PROPERTIES (predicates)
// ============================================================================

export const ECTA_PREDICATES = {
  requiresPrerequisite: `${ECTA_KG_NS}requiresPrerequisite`,
  targetsConcept: `${ECTA_KG_NS}targetsConcept`,
  conceptPrerequisite: `${ECTA_KG_NS}conceptPrerequisite`,
} as const;

// ============================================================================
// DATA PROPERTIES
// ============================================================================

export const ECTA_DATA_PROPERTIES = {
  uriId: `${ECTA_KG_NS}uriId`,
} as const;

// ============================================================================
// GraphNode interface - reflects ontology types
// ============================================================================

export type EctaClassType = (typeof ECTA_CLASSES)[keyof typeof ECTA_CLASSES];
export type EctaPredicateType = (typeof ECTA_PREDICATES)[keyof typeof ECTA_PREDICATES];

export interface GraphNode {
  /** Oxigraph instance URI - must match Document DB uri_id */
  uri: string;
  /** rdf:type - one of TeachingTask, Concept, Quest */
  type: EctaClassType;
  /** rdfs:label if present */
  label?: string;
  /** ecta-kg:requiresPrerequisite - URIs of prerequisite tasks */
  requiresPrerequisite?: string[];
  /** ecta-kg:targetsConcept - URIs of targeted concepts */
  targetsConcept?: string[];
  /** ecta-kg:conceptPrerequisite - for Concept nodes */
  conceptPrerequisite?: string[];
}
