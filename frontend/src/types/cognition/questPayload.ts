/**
 * QuestPayload - Document DB schema for ECTA Quest rich content
 * uri_id must strictly match Oxigraph Instance URI (links graph + document store)
 */

/** Fading prompt levels for structured desktop environment */
export interface FadingPrompts {
  hard: string[];
  good: string[];
  easy: string[];
}

/** Structured desktop: steps with fading prompts per level */
export interface StructuredDesktop {
  steps: string[];
  fading_prompts: FadingPrompts;
}

/** Environment-specific instructions */
export interface QuestEnvironments {
  structured_desktop: StructuredDesktop;
  group_social: string[];
  home_natural: string[];
}

/** Optional media links */
export interface MediaLinks {
  instruction_video_url?: string;
  downloadable_pdfs?: string[];
  physical_tool_urls?: string[];
}

/** Document DB payload - rich content for a quest */
export interface QuestPayload {
  /** Must strictly match Oxigraph Instance URI */
  uri_id: string;
  title: string;
  materials: string[];
  environments: QuestEnvironments;
  media_links?: MediaLinks;
}
