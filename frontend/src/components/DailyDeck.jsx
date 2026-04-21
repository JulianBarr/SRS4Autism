import React, { useState, useEffect, useCallback, useRef } from 'react';
import api, { API_BASE, cloudApi } from '../utils/api';
import SurveyFeedCard from './SurveyFeedCard';
import AICard from './AICard';
import VBMappSubgraphExplorer from './VBMappSubgraphExplorer';
import { Network } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';

function cleanTaskTitle(rawTitle) {
  if (!rawTitle) return '';

  let cleaned = String(rawTitle)
    // 1) Remove common list prefixes: "A. ", "3. ", "(3) "
    .replace(/^(?:[A-Z]\.|[0-9]+\.|\(\d+\))\s*/u, '')
    // 2) Remove age suffixes like "/ 1-3 岁"
    .replace(/\s*\/\s*\d+\s*-\s*\d+\s*岁.*$/u, '');

  // 3) Repeatedly remove bracketed examples, including nested fragments.
  let prev;
  do {
    prev = cleaned;
    cleaned = cleaned.replace(/[（(【][^）)】]*[）)】]/gu, '');
  } while (cleaned !== prev);

  // 4) Trim punctuation noise around the core phrase.
  return cleaned
    .replace(/^[、，。：；\s]+|[、，。：；\s]+$/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function escapeSparqlLiteral(value) {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function extractVbmappLabel(rawText) {
  if (!rawText) return '';
  const text = String(rawText).trim();
  if (!text) return '';
  const withoutPrefix = text.replace(/^【\s*VB-MAPP\s*】/i, '').trim();
  const [head] = withoutPrefix.split(/[：:]/);
  return (head || withoutPrefix).trim();
}

//       onMouseEnter={() => setShow(true)}
//       onMouseLeave={() => setShow(false)}
//     >
//       <span
//         style={{
//           display: 'inline-flex',
//           alignItems: 'center',
//           justifyContent: 'center',
//           width: '20px',
//           height: '20px',
//           fontSize: '14px',
//           fontWeight: 700,
//           color: '#4338ca',
//           backgroundColor: '#e0e7ff',
//           borderRadius: '50%',
//           border: '1px solid #818cf8'
//         }}
//       >
//         i
//       </span>
//       {show && (
//         <div
//           style={{
//             position: 'absolute',
//             zIndex: 50,
//             left: 0,
//             top: '100%',
//             marginTop: '6px',
//             width: '280px',
//             maxWidth: '90vw',
//             padding: '12px',
//             fontSize: '13px',
//             textAlign: 'left',
//             backgroundColor: '#1e293b',
//             color: '#e2e8f0',
//             borderRadius: '8px',
//             boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
//             border: '1px solid #334155'
//           }}
//           role="tooltip"
//         >
//           <div style={{ fontWeight: 600, color: '#a5b4fc', marginBottom: '8px' }}>PEP-3 评估项描述</div>
//           <ul style={{ margin: 0, paddingLeft: '18px', lineHeight: 1.6 }}>
//             {details.map((item, i) => (
//               <li key={i} style={{ marginBottom: '4px' }}>{item}</li>
//             ))}
//           </ul>
//         </div>
//       )}
//     </span>
//   );
// }

/** PEP3 悬停提示：鼠标悬停显示完整描述 */
function Pep3Tooltip({ pep3Standard, pep3Items }) {
  const { t } = useLanguage();
  const [show, setShow] = useState(false);
  if (!pep3Standard) return null;
  const hasDetails = pep3Items && pep3Items.length > 0;
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span
        className={`
          ml-2 text-xs cursor-help border-b border-dotted
          ${hasDetails ? 'border-indigo-400 text-indigo-700 hover:border-indigo-600' : 'border-slate-400 text-slate-600'}
        `}
      >
        {pep3Standard}
      </span>
      {hasDetails && (
        <>
          <span className="ml-1 text-indigo-500 text-xs">ⓘ</span>
          {show && (
            <div
              className="absolute z-10 left-0 top-full mt-1 w-72 max-w-[90vw] p-3 text-xs text-left bg-slate-800 text-slate-100 rounded-lg shadow-lg border border-slate-600"
              role="tooltip"
            >
              <div className="font-medium text-indigo-200 mb-2">{t('ddPep3AssessmentTitle')}</div>
              <ul className="space-y-1 list-disc list-inside">
                {pep3Items.map((item, i) => (
                  <li key={i} className="leading-relaxed">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </span>
  );
}


/** Topic Chat 沟通与记录模态框 - 家校接力 */
function QuestTopicChatModal({ quest, childName, childId, onClose }) {
  const { t } = useLanguage();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [resolvedChildId, setResolvedChildId] = useState(null);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    let active = true;
    const resolveId = async () => {
      try {
        if (typeof childId === 'number' || (typeof childId === 'string' && childId.trim() !== '' && !isNaN(Number(childId)))) {
          if (active) setResolvedChildId(Number(childId));
          return;
        }
        const res = await cloudApi.get('/api/v1/children/me');
        if (!active) return;
        
        const safeChildName = (childName || '').trim();
        const normalize = (str) => str ? str.replace(/\s+/g, '').toLowerCase() : '';
        const match = childName ? res.data.find(c => normalize(c.name) === normalize(childName)) : null;
        
        if (match && match.id) {
          if (active) setResolvedChildId(match.id);
        } else if (res.data && res.data.length > 0) {
          if (childName) {
            console.warn('Name mismatch, fallback to first child. Wanted:', safeChildName, 'Got:', res.data[0].name);
          }
          if (active) setResolvedChildId(res.data[0].id);
        } else {
          console.warn('Could not resolve integer childId from cloudApi for:', childName);
          if (active) setLoading(false); // Unblock loading state if resolution fails
        }
      } catch (err) {
        console.error('Failed to resolve child ID:', err);
        if (active) setLoading(false); // Unblock loading on error
      }
    };
    resolveId();
    return () => { active = false; };
  }, [childName, childId]);

  const fetchLogs = useCallback(async (silent = false) => {
    if (!quest?.quest_id || !resolvedChildId) return;
    if (!silent) setLoading(true);
    try {
      const res = await cloudApi.get(`/api/v1/children/${resolvedChildId}/logs`);
      const data = res.data;
      
      const mappedLogs = data.map(log => {
        let mappedRole = log.sender_role;
        if (mappedRole === 'agent') mappedRole = 'ai';
        if (mappedRole === 'qcq_admin') mappedRole = 'admin';
        return {
          role: mappedRole || 'parent',
          content: log.content,
          timestamp: log.created_at,
          file_url: null,
          file_type: null
        };
      });
      
      const newLogs = mappedLogs.reverse();
      setLogs(prev => {
        if (prev.length === newLogs.length) {
          // Check if any message content changed (e.g. streaming update)
          const hasChanged = prev.some((log, i) => 
            log.content !== newLogs[i].content || 
            log.role !== newLogs[i].role
          );
          if (!hasChanged) return prev;
        }
        return newLogs;
      });
    } catch {
      if (!silent) setLogs([]);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [quest?.quest_id, resolvedChildId]);

  useEffect(() => {
    fetchLogs();
    const intervalId = setInterval(() => {
      fetchLogs(true);
    }, 3000);
    return () => clearInterval(intervalId);
  }, [fetchLogs]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleSend = async () => {
    const content = input.trim();
    if (!content || sending || !resolvedChildId) return;
    setSending(true);
    try {
      const res = await cloudApi.post(`/api/v1/children/${resolvedChildId}/logs`, { content });
      setInput('');
      setSelectedFile(null);
      await fetchLogs(true);
    } catch (err) {
      console.error('发送失败:', err);
    } finally {
      setSending(false);
    }
  };

  const roleLabel = { parent: t('ddRoleParent'), teacher: t('ddRoleTeacher'), ai: t('ddRoleAi') };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0, left: 0, width: '100vw', height: '100vh',
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        zIndex: 99999,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px',
        boxSizing: 'border-box'
      }}
      onClick={onClose}
      role="dialog"
    >
      {/* 弹窗本体：宽90%（最大800px），高85vh */}
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          width: '90%',
          maxWidth: '800px',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header：左右两端对齐，X在右上角 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', borderBottom: '1px solid #f1f5f9', backgroundColor: '#f8fafc', flexShrink: 0 }}>
          <h3 style={{ fontWeight: 600, fontSize: '1.125rem', color: '#1e293b', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            💬 {t('ddChatModalTitle').replace('{label}', quest?.label || '')}
          </h3>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: '#64748b', padding: '4px 8px', borderRadius: '8px' }}
          >
            ✕
          </button>
        </div>

        {/* Chat Body：保留原有的渲染逻辑 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', backgroundColor: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {loading ? (
            <div style={{ color: '#64748b', fontSize: '14px', textAlign: 'center', padding: '32px 0' }}>{t('ddChatLoading')}</div>
          ) : logs.length === 0 ? (
            <div style={{ color: '#94a3b8', fontSize: '14px', textAlign: 'center', padding: '32px 0' }}>{t('ddChatEmpty')}</div>
          ) : (
            logs.map((log, i) => {
              if (log.role === 'system') {
                return (
                  <div key={i} style={{ alignSelf: 'center', backgroundColor: '#f1f5f9', color: '#64748b', padding: '6px 16px', borderRadius: '999px', fontSize: '12px', marginTop: '8px' }}>
                    {log.content}
                  </div>
                );
              }
              const isParent = log.role === 'parent';
              
              let textContent = log.content;
              let parsedData = null;
              if (log.role === 'ai' && log.content.includes('```json')) {
                try {
                  const parts = log.content.split('```json');
                  textContent = parts[0].trim();
                  const jsonStr = parts[1].split('```')[0].trim();
                  parsedData = JSON.parse(jsonStr);
                } catch (e) {
                  // Fallback to original content on parse error
                  textContent = log.content;
                  parsedData = null;
                }
              }

              return (
                <div key={i} style={{
                  alignSelf: isParent ? 'flex-end' : 'flex-start',
                  backgroundColor: isParent ? '#dcfce7' : (log.role === 'ai' ? '#ede9fe' : '#dbeafe'),
                  color: isParent ? '#064e3b' : (log.role === 'ai' ? '#4c1d95' : '#1e3a8a'),
                  padding: '12px 16px',
                  borderRadius: '16px',
                  borderBottomRightRadius: isParent ? '4px' : '16px',
                  borderBottomLeftRadius: !isParent ? '4px' : '16px',
                  maxWidth: '80%',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                }}>
                  <span style={{ fontSize: '12px', opacity: 0.6, display: 'block', marginBottom: '6px' }}>
                    {roleLabel[log.role] || log.role}
                  </span>
                  <div style={{ fontSize: '14px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{textContent}</div>
                  {parsedData && <AICard data={parsedData} />}
                  {log.file_url && (
                    <>
                      {log.file_type && log.file_type.startsWith('image/') && (
                        <img
                          src={API_BASE + log.file_url}
                          alt=""
                          style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '8px', display: 'block' }}
                        />
                      )}
                      {log.file_type && log.file_type.startsWith('video/') && (
                        <video
                          controls
                          src={API_BASE + log.file_url}
                          style={{ maxWidth: '100%', borderRadius: '8px', marginTop: '8px', display: 'block' }}
                        />
                      )}
                    </>
                  )}
                  <span style={{ fontSize: '11px', opacity: 0.5, display: 'block', marginTop: '8px', textAlign: 'right' }}>
                    {log.timestamp?.slice(0, 16).replace('T', ' ')}
                  </span>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area：多行文本框 */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', gap: '12px', flexShrink: 0 }}>
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*,video/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setSelectedFile(f);
              e.target.value = '';
            }}
          />
          {selectedFile && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', backgroundColor: '#f1f5f9', borderRadius: '8px', fontSize: '13px', color: '#475569' }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedFile.name}</span>
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '14px', color: '#64748b', padding: '2px 6px' }}
              >
                ✕
              </button>
            </div>
          )}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#e2e8f0'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '18px', padding: '8px', borderRadius: '6px' }}
            title={t('ddUploadMediaTitle')}
          >
            📎
          </button>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={t('ddChatPlaceholder')}
            rows={3}
            style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid #cbd5e1', outline: 'none', resize: 'none', fontFamily: 'inherit', fontSize: '14px', lineHeight: '1.5' }}
          />

          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            style={{ padding: '10px 24px', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500, alignSelf: 'stretch', opacity: (sending || !input.trim()) ? 0.5 : 1 }}
          >
            {t('ddSend')}
          </button>
          </div>
        </div>
      </div>
    </div>
  );
}


const ExpandableQuestCard = ({ quest, isCompleted, showButtons, submitting, onRecordFeedback, onOpenChat }) => {
  const { t } = useLanguage();
  const [isExpanded, setIsExpanded] = useState(false);
  const [vbmappLabel, setVbmappLabel] = useState('');
  const [vbmappUri, setVbmappUri] = useState('');
  const [loadingVbmapp, setLoadingVbmapp] = useState(false);
  const [showGraphExplorer, setShowGraphExplorer] = useState(false);
  const [resolvingGraphUri, setResolvingGraphUri] = useState(false);
  const [graphResolveError, setGraphResolveError] = useState('');
  const [graphCenterUri, setGraphCenterUri] = useState('');
  const isSubmitting = submitting === quest.quest_id;
  const pep3Items = quest.pep3_items || [];
  
  const title = quest.label || quest.title || t('ddUnnamedTask');
  const isHhs = (quest.source || '').toLowerCase() === 'hhs' || quest.content_source === 'HHS';
  const hhsModuleText = (quest.hhs_module || '').trim() || t('ddUnassignedModule');
  const cleanedTaskTitle = cleanTaskTitle(title);
  const shouldQueryVbmapp = cleanedTaskTitle.length >= 2;
  
  const badges = [];
  if (quest.badges) {
    badges.push(...quest.badges);
  } else if (isHhs) {
    const ageText = quest.age_group || t('ddAgeGeneral');
    badges.push(
      t('ddHhsBadgeLine').replace('{module}', hhsModuleText).replace('{age}', ageText)
    );
  } else if (quest.pep3_standard) {
    badges.push(`PEP-3: ${quest.pep3_standard}`);
  }
  
  let conditions = quest.conditions || quest.ecumenical_integration?.assessment?.content || "";
  let prerequisite = quest.prerequisite || quest.ecumenical_integration?.prerequisite?.content || "";
  const normalizeList = (value) => {
    if (Array.isArray(value)) return value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean);
    if (typeof value === 'string') {
      const txt = value.trim();
      return txt ? [txt] : [];
    }
    return [];
  };

  const materialItems = normalizeList(quest.suggested_materials).length
    ? normalizeList(quest.suggested_materials)
    : normalizeList(quest.materials || quest.ecumenical_integration?.teaching?.materials);
  const activityItems = normalizeList(quest.activities);
  const precautionItems = normalizeList(quest.precautions);
  const fallbackStepText = quest.teaching_steps || quest.steps || quest.ecumenical_integration?.teaching?.steps || quest.ecumenical_integration?.teaching?.content || "";
  const renderedSteps = [...activityItems, ...precautionItems].length > 0
    ? [
        ...activityItems.map((a) => `${t('ddActivityPrefix')} ${a}`),
        ...precautionItems.map((p) => `${t('ddPrecautionPrefix')} ${p}`),
      ].join('\n')
    : fallbackStepText;
  let generalization = quest.home_generalization || quest.generalization || quest.ecumenical_integration?.generalization?.content || "";
  const inferredQuestVbmappUri =
    quest.vbmapp_uri ||
    quest.vbmappUri ||
    quest.vbmapp_node_uri ||
    quest.vbmappNodeUri ||
    quest.ecumenical_integration?.prerequisite?.uri ||
    quest.ecumenical_integration?.prerequisite?.node_uri ||
    '';
  const currentVbmappUri = (inferredQuestVbmappUri || vbmappUri || '').trim();
  const resolvedCenterUri = (graphCenterUri || currentVbmappUri).trim();
  const vbmappCandidateLabel = extractVbmappLabel(prerequisite || vbmappLabel || '');
  const canTriggerGraphExplorer = Boolean(vbmappCandidateLabel || cleanedTaskTitle || currentVbmappUri);

  const resolveUriByLabel = useCallback(async (labelText) => {
    const candidate = (labelText || '').trim();
    if (!candidate) return '';
    const exactSparql = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?vbmappInst WHERE {
  ?vbmappInst rdfs:label ?lbl .
  FILTER(LANG(?lbl) = "zh")
  FILTER(STR(?lbl) = "${escapeSparqlLiteral(candidate)}")
} LIMIT 1`;
    const fuzzySparql = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?vbmappInst WHERE {
  ?vbmappInst rdfs:label ?lbl .
  FILTER(LANG(?lbl) = "zh")
  FILTER(CONTAINS(STR(?lbl), "${escapeSparqlLiteral(candidate)}"))
} LIMIT 1`;

    const runQuery = async (sparql) => {
      const response = await fetch(`${API_BASE}/api/kg/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/sparql-query; charset=utf-8',
          Accept: 'application/sparql-results+json',
          Authorization: localStorage.getItem('access_token')
            ? `Bearer ${localStorage.getItem('access_token')}`
            : '',
        },
        body: sparql,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || `HTTP ${response.status}`);
      }
      return data?.results?.bindings?.[0]?.vbmappInst?.value || '';
    };

    const exact = await runQuery(exactSparql);
    if (exact) return exact;
    return runQuery(fuzzySparql);
  }, []);

  const handleOpenGraphExplorer = useCallback(async (event) => {
    event.stopPropagation();
    setGraphResolveError('');
    if (currentVbmappUri) {
      setGraphCenterUri(currentVbmappUri);
      setShowGraphExplorer(true);
      return;
    }

    const candidates = [vbmappCandidateLabel, cleanedTaskTitle].filter(Boolean);
    if (candidates.length === 0) {
      setGraphResolveError(t('graphErrorNoVbmappLabel'));
      return;
    }

    setResolvingGraphUri(true);
    try {
      let resolved = '';
      for (const label of candidates) {
        resolved = await resolveUriByLabel(label);
        if (resolved) break;
      }
      if (!resolved) {
        setGraphResolveError(t('graphErrorUriUnresolved'));
        return;
      }
      setVbmappUri(resolved);
      setGraphCenterUri(resolved);
      setShowGraphExplorer(true);
    } catch (err) {
      console.warn('Failed to resolve VB-MAPP URI for graph explorer:', err);
      setGraphResolveError(t('graphErrorResolveFailed'));
    } finally {
      setResolvingGraphUri(false);
    }
  }, [cleanedTaskTitle, currentVbmappUri, resolveUriByLabel, vbmappCandidateLabel, t]);

  useEffect(() => {
    if (!isHhs || prerequisite || !shouldQueryVbmapp) {
      setVbmappLabel('');
      setVbmappUri('');
      setLoadingVbmapp(false);
      return;
    }

    let active = true;
    const fetchVbmapp = async () => {
      setLoadingVbmapp(true);
      try {
        const sparql = `PREFIX cuma-schema: <http://cuma.ai/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?vbmappInst ?vbmappLabel ?score WHERE {
  ?hhsGoal rdfs:label ?hhsLabel .
  FILTER(CONTAINS(STR(?hhsLabel), "${escapeSparqlLiteral(cleanedTaskTitle)}"))
  ?hhsGoal cuma-schema:alignsWith ?vbmappInst .
  ?vbmappInst rdfs:label ?vbmappLabel .
  FILTER(LANG(?vbmappLabel) = "zh")
  OPTIONAL { ?hhsGoal cuma-schema:matchScore ?score . }
} ORDER BY DESC(?score) LIMIT 1`;
        const response = await fetch(`${API_BASE}/api/kg/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/sparql-query; charset=utf-8',
            Accept: 'application/sparql-results+json',
            Authorization: localStorage.getItem('access_token')
              ? `Bearer ${localStorage.getItem('access_token')}`
              : '',
          },
          body: sparql,
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || `HTTP ${response.status}`);
        }
        const first = data?.results?.bindings?.[0];
        if (!active) return;
        setVbmappLabel(first?.vbmappLabel?.value || '');
        setVbmappUri(first?.vbmappInst?.value || '');
      } catch (err) {
        if (active) {
          setVbmappLabel('');
          setVbmappUri('');
          console.warn('Failed to fetch VB-MAPP prerequisite for HHS card:', err);
        }
      } finally {
        if (active) {
          setLoadingVbmapp(false);
        }
      }
    };

    fetchVbmapp();
    return () => {
      active = false;
    };
  }, [isHhs, prerequisite, shouldQueryVbmapp, cleanedTaskTitle]);

  return (
    <div className={`border border-slate-200 rounded-xl bg-white overflow-hidden shadow-sm ${isCompleted ? 'opacity-60 bg-slate-50' : ''}`}>
      {/* Header */}
      <div 
        className="cursor-pointer p-4 hover:bg-slate-50 transition-colors flex justify-between items-start"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex-1">
          <h2 className="text-lg font-bold text-slate-800">
            {title}
          </h2>
          <div className="flex flex-wrap gap-2 mt-2">
            {badges.map((badge, idx) => (
              <span key={idx} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                {badge}
              </span>
            ))}
            {!isHhs && quest.pep3_standard && !quest.badges && (
               <Pep3Tooltip pep3Standard={quest.pep3_standard} pep3Items={pep3Items} />
            )}
          </div>
        </div>
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500 ml-4">
          <svg 
            className={`w-5 h-5 shrink-0 text-slate-400 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} 
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
            width="20" height="20" style={{ minWidth: '20px', minHeight: '20px' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="p-4 border-t border-slate-100 space-y-4 bg-slate-50/50">
          
          {/* 区块 A - 🎯 核心目标 */}
          {conditions && (
            <div className="bg-blue-50 text-blue-800 p-3 rounded-lg">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <span>🎯</span> {t('ddCoreGoal')}
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed text-sm">
                {conditions}
              </div>
            </div>
          )}

          {/* 区块 B - 🧠 前置能力 */}
          {prerequisite && (
            <div className="bg-purple-50 text-purple-800 p-3 rounded-lg text-sm">
              <h3 className="font-bold mb-1 flex items-center justify-between gap-2">
                <span className="flex items-center gap-2">
                  <span>🧠</span> {t('ddPrerequisite')}
                </span>
                {canTriggerGraphExplorer && (
                  <button
                    type="button"
                    onClick={handleOpenGraphExplorer}
                    disabled={resolvingGraphUri}
                    className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-white/70 px-2 py-0.5 text-xs font-medium text-purple-700 hover:bg-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    title={t('ddAnalyzeInGraph')}
                  >
                    <Network className="h-3.5 w-3.5" />
                    <span>{resolvingGraphUri ? t('ddAnalyzingGraph') : `🗺️ ${t('ddAnalyzeInGraph')}`}</span>
                  </button>
                )}
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed">
                {prerequisite}
              </div>
            </div>
          )}
          {!prerequisite && (loadingVbmapp || vbmappLabel) && (
            <div className="bg-purple-50 text-purple-800 p-3 rounded-lg text-sm">
              <h3 className="font-bold mb-1 flex items-center justify-between gap-2">
                <span className="flex items-center gap-2">
                  <span>🧠</span> {t('ddPrerequisite')}
                </span>
                {canTriggerGraphExplorer && (
                  <button
                    type="button"
                    onClick={handleOpenGraphExplorer}
                    disabled={resolvingGraphUri}
                    className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-white/70 px-2 py-0.5 text-xs font-medium text-purple-700 hover:bg-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    title={t('ddAnalyzeInGraph')}
                  >
                    <Network className="h-3.5 w-3.5" />
                    <span>{resolvingGraphUri ? t('ddAnalyzingGraph') : `🗺️ ${t('ddAnalyzeInGraph')}`}</span>
                  </button>
                )}
              </h3>
              <div className="whitespace-pre-wrap leading-relaxed">
                {loadingVbmapp ? t('ddLoadingPrerequisite') : `${t('ddVbmappBadgePrefix')}${vbmappLabel}`}
              </div>
            </div>
          )}
          {graphResolveError && (
            <p className="text-xs text-red-600 -mt-2">{graphResolveError}</p>
          )}
          {showGraphExplorer && resolvedCenterUri && (
            <div className="rounded-xl border border-purple-200 bg-white p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-xs text-slate-600 truncate">
                  {t('ddGraphCenterLabel')} {resolvedCenterUri}
                </div>
                <button
                  type="button"
                  className="text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded px-2 py-0.5"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowGraphExplorer(false);
                  }}
                >
                  {t('ddCloseGraph')}
                </button>
              </div>
              <div className="h-[80vh] min-h-[520px] w-full rounded-lg border border-slate-200 overflow-hidden">
                <VBMappSubgraphExplorer
                  initialCenterUri={resolvedCenterUri}
                  className="!h-full"
                  style={{ height: '100%' }}
                />
              </div>
            </div>
          )}

          {/* 区块 C - 🛠️ 教具与步骤 */}
          {(materialItems.length > 0 || renderedSteps) && (
            <div className="bg-white border border-slate-100 p-3 rounded-lg">
              <h3 className="font-bold text-slate-700 mb-2 flex items-center gap-2">
                <span>🛠️</span> {t('ddMaterialsSteps')}
              </h3>
              {materialItems.length > 0 && (
                <div className="mb-2 text-sm text-slate-700">
                  <span className="font-semibold text-slate-800">{t('ddMaterialsPrep')}</span>
                  <ul className="mt-1 list-disc list-inside">
                    {materialItems.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {renderedSteps && (
                <div className="text-sm text-slate-600 whitespace-pre-wrap leading-relaxed">
                  {renderedSteps}
                </div>
              )}
            </div>
          )}

          {/* 区块 D - 🏡 家庭泛化 */}
          {generalization && (
            <div className="bg-amber-50 text-amber-900 p-3 rounded-lg border-l-4 border-amber-400">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <span>🏡</span> {t('ddHomeGeneralization')}
              </h3>
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {generalization}
              </div>
            </div>
          )}

          {/* Action Area */}
          <div className="pt-2">
            <div className="flex justify-end gap-3 mb-4">
              <button
                type="button"
                className="text-sm bg-white text-slate-700 border border-slate-300 px-4 py-2 rounded-lg hover:bg-slate-50 transition font-medium flex items-center gap-2"
                onClick={(e) => { e.stopPropagation(); }}
              >
                <span>📹</span> {t('ddDemoVideoTbd')}
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onOpenChat(quest); }}
                className="text-sm bg-indigo-50 text-indigo-700 border border-indigo-100 px-4 py-2 rounded-lg hover:bg-indigo-100 transition font-medium flex items-center gap-2"
              >
                <span>💬</span> {t('ddChatAndLog')}
              </button>
            </div>

            {showButtons ? (
              <div className="flex gap-4">
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '全辅助'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-red-50 text-red-600 border border-red-200 px-4 py-3 rounded-xl hover:bg-red-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟥 {t('ddPromptFull')}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '部分辅助'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-amber-50 text-amber-600 border border-amber-200 px-4 py-3 rounded-xl hover:bg-amber-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟨 {t('ddPromptPartial')}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onRecordFeedback(quest.quest_id, '独立完成'); }}
                  disabled={isSubmitting}
                  className={`flex-1 bg-emerald-50 text-emerald-600 border border-emerald-200 px-4 py-3 rounded-xl hover:bg-emerald-500 hover:text-white transition-all font-bold shadow-sm ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  🟩 {t('ddPromptIndependent')}
                </button>
              </div>
            ) : (
              <div className="flex justify-between items-center bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                <div className="flex items-center gap-2 text-emerald-600 font-bold">
                  <span className="text-xl">✅</span>
                  {t('ddCompletedToday')}
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onOpenChat(quest); }}
                  className="text-sm bg-slate-50 border border-slate-200 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-100 transition font-medium"
                >
                  💬 {t('ddSupplementLog')}
                </button>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
};

