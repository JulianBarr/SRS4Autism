import React, { useState, useCallback } from 'react';
import theme from '../styles/theme';
// CRA only bundles JSON under src/. Files mirror scripts/data_extraction/{21,22,23}_*_enriched_abox.json.
import languageData from '../data/21_heep_hong_language_enriched_abox.json';
import cognitionData from '../data/22_cognition_enriched_abox.json';
import selfCareData from '../data/23_self_care_enriched_abox.json';

/** Canonical Level-1 labels (third file may use a mismatched `module` in JSON). */
const MODULE_LEVEL_LABELS = ['语言', '认知', '自理'];

const fullCurriculum = [languageData, cognitionData, selfCareData];

/** Matches age suffix after slash, e.g. "/ 0-6 个月", "/ 1-2岁", "/ >0 岁". */
const GOAL_DESCRIPTION_AGE_SUFFIX =
  /\s*[/／]\s*((?:>\s*)?\d+(?:\s*[-–]\s*\d+)?\s*(?:个月|岁))/g;

/**
 * Extracts age fragments after an ASCII or fullwidth slash.
 * Removes every matched segment from the description and returns unique age strings for badges.
 */
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

function GoalCard({ goal }) {
  const { cleanText, ageBadges } = stripAgeFromDescriptionText(goal.description || '');
  const materials = Array.isArray(goal.materials) ? goal.materials : [];
  const precautions = goal.precautions;
  const activitySuggestions = goal.activity_suggestions;

  return (
    <div
      style={{
        position: 'relative',
        backgroundColor: theme.ui.background,
        borderRadius: theme.borderRadius.lg,
        border: `1px solid ${theme.ui.border}`,
        padding: theme.spacing.lg,
        paddingTop: ageBadges.length ? theme.spacing.xl : theme.spacing.lg,
        boxShadow: theme.shadows?.sm ?? '0 1px 2px rgba(0,0,0,0.06)',
        display: 'flex',
        flexDirection: 'column',
        gap: theme.spacing.md,
        minHeight: '80px',
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
            {materials.map((m) => (
              <span key={m} style={tagStyle}>
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
                <div style={{ padding: theme.spacing.md, paddingTop: 0 }}>
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
                          <div style={{ marginLeft: 12, marginTop: theme.spacing.sm }}>
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
                                    <div style={{ marginLeft: 12, marginTop: theme.spacing.sm }}>
                                      {phases.map((phase, pi) => {
                                        const pKey = `${oKey}-p-${pi}`;
                                        const pExpanded = isOpen(pKey, false);
                                        const phaseLabel = phase.index
                                          ? `${phase.index} ${phase.title || ''}`.trim()
                                          : phase.title || `阶段 ${pi + 1}`;
                                        const goals = Array.isArray(phase.goals) ? phase.goals : [];

                                        return (
                                          <div key={pKey} style={{ marginBottom: theme.spacing.sm }}>
                                            <AccordionHeader
                                              id={`hhh-${pKey}`}
                                              title={phaseLabel}
                                              expanded={pExpanded}
                                              onToggle={() => toggle(pKey)}
                                              level={3}
                                            />
                                            {pExpanded && goals.length > 0 && (
                                              <div
                                                style={{
                                                  display: 'grid',
                                                  gridTemplateColumns:
                                                    'repeat(auto-fill, minmax(300px, 1fr))',
                                                  gap: theme.spacing.md,
                                                  marginLeft: 12,
                                                  marginTop: theme.spacing.sm,
                                                  marginBottom: theme.spacing.md,
                                                }}
                                              >
                                                {goals.map((goal, gi) => (
                                                  <GoalCard
                                                    key={`${pKey}-g-${gi}`}
                                                    goal={goal}
                                                  />
                                                ))}
                                              </div>
                                            )}
                                            {pExpanded && goals.length === 0 && (
                                              <p
                                                style={{
                                                  marginLeft: 12,
                                                  fontSize: '13px',
                                                  color: theme.ui.text.hint,
                                                  fontStyle: 'italic',
                                                }}
                                              >
                                                暂无训练目标
                                              </p>
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
