import React, { useState, useCallback } from 'react';
import theme from '../styles/theme';

/**
 * Temporary direct imports of enriched ABox JSON (language, cognition, self-care).
 * Source of truth in repo: `scripts/data_extraction/`
 *   - 21_heep_hong_language_enriched_abox.json
 *   - 22_cognition_enriched_abox.json
 *   - 23_self_care_enriched_abox.json
 * Create React App only resolves JSON imports from `src/`; `frontend/src/data/` mirrors those files.
 */
import languageData from '../data/21_heep_hong_language_enriched_abox.json';
import cognitionData from '../data/22_cognition_enriched_abox.json';
import selfCareData from '../data/23_self_care_enriched_abox.json';

/** Canonical Level-1 labels (self-care JSON may still say `module`: "认知"). */
const MODULE_LEVEL_LABELS = ['语言', '认知', '自理'];

const fullCurriculum = [languageData, cognitionData, selfCareData];

/**
 * Legacy goal descriptions: age fragments after / or ／ (language & cognition data).
 * Used only when rendering the old `goals` array (no `sub_goals`).
 */
const GOAL_DESCRIPTION_AGE_SUFFIX =
  /\s*[/／]\s*((?:>\s*)?\d+(?:\s*[-–]\s*\d+)?\s*(?:个月|岁))/g;

