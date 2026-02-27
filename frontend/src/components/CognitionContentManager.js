import React, { useState, useEffect } from 'react';
import { CognitionQuestService } from '../services/cognition/cognitionQuestService';
import theme from '../styles/theme';

/**
 * MacroObjective row - clickable row for a macro objective.
 * Expands to show Level 3 Quest Cards (phases) when clicked.
 */
const MacroObjectiveRow = ({ objective, isExpanded, onToggle }) => {
  const { uri_id, label, phases } = objective;
  const hasPhases = phases && phases.length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <div
        role="button"
        tabIndex={0}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: theme.spacing.sm,
          padding: `${theme.spacing.sm} ${theme.spacing.md}`,
          borderRadius: theme.borderRadius.sm,
          cursor: 'pointer',
          backgroundColor: theme.ui.background,
          border: `1px solid ${theme.ui.border}`,
          transition: 'background-color 0.15s ease, border-color 0.15s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = theme.ui.backgrounds.hover;
          e.currentTarget.style.borderColor = theme.categories.cognition.light;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = theme.ui.background;
          e.currentTarget.style.borderColor = theme.ui.border;
        }}
      >
        <span style={{ fontSize: '14px', color: theme.ui.text.primary, flex: 1 }}>
          {label}
        </span>
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            color: theme.ui.text.hint,
            transition: 'transform 0.2s ease'
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
            }}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </span>
      </div>
      {isExpanded && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: theme.spacing.sm,
            padding: theme.spacing.md,
            marginTop: theme.spacing.xs,
            marginLeft: theme.spacing.lg,
            backgroundColor: theme.ui.backgrounds.surface,
            borderRadius: theme.borderRadius.sm,
            borderLeft: `3px solid ${theme.categories.cognition.light}`,
            transition: 'opacity 0.2s ease'
          }}
        >
          {hasPhases ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                gap: theme.spacing.md
              }}
            >
              {phases.map((quest) => (
                <QuestCard key={quest.uri_id} quest={quest} />
              ))}
            </div>
          ) : (
            <p
              style={{
                fontSize: '13px',
                color: theme.ui.text.secondary,
                fontStyle: 'italic',
                margin: 0
              }}
            >
              暂无阶段任务 (No phasal quests yet)
            </p>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Quest Card - displays a single quest with title, uri_id, materials, and environments.
 * Kept for future use when MacroObjective drawer/modal shows TeachingTask cards.
 */
const QuestCard = ({ quest }) => {
  const { uri_id, title, materials, environments } = quest;
  const desktopCount = environments?.structured_desktop?.steps?.length ?? 0;
  const socialCount = environments?.group_social?.length ?? 0;
  const homeCount = environments?.home_natural?.length ?? 0;

  return (
    <div
      style={{
        backgroundColor: theme.ui.background,
        borderRadius: theme.borderRadius.lg,
        border: `1px solid ${theme.ui.border}`,
        padding: theme.spacing.lg,
        boxShadow: theme.shadows.sm,
        display: 'flex',
        flexDirection: 'column',
        gap: theme.spacing.md
      }}
    >
      <h3
        style={{
          color: theme.categories.cognition.primary,
          fontSize: '18px',
          fontWeight: '600',
          margin: 0
        }}
      >
        {title}
      </h3>
      <span
        style={{
          fontSize: '11px',
          color: theme.ui.text.hint,
          fontFamily: 'monospace',
          backgroundColor: theme.ui.backgrounds.surface,
          padding: `${theme.spacing.xs} ${theme.spacing.sm}`,
          borderRadius: theme.borderRadius.sm,
          alignSelf: 'flex-start'
        }}
      >
        {uri_id}
      </span>
      {materials?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: theme.spacing.xs }}>
          {materials.map((m) => (
            <span
              key={m}
              style={{
                fontSize: '12px',
                padding: `${theme.spacing.xs} ${theme.spacing.sm}`,
                backgroundColor: theme.statusBackgrounds.info,
                color: theme.categories.cognition.dark,
                borderRadius: theme.borderRadius.sm
              }}
            >
              {m}
            </span>
          ))}
        </div>
      )}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: theme.spacing.sm,
          marginTop: theme.spacing.xs
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: theme.spacing.xs,
            fontSize: '12px',
            color: theme.ui.text.secondary
          }}
        >
          <span title="Structured Desktop">🖥️</span>
          <span>{desktopCount} {desktopCount === 1 ? 'step' : 'steps'}</span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: theme.spacing.xs,
            fontSize: '12px',
            color: theme.ui.text.secondary
          }}
        >
          <span title="Group Social">👥</span>
          <span>{socialCount} {socialCount === 1 ? 'activity' : 'activities'}</span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: theme.spacing.xs,
            fontSize: '12px',
            color: theme.ui.text.secondary
          }}
        >
          <span title="Home Natural">🏠</span>
          <span>{homeCount} {homeCount === 1 ? 'activity' : 'activities'}</span>
        </div>
      </div>
    </div>
  );
};

