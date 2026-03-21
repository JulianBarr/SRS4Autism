import React from 'react';

export default function AICard({ data }) {
  if (!data) return null;

  const {
    card_type,
    topic,
    difficulty,
    macro_objective,
    phasal_objective,
    suggested_materials,
    teaching_steps,
    home_generalization,
    analysis
  } = data;

  const isPhysical = card_type === 'PHYSICAL_QUEST';
  const headerBg = isPhysical ? '#FFF7ED' : '#EFF6FF';
  const headerBorder = isPhysical ? '#FED7AA' : '#BFDBFE';
  const headerTextColor = isPhysical ? '#9A3412' : '#1E40AF';
  const headerIcon = isPhysical ? '🏃' : '📱';
  const headerLabel = isPhysical ? '物理互动副本' : (card_type === 'DIGITAL_ANKI' ? '数字认知闪卡' : card_type);

  return (
    <div style={{
      marginTop: '12px',
      backgroundColor: '#FFFFFF',
      borderRadius: '12px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      border: '1px solid #E5E7EB',
      overflow: 'hidden',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* 头部类型标识 */}
      <div style={{
        backgroundColor: headerBg,
        borderBottom: `1px solid ${headerBorder}`,
        padding: '12px 16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: headerTextColor, fontWeight: '600', fontSize: '15px' }}>
          <span>{headerIcon}</span>
          <span>{headerLabel}</span>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <span style={{ backgroundColor: '#F3F4F6', color: '#4B5563', fontSize: '12px', padding: '2px 8px', borderRadius: '12px', fontWeight: '500' }}>
            L{difficulty}
          </span>
          <span style={{ backgroundColor: '#F3F4F6', color: '#4B5563', fontSize: '12px', padding: '2px 8px', borderRadius: '12px', fontWeight: '500' }}>
            {topic}
          </span>
        </div>
      </div>

      {/* 核心内容区 */}
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        
        {/* 知识图谱节点展示 */}
        <div style={{ display: 'flex', gap: '8px', fontSize: '14px' }}>
          <div style={{ flex: 1, backgroundColor: '#F9FAFB', padding: '10px', borderRadius: '8px', border: '1px solid #F3F4F6' }}>
            <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '4px' }}>宏观目标 (Macro)</div>
            <div style={{ color: '#111827', fontWeight: '500' }}>{macro_objective || '未指定'}</div>
          </div>
          <div style={{ flex: 1, backgroundColor: '#F9FAFB', padding: '10px', borderRadius: '8px', border: '1px solid #F3F4F6' }}>
            <div style={{ color: '#6B7280', fontSize: '12px', marginBottom: '4px' }}>阶段目标 (Phasal)</div>
            <div style={{ color: '#111827', fontWeight: '500' }}>{phasal_objective || '未指定'}</div>
          </div>
        </div>

        {/* 简短分析 */}
        {analysis && (
          <div style={{ fontSize: '14px' }}>
            <div style={{ color: '#4B5563', fontWeight: '600', marginBottom: '6px' }}>📝 分析总结</div>
            <div style={{ color: '#374151', lineHeight: '1.5' }}>{analysis}</div>
          </div>
        )}

        {/* 教具准备 */}
        {suggested_materials && suggested_materials.length > 0 && (
          <div style={{ fontSize: '14px' }}>
            <div style={{ color: '#4B5563', fontWeight: '600', marginBottom: '6px' }}>🎒 教具准备</div>
            <ul style={{ margin: 0, paddingLeft: '20px', color: '#374151', lineHeight: '1.5' }}>
              {suggested_materials.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        )}

        {/* 教学步骤 */}
        {teaching_steps && teaching_steps.length > 0 && (
          <div style={{ fontSize: '14px' }}>
            <div style={{ color: '#4B5563', fontWeight: '600', marginBottom: '6px' }}>👣 教学步骤</div>
            <ol style={{ margin: 0, paddingLeft: '20px', color: '#374151', lineHeight: '1.6' }}>
              {teaching_steps.map((step, i) => <li key={i}>{step}</li>)}
            </ol>
          </div>
        )}

        {/* 家庭泛化 */}
        {home_generalization && (
          <div style={{ fontSize: '14px' }}>
            <div style={{ color: '#4B5563', fontWeight: '600', marginBottom: '6px' }}>🏡 家庭泛化</div>
            <div style={{ color: '#374151', lineHeight: '1.5', backgroundColor: '#F0FDF4', padding: '10px', borderRadius: '8px', border: '1px solid #BBF7D0' }}>
              {home_generalization}
            </div>
          </div>
        )}
      </div>

      {/* 底部动作栏 */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #E5E7EB', backgroundColor: '#F9FAFB' }}>
        <button 
          style={{
            width: '100%',
            padding: '10px 0',
            backgroundColor: '#2563EB',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            fontSize: '15px',
            fontWeight: '600',
            cursor: 'pointer',
            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px',
            transition: 'background-color 0.2s'
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#1D4ED8'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2563EB'}
          onClick={() => alert(`已将【${topic}】加入今日训练计划！`)}
        >
          🚀 一键加入今日训练计划
        </button>
      </div>
    </div>
  );
}
