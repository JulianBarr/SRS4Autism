import React, { useState, useEffect } from 'react';
import { CognitionQuestService } from '../services/cognition/cognitionQuestService';
import theme from '../styles/theme';

/**
 * MacroObjective row - clickable row for a macro objective.
 * TODO: Clicking will eventually open a drawer/modal showing the detailed TeachingTask cards.
 */
const MacroObjectiveRow = ({ objective }) => {
  const { uri_id, label } = objective;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => {
        /* TODO: Open drawer/modal with TeachingTask cards for this objective */
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          /* TODO: Open drawer/modal */
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
      <span
        style={{
          fontSize: '12px',
          color: theme.ui.text.hint,
          fontFamily: 'monospace',
          minWidth: '48px'
        }}
      >
        {uri_id.replace(/^.*:/, '')}
      </span>
      <span style={{ fontSize: '14px', color: theme.ui.text.primary, flex: 1 }}>
        {label}
      </span>
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

/**
 * Cognition Content Manager
 * Renders hierarchical TOC (Module -> MacroObjective by age bracket) from getMacroStructure().
 * TeachingTask cards are hidden by default; clicking a MacroObjective will eventually
 * open a drawer/modal showing those detailed cards.
 */
const CognitionContentManager = () => {
  const [macroGroups, setMacroGroups] = useState([]);
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [macroData, questData] = await Promise.all([
          CognitionQuestService.getMacroStructure(),
          CognitionQuestService.getUnlockedQuests([])
        ]);
        setMacroGroups(macroData);
        setQuests(questData);
      } catch (err) {
        console.error('Failed to load cognition content:', err);
        setMacroGroups([]);
        setQuests([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

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
      <h2
        style={{
          color: theme.categories.cognition.primary,
          marginBottom: theme.spacing.md,
          fontSize: '22px',
          fontWeight: '600'
        }}
      >
        🧠 认知发展篇 (Cognitive Development Module)
      </h2>
      {loading ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          加载中...
        </p>
      ) : macroGroups.length === 0 ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          暂无可用内容
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: theme.spacing.md }}>
          {macroGroups.map((group) => (
            <details
              key={group.ageBracket}
              open
              style={{
                backgroundColor: theme.ui.background,
                borderRadius: theme.borderRadius.md,
                border: `1px solid ${theme.ui.border}`,
                overflow: 'hidden'
              }}
            >
              <summary
                style={{
                  padding: theme.spacing.md,
                  fontSize: '16px',
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
                {group.objectives.map((obj) => (
                  <MacroObjectiveRow key={obj.uri_id} objective={obj} />
                ))}
              </div>
            </details>
          ))}
        </div>
      )}

      {/* TeachingTask cards - hidden by default. Clicking a MacroObjective row will
          eventually open a drawer/modal showing these detailed cards for that objective. */}
      {quests.length > 0 && (
        <div style={{ display: 'none' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: theme.spacing.lg
            }}
          >
            {quests.map((quest) => (
              <QuestCard key={quest.uri_id} quest={quest} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CognitionContentManager;