/** Emoji mapping for each module */
const MODULE_EMOJI = {
  '认知发展篇': '🧠',
  '语言表达篇': '🗣️',
  '语言理解篇': '👂',
  '小肌肉发展篇': '🤏',
  '大肌肉发展篇': '🏃‍♂️',
  '模仿发展篇': '👯',
  '未分类模块': '📋'
};

/**
 * Cognition Content Manager
 * Renders hierarchical TOC (Module -> Age Bracket -> MacroObjective) from getMacroStructure().
 * Each module (认知发展篇, 大肌肉发展篇, etc.) is a top-level section; within each,
 * age brackets are accordion panels containing MacroObjectives.
 */
const CognitionContentManager = () => {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedObjective, setExpandedObjective] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await CognitionQuestService.getMacroStructure();
        setModules(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Failed to load cognition content:', err);
        setModules([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleToggleObjective = (uriId) => {
    setExpandedObjective((prev) => (prev === uriId ? null : uriId));
  };

  return (
    <div
      style={{
        marginTop: '20px',
        padding: theme.spacing.lg,
        backgroundColor: theme.categories.cognition.background,
        borderRadius: theme.borderRadius.lg,
        border: `1px solid ${theme.categories.cognition.light}`
      }}
    >
      {loading ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          加载中...
        </p>
      ) : modules.length === 0 ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          暂无可用内容
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.xl }}>
          {modules.map((mod) => {
            const emoji = MODULE_EMOJI[mod.moduleName] || '📋';
            return (
              <div
                key={mod.moduleName}
                style={{
                  backgroundColor: theme.ui.background,
                  borderRadius: theme.borderRadius.md,
                  border: `1px solid ${theme.ui.border}`,
                  overflow: 'hidden'
                }}
              >
                <h2
                  style={{
                    padding: theme.spacing.md,
                    color: theme.categories.cognition.primary,
                    fontSize: '20px',
                    fontWeight: '600',
                    margin: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: theme.spacing.sm
                  }}
                >
                  <span>{emoji}</span>
                  <span>{mod.moduleName}</span>
                </h2>
                <div
                  style={{
                    padding: `0 ${theme.spacing.md} ${theme.spacing.md}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: theme.spacing.sm
                  }}
                >
                  {(mod.ageGroups || []).map((group) => (
                    <details
                      key={`${mod.moduleName}-${group.ageBracket}`}
                      open
                      style={{
                        backgroundColor: theme.ui.backgrounds.surface,
                        borderRadius: theme.borderRadius.sm,
                        border: `1px solid ${theme.ui.border}`,
                        overflow: 'hidden'
                      }}
                    >
                      <summary
                        style={{
                          padding: theme.spacing.md,
                          fontSize: '15px',
                          fontWeight: '600',
                          color: theme.categories.cognition.primary,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: theme.spacing.sm
                        }}
                      >
                        <span>📍</span>
                        <span>{group.ageBracket}年龄段训练目标</span>
                      </summary>
                      <div
                        style={{
                          padding: `0 ${theme.spacing.md} ${theme.spacing.md}`,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: theme.spacing.xs
                        }}
                      >
                        {(group.objectives || []).map((obj) => (
                          <MacroObjectiveRow
                            key={obj.uri_id}
                            objective={obj}
                            isExpanded={expandedObjective === obj.uri_id}
                            onToggle={() => handleToggleObjective(obj.uri_id)}
                          />
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CognitionContentManager;