function stripAgeFromDescriptionText(raw) {
  if (!raw || typeof raw !== 'string') {
    return { cleanText: '', ageBadges: [] };
  }
  const matches = [...raw.matchAll(GOAL_DESCRIPTION_AGE_SUFFIX)];
  const found = matches.map((m) => m[1].replace(/\s+/g, ' ').trim());
  const ageBadges = [...new Set(found)];
  const cleanText = raw
    .replace(GOAL_DESCRIPTION_AGE_SUFFIX, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return { cleanText, ageBadges };
}

const tagStyle = {
  fontSize: '12px',
  padding: `${theme.spacing.xs} ${theme.spacing.sm}`,
  backgroundColor: theme.statusBackgrounds?.info ?? '#e0f2fe',
  color: theme.categories?.cognition?.dark ?? '#0c4a6e',
  borderRadius: theme.borderRadius.sm,
};

const badgeStyle = {
  fontSize: '11px',
  fontWeight: 600,
  padding: '2px 8px',
  borderRadius: theme.borderRadius.sm,
  backgroundColor: '#dbeafe',
  color: '#1e40af',
  border: '1px solid #93c5fd',
  whiteSpace: 'nowrap',
};

function AccordionHeader({ id, title, expanded, onToggle, level, emoji }) {
  const panelId = `${id}-panel`;
  const indent = level * 12;
  const palette = [
    { bg: '#eff6ff', border: '#bfdbfe', title: '#1e3a8a' },
    { bg: '#f0fdf4', border: '#bbf7d0', title: '#14532d' },
    { bg: '#fffbeb', border: '#fde68a', title: '#78350f' },
    { bg: '#faf5ff', border: '#e9d5ff', title: '#581c87' },
  ];
  const p = palette[Math.min(level, palette.length - 1)];

  return (
    <button
      type="button"
      id={id}
      aria-expanded={expanded}
      aria-controls={panelId}
      onClick={onToggle}
      style={{
        width: '100%',
        textAlign: 'left',
        cursor: 'pointer',
        padding: '10px 12px',
        marginLeft: indent,
        marginBottom: theme.spacing.xs,
        borderRadius: theme.borderRadius.sm,
        border: `1px solid ${p.border}`,
        backgroundColor: p.bg,
        color: p.title,
        fontWeight: 600,
        fontSize: level === 0 ? '16px' : '14px',
        display: 'flex',
        alignItems: 'center',
        gap: theme.spacing.sm,
      }}
    >
      <span style={{ fontSize: '12px', color: '#64748b', width: '14px' }}>
        {expanded ? '▼' : '▶'}
      </span>
      {emoji ? <span aria-hidden>{emoji}</span> : null}
      <span style={{ flex: 1 }}>{title}</span>
    </button>
  );
}

/** Normalizes `materials` to string tags for display. */
function normalizeMaterialTags(raw) {
  if (raw == null) return [];
  if (Array.isArray(raw)) {
    return raw.map((m) => (typeof m === 'string' ? m.trim() : String(m))).filter(Boolean);
  }
  if (typeof raw === 'string') {
    return raw
      .split(/[,，、;；]/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

/** Normalizes `shared_activity_suggestions` to ordered-list items (array or newline-separated string). */
function normalizeOrderedLines(raw) {
  if (raw == null) return [];
  if (Array.isArray(raw)) {
    return raw.map((s) => (typeof s === 'string' ? s.trim() : String(s))).filter(Boolean);
  }
  if (typeof raw === 'string') {
    return raw
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

const phasalParentCardStyle = {
  backgroundColor: theme.ui.background,
  borderRadius: theme.borderRadius.lg,
  border: `1px solid ${theme.ui.border}`,
  padding: theme.spacing.lg,
  boxShadow: theme.shadows?.sm ?? '0 1px 2px rgba(0,0,0,0.06)',
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing.md,
  minHeight: '80px',
};

/** Single goal card for legacy `goals[]` (unchanged behavior vs. previous GoalCard). */
function LegacyGoalCard({ goal }) {
  const { cleanText, ageBadges } = stripAgeFromDescriptionText(goal.description || '');
  const materials = normalizeMaterialTags(goal.materials);
  const precautions = goal.precautions;
  const activitySuggestions = goal.activity_suggestions;

  return (
    <div
      style={{
        position: 'relative',
        ...phasalParentCardStyle,
        paddingTop: ageBadges.length ? theme.spacing.xl : theme.spacing.lg,
      }}
    >
      {ageBadges.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: theme.spacing.sm,
            right: theme.spacing.sm,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            justifyContent: 'flex-end',
            maxWidth: '55%',
          }}
        >
          {ageBadges.map((a) => (
            <span key={a} style={badgeStyle}>
              {a}
            </span>
          ))}
        </div>
      )}
      <div
        style={{
          color: theme.ui.text.primary,
          fontSize: '14px',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {cleanText || '（无描述）'}
      </div>
      {materials.length > 0 && (
        <div>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: theme.ui.text.secondary,
              marginBottom: theme.spacing.xs,
            }}
          >
            材料
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: theme.spacing.xs }}>
            {materials.map((m, ti) => (
              <span key={`${m}-${ti}`} style={tagStyle}>
                {m}
              </span>
            ))}
          </div>
        </div>
      )}
      {precautions ? (
        <div>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: theme.ui.text.secondary,
              marginBottom: theme.spacing.xs,
            }}
          >
            注意事项
          </div>
          <p
            style={{
              margin: 0,
              fontSize: '13px',
              color: theme.ui.text.secondary,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}
          >
            {precautions}
          </p>
        </div>
      ) : null}
      {activitySuggestions ? (
        <div>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: theme.ui.text.secondary,
              marginBottom: theme.spacing.xs,
            }}
          >
            活动建议
          </div>
          <p
            style={{
              margin: 0,
              fontSize: '13px',
              color: theme.ui.text.secondary,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}
          >
            {activitySuggestions}
          </p>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Phasal objective: Target Set (`sub_goals` + `shared_*`) or legacy `goals[]` grid.
 */
function PhasalObjectiveContainer({ phasalObjective }) {
  const phase = phasalObjective || {};
  const subGoals = Array.isArray(phase.sub_goals) ? phase.sub_goals : [];
  const legacyGoals = Array.isArray(phase.goals) ? phase.goals : [];

  if (subGoals.length > 0) {
    const sharedMaterials = normalizeMaterialTags(phase.shared_materials);
    const sharedPrecautions = phase.shared_precautions;
    const sharedActivityLines = normalizeOrderedLines(phase.shared_activity_suggestions);

    return (
      <div style={phasalParentCardStyle}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.sm }}>
          {subGoals.map((sg, sgi) => {
            const label = sg.label != null ? String(sg.label) : '';
            const desc = sg.description != null ? String(sg.description) : '';
            const ageTag = sg.age_group != null ? String(sg.age_group).trim() : '';
            return (
              <div
                key={sgi}
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'flex-start',
                  gap: theme.spacing.sm,
                  padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                  backgroundColor: theme.ui.backgrounds?.surface ?? '#f1f5f9',
                  borderRadius: theme.borderRadius.sm,
                  border: `1px solid ${theme.ui.border}`,
                }}
              >
                {label ? (
                  <span
                    style={{
                      fontWeight: 700,
                      fontSize: '13px',
                      color: theme.ui.text.primary,
                      minWidth: '1.25em',
                      flexShrink: 0,
                    }}
                  >
                    {label}
                  </span>
                ) : null}
                <div
                  style={{
                    flex: '1 1 200px',
                    fontSize: '14px',
                    lineHeight: 1.6,
                    color: theme.ui.text.primary,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {desc || '（无描述）'}
                </div>
                {ageTag ? (
                  <span style={{ ...badgeStyle, marginLeft: 'auto', flexShrink: 0 }}>{ageTag}</span>
                ) : null}
              </div>
            );
          })}
        </div>

        {sharedMaterials.length > 0 ? (
          <div>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: theme.ui.text.secondary,
                marginBottom: theme.spacing.xs,
              }}
            >
              材料
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: theme.spacing.xs }}>
              {sharedMaterials.map((m, ti) => (
                <span key={`${m}-${ti}`} style={tagStyle}>
                  {m}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {sharedPrecautions ? (
          <div>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: theme.ui.text.secondary,
                marginBottom: theme.spacing.xs,
              }}
            >
              注意事项
            </div>
            <p
              style={{
                margin: 0,
                fontSize: '13px',
                color: theme.ui.text.secondary,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
              }}
            >
              {sharedPrecautions}
            </p>
          </div>
        ) : null}

        {sharedActivityLines.length > 0 ? (
          <div>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: theme.ui.text.secondary,
                marginBottom: theme.spacing.xs,
              }}
            >
              活动建议
            </div>
            <ol
              style={{
                margin: 0,
                paddingLeft: '1.25em',
                fontSize: '13px',
                color: theme.ui.text.secondary,
                lineHeight: 1.6,
              }}
            >
              {sharedActivityLines.map((line, li) => (
                <li key={li} style={{ marginBottom: '0.25em' }}>
                  {line}
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </div>
    );
  }

  if (legacyGoals.length > 0) {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: theme.spacing.md,
        }}
      >
        {legacyGoals.map((goal, gi) => (
          <LegacyGoalCard key={gi} goal={goal} />
        ))}
      </div>
    );
  }

  return null;
}

