import React, { useState, useEffect } from 'react';
import businessApi from '../utils/api';
import theme from '../styles/theme';

const HHHContentManager = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState({});

  useEffect(() => {
    const fetchHHHLanguage = async () => {
      try {
        setLoading(true);
        const res = await businessApi.get('/kg/hhh/language');
        setData(res.data.data);
      } catch (err) {
        console.error('Failed to fetch HHH language curriculum:', err);
        setError(err.message || 'Error fetching data');
      } finally {
        setLoading(false);
      }
    };
    fetchHHHLanguage();
  }, []);

  const toggleNode = (nodeId) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [nodeId]: !prev[nodeId],
    }));
  };

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading HHH Curriculum...</div>;
  }

  if (error) {
    return <div style={{ padding: '20px', color: 'red', textAlign: 'center' }}>{error}</div>;
  }

  if (!data || Object.keys(data).length === 0) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>No HHH data found.</div>;
  }

  const renderTree = (nodeData, path = '', level = 0) => {
    if (Array.isArray(nodeData)) {
      // It's a list of targets
      return (
        <ul style={{ paddingLeft: '20px', listStyleType: 'disc', margin: '4px 0' }}>
          {nodeData.map((target, idx) => (
            <li key={idx} style={{ color: theme.ui.text.secondary, marginBottom: '4px' }}>
              {target}
            </li>
          ))}
        </ul>
      );
    }

    // It's an object (Age, Module, Submodule, Focus, or Item)
    return (
      <div style={{ marginLeft: level > 0 ? '20px' : '0' }}>
        {Object.entries(nodeData).map(([key, value]) => {
          const currentPath = `${path}/${key}`;
          const isExpanded = expandedNodes[currentPath] || level < 1; // expand top level by default

          return (
            <div key={key} style={{ marginBottom: '8px' }}>
              <div 
                onClick={() => toggleNode(currentPath)}
                style={{ 
                  cursor: 'pointer', 
                  padding: '6px 8px',
                  backgroundColor: level === 0 ? '#eff6ff' : 'transparent',
                  borderRadius: '4px',
                  fontWeight: level < 3 ? 'bold' : 'normal',
                  color: level === 0 ? '#1d4ed8' : '#374151',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <span style={{ 
                  display: 'inline-block', 
                  width: '16px', 
                  marginRight: '8px',
                  fontSize: '12px',
                  color: '#9ca3af'
                }}>
                  {Object.keys(value).length > 0 ? (isExpanded ? '▼' : '▶') : '•'}
                </span>
                {key}
              </div>
              
              {isExpanded && value && (
                <div style={{ paddingLeft: '8px', borderLeft: '1px solid #e5e7eb', marginLeft: '12px', marginTop: '4px' }}>
                  {renderTree(value, currentPath, level + 1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <h2 style={{ color: '#1e3a8a', marginBottom: '20px', borderBottom: '2px solid #eff6ff', paddingBottom: '10px' }}>
        🏫 协康会 (HHH) 语言干预课程
      </h2>
      <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
        {renderTree(data)}
      </div>
    </div>
  );
};

export default HHHContentManager;
