import React from 'react';
import theme from '../../styles/theme';

/**
 * Base Widget Component
 * Provides consistent styling and structure for all widgets
 */
const BaseWidget = ({ 
  title, 
  category = 'language', 
  children, 
  actions,
  loading = false,
  error = null,
  className = '',
  style = {}
}) => {
  const categoryColors = theme.categories[category] || theme.categories.language;
  
  return (
    <div
      className={`base-widget ${className}`}
      style={{
        backgroundColor: theme.ui.background,
        border: `2px solid ${categoryColors.primary}`,
        borderRadius: theme.borderRadius.lg,
        padding: theme.spacing.lg,
        marginBottom: theme.spacing.md,
        boxShadow: theme.shadows.md,
        ...style
      }}
    >
      {/* Widget Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: theme.spacing.md,
          paddingBottom: theme.spacing.sm,
          borderBottom: `2px solid ${categoryColors.background}`
        }}
      >
        <h3
          style={{
            margin: 0,
            color: categoryColors.primary,
            fontSize: '18px',
            fontWeight: '600'
          }}
        >
          {title}
        </h3>
        {actions && (
          <div style={{ display: 'flex', gap: theme.spacing.sm }}>
            {actions}
          </div>
        )}
      </div>
      
      {/* Widget Content */}
      {error ? (
        <div
          style={{
            padding: theme.spacing.md,
            backgroundColor: theme.status.error + '20',
            color: theme.status.error,
            borderRadius: theme.borderRadius.md,
            textAlign: 'center'
          }}
        >
          {error}
        </div>
      ) : loading ? (
        <div
          style={{
            padding: theme.spacing.xl,
            textAlign: 'center',
            color: theme.ui.text.secondary
          }}
        >
          Loading...
        </div>
      ) : (
        <div>{children}</div>
      )}
    </div>
  );
};

export default BaseWidget;


