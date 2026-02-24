import React, { useState, useEffect } from 'react';
import { CognitionQuestService } from '../services/cognition/cognitionQuestService';
import theme from '../styles/theme';

/**
 * Quest Card - displays a single quest with title, uri_id, materials, and environments.
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
 * Renders unlocked quests as Quest Cards from CognitionQuestService.
 */
const CognitionContentManager = () => {
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await CognitionQuestService.getUnlockedQuests([]);
        setQuests(data);
      } catch (err) {
        console.error('Failed to load quests:', err);
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
        🧠 认知干预模块 (Cognition Module)
      </h2>
      {loading ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          加载中...
        </p>
      ) : quests.length === 0 ? (
        <p style={{ color: theme.ui.text.secondary, fontSize: '16px' }}>
          暂无可用任务
        </p>
      ) : (
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
      )}
    </div>
  );
};

export default CognitionContentManager;
