import React, { useState, useEffect } from 'react';
import axios from 'axios';
import BaseWidget from './BaseWidget';
import theme from '../../styles/theme';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Logic City Gallery Component
 * Displays vocabulary items tagged with "Logic City" theme in a responsive grid layout.
 */
const LogicCityGallery = () => {
  const [vocabulary, setVocabulary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const pageSize = 50;

  useEffect(() => {
    const fetchVocabulary = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await axios.get(`${API_BASE}/literacy/logic-city`, {
          params: { page, page_size: pageSize }
        });
        const newItems = response.data || [];
        setVocabulary(newItems);
        setHasMore(newItems.length === pageSize); // If we got a full page, there might be more
      } catch (err) {
        console.error('Error fetching Logic City vocabulary:', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load vocabulary');
      } finally {
        setLoading(false);
      }
    };

    fetchVocabulary();
  }, [page]);

  const handleImageError = (e) => {
    // Prevent infinite loop - if we've already tried to hide it, stop
    if (e.target.dataset.errorHandled === 'true') {
      return;
    }
    e.target.dataset.errorHandled = 'true';
    
    // Hide the broken image
    e.target.style.display = 'none';
    
    // Show fallback
    const container = e.target.parentElement;
    const fallback = container?.querySelector('.image-fallback');
    if (fallback) {
      fallback.style.display = 'flex';
    }
  };

  return (
    <BaseWidget
      title="Logic City Vocabulary"
      category="logic"
      loading={loading}
      error={error}
    >
      {vocabulary.length === 0 && !loading && !error ? (
        <div style={{ textAlign: 'center', padding: theme.spacing.xl, color: theme.ui.text.secondary }}>
          No vocabulary items found. Make sure the knowledge graph is loaded and tagged correctly.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: theme.spacing.md,
            padding: theme.spacing.sm
          }}
        >
          {vocabulary.map((item, index) => (
            <div
              key={index}
              style={{
                backgroundColor: theme.ui.surface,
                borderRadius: theme.borderRadius.md,
                padding: theme.spacing.md,
                boxShadow: theme.shadows.sm,
                transition: 'transform 0.2s, box-shadow 0.2s',
                cursor: 'pointer',
                border: `1px solid ${theme.ui.border}`
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)';
                e.currentTarget.style.boxShadow = theme.shadows.md;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = theme.shadows.sm;
              }}
            >
              {/* Image */}
              <div
                style={{
                  width: '100%',
                  height: '150px',
                  backgroundColor: theme.ui.background,
                  borderRadius: theme.borderRadius.sm,
                  marginBottom: theme.spacing.sm,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                  position: 'relative'
                }}
              >
                {item.image_path ? (
                  <>
                    <img
                      src={`${API_BASE}${item.image_path}`}
                      alt={item.english}
                      onError={handleImageError}
                      onLoad={(e) => {
                        // Hide fallback when image loads successfully
                        const fallback = e.target.parentElement.querySelector('.image-fallback');
                        if (fallback) fallback.style.display = 'none';
                        e.target.style.display = 'block';
                      }}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        display: 'block'
                      }}
                    />
                    {/* Fallback shown when image fails - initially hidden */}
                    <div
                      className="image-fallback"
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        display: 'none',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: theme.ui.text.secondary,
                        fontSize: '48px',
                        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
                      }}
                    >
                      📷
                    </div>
                  </>
                ) : (
                  <div
                    style={{
                      color: theme.ui.text.secondary,
                      fontSize: '48px',
                      textAlign: 'center',
                      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    📷
                  </div>
                )}
              </div>

              {/* English Word (Bold) */}
              <div
                style={{
                  fontWeight: 'bold',
                  fontSize: '16px',
                  color: theme.ui.text.primary,
                  marginBottom: theme.spacing.xs,
                  textAlign: 'center'
                }}
              >
                {item.english}
              </div>

              {/* Chinese and Pinyin (Subtext) */}
              {(item.chinese || item.pinyin) && (
                <div
                  style={{
                    fontSize: '14px',
                    color: theme.ui.text.secondary,
                    textAlign: 'center',
                    lineHeight: '1.4'
                  }}
                >
                  {item.chinese && (
                    <div style={{ marginBottom: item.pinyin ? '4px' : '0' }}>
                      {item.chinese}
                    </div>
                  )}
                  {item.pinyin && (
                    <div style={{ fontStyle: 'italic', opacity: 0.8 }}>
                      {item.pinyin}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {/* Pagination Controls */}
      {vocabulary.length > 0 && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: theme.spacing.md,
          marginTop: theme.spacing.lg,
          paddingTop: theme.spacing.md,
          borderTop: `1px solid ${theme.ui.border}`
        }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '8px 16px',
              backgroundColor: page === 1 ? theme.ui.background : theme.categories.language.primary,
              color: page === 1 ? theme.ui.text.secondary : 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: page === 1 ? 'not-allowed' : 'pointer',
              opacity: page === 1 ? 0.5 : 1
            }}
          >
            ← Previous
          </button>
          <span style={{ color: theme.ui.text.secondary }}>
            Page {page}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!hasMore}
            style={{
              padding: '8px 16px',
              backgroundColor: !hasMore ? theme.ui.background : theme.categories.language.primary,
              color: !hasMore ? theme.ui.text.secondary : 'white',
              border: 'none',
              borderRadius: theme.borderRadius.md,
              cursor: !hasMore ? 'not-allowed' : 'pointer',
              opacity: !hasMore ? 0.5 : 1
            }}
          >
            Next →
          </button>
        </div>
      )}
    </BaseWidget>
  );
};

export default LogicCityGallery;

