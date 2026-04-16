import React, { useState } from 'react';

const TEST_SPARQL = `PREFIX cuma-schema: <http://cuma.ai/schema/>
PREFIX vbmapp-inst: <http://cuma.ai/instance/vbmapp/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?enLabel ?zhLabel ?hhsGoalLabel ?score WHERE {
  vbmapp-inst:tact_3_m rdfs:label ?enLabel .
  FILTER(LANG(?enLabel) = "en")
  OPTIONAL {
    vbmapp-inst:tact_3_m rdfs:label ?zhLabel .
    FILTER(LANG(?zhLabel) = "zh")
  }
  ?hhsGoal cuma-schema:alignsWith vbmapp-inst:tact_3_m .
  ?hhsGoal rdfs:label ?hhsGoalLabel .
  ?hhsGoal cuma-schema:matchScore ?score .
} ORDER BY DESC(?score) LIMIT 5`;

export default function GraphTest() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleQuery = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/kg/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/sparql-query; charset=utf-8',
          Accept: 'application/sparql-results+json',
        },
        body: TEST_SPARQL,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || `HTTP ${response.status}`);
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '16px', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h3 style={{ marginTop: 0 }}>Graph Test</h3>
      <button type="button" onClick={handleQuery} disabled={loading}>
        {loading ? '查询中...' : '发起 SPARQL 查询'}
      </button>

      {error && (
        <pre style={{ marginTop: '12px', color: '#b00020', whiteSpace: 'pre-wrap' }}>
          {error}
        </pre>
      )}

      {result && (
        <pre style={{ marginTop: '12px', background: '#f7f7f7', padding: '12px', overflowX: 'auto' }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