function DailyDeck({
  childName = null,
  childId,
  scheduleSource = 'qcq',
  showDemoButton = true,
}) {
  const { t } = useLanguage();
  const [pending, setPending] = useState([]);
  const [completedToday, setCompletedToday] = useState([]);
  const [historyQuests, setHistoryQuests] = useState([]);
  const [weakestDomainInfo, setWeakestDomainInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(null); // quest_id when submitting
  const [questCount, setQuestCount] = useState(3);
  const [currentChatQuest, setCurrentChatQuest] = useState(null);
  const [surveyQuestion, setSurveyQuestion] = useState(null);
  const [surveyBooting, setSurveyBooting] = useState(true);

  const { language } = useLanguage(); // Destructure language from useLanguage here
  const fetchSurveyNext = useCallback(async () => {
    try {
      const res = await api.get(`/api/survey/next?lang=${language}`);
      const d = res.data;
      console.log("fetchSurveyNext received data:", d); // DEBUG LINE
      if (d?.question_uri) {
        setSurveyQuestion(d);
      } else {
        setSurveyQuestion(null);
      }
    } catch (e) {
      console.warn('Survey feed unavailable', e);
      setSurveyQuestion(null);
    } finally {
      setSurveyBooting(false);
    }
  }, [language]);

  useEffect(() => {
    if (!childName) return;
    setSurveyBooting(true);
    fetchSurveyNext();
  }, [childName, fetchSurveyNext]);

  const handleSurveyAnswered = useCallback(async () => {
    await fetchSurveyNext();
  }, [fetchSurveyNext]);

  const renderSurveySection = () =>
    !surveyBooting && surveyQuestion?.question_uri ? (
      <section className="mb-8" aria-label="Adaptive survey">
        <SurveyFeedCard
          key={surveyQuestion.question_uri}
          question={surveyQuestion}
          onAnswerSubmitted={handleSurveyAnswered}
        />
      </section>
    ) : null;

  // Prevent background scroll when modal is open; always restore on unmount
  useEffect(() => {
    if (currentChatQuest) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [currentChatQuest]);

  const openChat = (quest) => setCurrentChatQuest(quest);
  const closeChat = () => setCurrentChatQuest(null);

  const DEMO_MOCK_DATA = {
    quest_id: "demo_1057",
    label: "(3) 特征相同和不同（颜色、形状）",
    badges: ["PEP-3 认知", "VB-MAPP"],
    ecumenical_integration: {
      assessment: { content: "颜色相同、形状不同的物件配对" },
      prerequisite: { content: "【VB-MAPP】视觉表现与配对 6-M：配对20个相同的物品或图片" },
      teaching: {
        materials: "积木片、珠子、雪花片（颜色相同、形状不同的一组）",
        steps: "1. 导师拿出颜色相同、形状不同的一组物件...\n2. 引导儿童说出“XX是相同的”..."
      },
      generalization: { content: "收拾衣服，按长短袖整理，引导儿童观察并说出：“这些衣服是一样的，都是短袖。”" }
    }
  };

  const fetchDailyQuests = useCallback(async () => {
    if (!childName) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/daily_quests', {
        params: {
          child_name: childName,
          count: questCount,
          source: scheduleSource,
        },
      });
      const data = res.data;
      setPending(data.pending || []);
      setCompletedToday(data.completed_today || []);
      setHistoryQuests(data.history_quests || []);
      setWeakestDomainInfo(data.weakest_domain_info || null);
    } catch (err) {
      setError(err.message || t('ddFetchScheduleFailed'));
      setPending([]);
      setCompletedToday([]);
      setHistoryQuests([]);
    } finally {
      setLoading(false);
    }
  }, [childName, questCount, scheduleSource, t]);

  useEffect(() => {
    fetchDailyQuests();
  }, [fetchDailyQuests]);

  const recordFeedback = async (questId, promptLevel) => {
    if (submitting) return;
    setSubmitting(questId);
    try {
      const res = await api.post(`/api/record_feedback`, {
          child_name: childName,
          quest_id: questId,
          prompt_level: promptLevel,
      });
      const data = res.data;
      if (data.status !== 'success') throw new Error(t('ddRecordFailed'));

      // 打卡成功后重新拉取数据，将任务从 pending 移到 completed_today
      await fetchDailyQuests();
    } catch (err) {
      setError(err.message || t('ddRecordFeedbackFailed'));
    } finally {
      setSubmitting(null);
    }
  };

  const totalCount = questCount;
  const completedCount = completedToday.length;
  const allDone = totalCount > 0 && completedCount >= totalCount;

  if (!childName) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-slate-600 text-lg">{t('ddSelectChildFirst')}</div>
      </div>
    );
  }

  const deckHeadline =
    scheduleSource === 'hhs'
      ? t('ddDeckHeadlineHhs').replace('{name}', childName)
      : scheduleSource === 'mixed'
        ? t('ddDeckHeadlineMixed').replace('{name}', childName)
        : t('ddDeckHeadlineQcq').replace('{name}', childName);

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-slate-600 text-lg">{t('ddLoadingSchedule')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-6 max-w-md text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={fetchDailyQuests}
            className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600"
          >
            {t('ddRetry')}
          </button>
        </div>
      </div>
    );
  }

  if (allDone && pending.length === 0) {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <div className="max-w-2xl mx-auto w-full px-4 pt-6">{renderSurveySection()}</div>
        <div className="flex flex-col items-center justify-center p-6 shrink-0">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">
            {t('ddAllDoneTitle')}
          </h2>
          <p className="text-slate-600 mb-6">{t('ddAllDoneSubtitle')}</p>
          <button
            onClick={fetchDailyQuests}
            className="px-6 py-3 bg-amber-500 text-white rounded-xl hover:bg-amber-600 font-medium"
          >
            {t('ddRefreshSchedule')}
          </button>
        </div>
        {completedToday.length > 0 && (
          <div className="max-w-2xl mx-auto w-full px-4 pb-8">
            <h2 className="text-base font-semibold text-slate-600 mb-4">✅ {t('ddCompletedTodaySection')}</h2>
            <div className="space-y-4">
              {completedToday.map((quest) => (
                <div
                  key={quest.quest_id}
                  className="card opacity-60 bg-slate-50 p-4 rounded-lg"
                >
                  <h3 className="font-semibold text-slate-700">{quest.label}</h3>
                  {((quest.source || '').toLowerCase() === 'hhs' || quest.content_source === 'HHS') ? (
                    <p className="text-sm text-slate-500 mt-1">
                      {t('ddHhsBadgeLine')
                        .replace('{module}', (quest.hhs_module || '').trim() || t('ddUnassignedModule'))
                        .replace('{age}', quest.age_group || t('ddAgeGeneral'))}
                    </p>
                  ) : quest.pep3_standard ? (
                    <p className="text-sm text-slate-500 mt-1">PEP-3: {quest.pep3_standard}</p>
                  ) : null}
                  <hr className="my-4 border-gray-100" />
                  <div className="flex justify-between items-center bg-gray-50 p-3 rounded-lg">
                    <div className="flex items-center gap-2 text-emerald-700 font-bold">
                      <span>✅</span>
                      {t('ddMarkedComplete')}
                    </div>
                    <button
                      type="button"
                      onClick={() => openChat(quest)}
                      className="text-sm bg-white border border-gray-200 text-gray-700 px-3 py-1.5 rounded-md hover:bg-gray-50 transition font-medium"
                    >
                      💬 {t('ddSupplementLog')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {historyQuests.length > 0 && (
          <div className="max-w-2xl mx-auto w-full px-4 pb-8">
            <h2 className="text-base font-semibold text-slate-600 mb-4">🕰️ {t('ddHistorySection')}</h2>
            <div className="space-y-2">
              {historyQuests.map((item) => (
                <div
                  key={item.quest?.quest_id || item.last_review}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0'
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 500, color: '#334155' }}>{item.quest?.label || item.quest?.quest_id}</span>
                    <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '8px' }}>{item.last_review}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => openChat(item.quest)}
                    style={{
                      fontSize: '12px',
                      padding: '4px 10px',
                      backgroundColor: '#e0e7ff',
                      color: '#4338ca',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer'
                    }}
                  >
                    💬 {t('ddViewLog')}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {currentChatQuest && (
          <QuestTopicChatModal
            quest={currentChatQuest}
            childName={childName}
            childId={childId}
            onClose={closeChat}
          />
        )}
      </div>
    );
  }

  if (pending.length === 0 && completedToday.length === 0) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center p-4">
        <div className="max-w-2xl w-full mb-6">{renderSurveySection()}</div>
        <div className="text-slate-600 text-lg">{t('ddNoTasksToday')}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-slate-800">
              {deckHeadline}
            </h1>
            {weakestDomainInfo && (
              <p className="text-sm text-amber-700 mt-1">
                🚨 {t('ddWeakestDomain').replace('{domain}', weakestDomainInfo.domain_name)}
              </p>
            )}
            <p className="text-sm text-slate-500 mt-1">
              {t('ddProgress').replace('{done}', String(completedCount)).replace('{total}', String(totalCount))}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600">{t('ddTaskCountLabel')}</label>
            <select
              value={questCount}
              onChange={(e) => setQuestCount(Number(e.target.value))}
              className="text-sm border border-slate-300 rounded-lg px-2 py-1"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{`${n} ${t('ddTasksUnit')}`}</option>
              ))}
            </select>
            <button
              onClick={fetchDailyQuests}
              className="text-sm px-3 py-1 bg-slate-200 hover:bg-slate-300 rounded-lg"
            >
              {t('ddRefresh')}
            </button>
            {showDemoButton && scheduleSource === 'qcq' ? (
              <button
                type="button"
                onClick={() => {
                  setPending([DEMO_MOCK_DATA]);
                  setCompletedToday([]);
                }}
                className="text-sm px-4 py-1.5 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg font-bold shadow-md transition-all ml-2"
              >
                ✨ {t('ddLoadDemo')}
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-4 bg-white">
        <div className="max-w-2xl mx-auto space-y-8">
          {/* 今日待完成 */}
          {pending.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-700 mb-4 flex items-center gap-2">
                📌 {t('ddPendingSection')}
              </h2>
              {renderSurveySection()}
              <div className="space-y-4">
                {pending.map((quest) => (
                  <ExpandableQuestCard
                    submitting={submitting}
                    onRecordFeedback={recordFeedback}
                    onOpenChat={openChat}
                    key={quest.quest_id}
                    quest={quest}
                    isCompleted={false}
                    showButtons={true}
                  />
                ))}
              </div>
            </section>
          )}

          {pending.length === 0 && renderSurveySection()}

          {/* 今日已打卡 */}
          {completedToday.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-600 mb-4 flex items-center gap-2">
                ✅ {t('ddCompletedSectionHeader')}
              </h2>
              <div className="space-y-4">
                {completedToday.map((quest) => (
                  <ExpandableQuestCard
                    submitting={submitting}
                    onRecordFeedback={recordFeedback}
                    onOpenChat={openChat}
                    key={quest.quest_id}
                    quest={quest}
                    isCompleted={true}
                    showButtons={false}
                  />
                ))}
              </div>
            </section>
          )}

          {/* 历史干预记录 */}
          {historyQuests.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-slate-600 mb-4 flex items-center gap-2">
                🕰️ {t('ddHistorySection')}
              </h2>
              <div className="space-y-2">
                {historyQuests.map((item) => (
                  <div
                    key={item.quest?.quest_id || item.last_review}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0'
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 500, color: '#334155' }}>{item.quest?.label || item.quest?.quest_id}</span>
                      <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '8px' }}>{item.last_review}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => openChat(item.quest)}
                      style={{
                        fontSize: '12px',
                        padding: '4px 10px',
                        backgroundColor: '#e0e7ff',
                        color: '#4338ca',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer'
                      }}
                    >
                      💬 {t('ddViewLog')}
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>

      {currentChatQuest && (
        <QuestTopicChatModal
          quest={currentChatQuest}
          childName={childName}
          childId={childId}
          onClose={closeChat}
        />
      )}
    </div>
  );
}

export default DailyDeck;