const MODULE_EMOJI = ['🗣️', '🧠', '🧴'];

/**
 * Heep Hong (HHH) curriculum: Module → Submodule → Objective → Phasal objective → Goals.
 * Data is loaded from bundled enriched ABox JSON (language, cognition, self-care).
 */
const HHHContentManager = () => {
  const [expanded, setExpanded] = useState(() => {
    const init = {};
    fullCurriculum.forEach((_, mi) => {
      init[`m-${mi}`] = true;
    });
    return init;
  });

  const toggle = useCallback((key) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const isOpen = useCallback(
    (key, defaultOpen = false) => (expanded[key] !== undefined ? expanded[key] : defaultOpen),
    [expanded]
  );

  return (
    <div
      style={{
        marginTop: '20px',
        padding: theme.spacing.lg,
        backgroundColor: '#fff',
        borderRadius: theme.borderRadius.lg,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      <h2
        style={{
          color: '#1e3a8a',
          marginBottom: theme.spacing.lg,
          borderBottom: '2px solid #eff6ff',
          paddingBottom: theme.spacing.sm,
        }}
      >
        🏫 协康会 (HHH) 发展课程（语言 · 认知 · 自理）
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
        {fullCurriculum.map((moduleRoot, mi) => {
          const moduleTitle = MODULE_LEVEL_LABELS[mi] || moduleRoot.module || `模块 ${mi + 1}`;
          const mKey = `m-${mi}`;
          const mExpanded = isOpen(mKey, true);

          const submodules = Array.isArray(moduleRoot.submodules) ? moduleRoot.submodules : [];

          return (
            <div
              key={mKey}
              style={{
                border: `1px solid ${theme.ui.border}`,
                borderRadius: theme.borderRadius.md,
                overflow: 'hidden',
                backgroundColor: theme.ui.backgrounds?.surface ?? '#f8fafc',
              }}
            >
              <AccordionHeader
                id={`hhh-${mKey}`}
                title={moduleTitle}
                expanded={mExpanded}
                onToggle={() => toggle(mKey)}
                level={0}
                emoji={MODULE_EMOJI[mi] ?? '📚'}
              />
              {mExpanded && (
                <div
                  id={`hhh-${mKey}-panel`}
                  role="region"
                  aria-labelledby={`hhh-${mKey}`}
                  style={{ padding: theme.spacing.md, paddingTop: 0 }}
                >
                  {submodules.map((sub, si) => {
                    const sKey = `${mKey}-s-${si}`;
                    const sExpanded = isOpen(sKey, false);
                    const objectives = Array.isArray(sub.objectives) ? sub.objectives : [];

                    return (
                      <div key={sKey} style={{ marginBottom: theme.spacing.md }}>
                        <AccordionHeader
                          id={`hhh-${sKey}`}
                          title={sub.title || `子模块 ${si + 1}`}
                          expanded={sExpanded}
                          onToggle={() => toggle(sKey)}
                          level={1}
                        />
                        {sExpanded && (
                          <div
                            id={`hhh-${sKey}-panel`}
                            role="region"
                            aria-labelledby={`hhh-${sKey}`}
                            style={{ marginLeft: 12, marginTop: theme.spacing.sm }}
                          >
                            {objectives.map((objective, oi) => {
                              const oKey = `${sKey}-o-${oi}`;
                              const oExpanded = isOpen(oKey, false);
                              const phases = Array.isArray(objective.phasal_objectives)
                                ? objective.phasal_objectives
                                : [];

                              return (
                                <div key={oKey} style={{ marginBottom: theme.spacing.sm }}>
                                  <AccordionHeader
                                    id={`hhh-${oKey}`}
                                    title={objective.title || `目标 ${oi + 1}`}
                                    expanded={oExpanded}
                                    onToggle={() => toggle(oKey)}
                                    level={2}
                                  />
                                  {oExpanded && (
                                    <div
                                      id={`hhh-${oKey}-panel`}
                                      role="region"
                                      aria-labelledby={`hhh-${oKey}`}
                                      style={{ marginLeft: 12, marginTop: theme.spacing.sm }}
                                    >
                                      {phases.map((phase, pi) => {
                                        const pKey = `${oKey}-p-${pi}`;
                                        const pExpanded = isOpen(pKey, false);
                                        const phaseLabel = phase.index
                                          ? `${phase.index} ${phase.title || ''}`.trim()
                                          : phase.title || `阶段 ${pi + 1}`;
                                        const subGoals = Array.isArray(phase.sub_goals)
                                          ? phase.sub_goals
                                          : [];
                                        const goals = Array.isArray(phase.goals) ? phase.goals : [];
                                        const hasGoalContent =
                                          subGoals.length > 0 || goals.length > 0;

                                        return (
                                          <div key={pKey} style={{ marginBottom: theme.spacing.sm }}>
                                            <AccordionHeader
                                              id={`hhh-${pKey}`}
                                              title={phaseLabel}
                                              expanded={pExpanded}
                                              onToggle={() => toggle(pKey)}
                                              level={3}
                                            />
                                            {pExpanded && (
                                              <div
                                                id={`hhh-${pKey}-panel`}
                                                role="region"
                                                aria-labelledby={`hhh-${pKey}`}
                                                style={{
                                                  marginLeft: 12,
                                                  marginTop: theme.spacing.sm,
                                                  marginBottom: theme.spacing.md,
                                                }}
                                              >
                                                {hasGoalContent ? (
                                                  <PhasalObjectiveContainer phasalObjective={phase} />
                                                ) : (
                                                  <p
                                                    style={{
                                                      fontSize: '13px',
                                                      color: theme.ui.text.hint,
                                                      fontStyle: 'italic',
                                                    }}
                                                  >
                                                    暂无训练目标
                                                  </p>
                                                )}
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default HHHContentManager;
