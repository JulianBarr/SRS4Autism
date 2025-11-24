/**
 * Consistent color coding scheme for UI
 */

export const theme = {
  // Category Colors
  categories: {
    language: {
      primary: '#1976d2',
      light: '#64B5F6',
      dark: '#0D47A1',
      background: '#E3F2FD'
    },
    math: {
      primary: '#4CAF50',
      light: '#81C784',
      dark: '#2E7D32',
      background: '#E8F5E9'
    },
    knowledge: {
      primary: '#FF9800',
      light: '#FFB74D',
      dark: '#E65100',
      background: '#FFF3E0'
    },
    culture: {
      primary: '#9C27B0',
      light: '#BA68C8',
      dark: '#6A1B9A',
      background: '#F3E5F5'
    }
  },
  
  // Status Colors
  status: {
    mastered: '#4CAF50',
    inProgress: '#FFC107',
    notStarted: '#9E9E9E',
    recommended: '#2196F3',
    error: '#F44336',
    warning: '#FF9800',
    info: '#2196F3',
    success: '#4CAF50'
  },
  
  // UI Colors
  ui: {
    background: '#FFFFFF',
    surface: '#F5F5F5',
    border: '#E0E0E0',
    text: {
      primary: '#212121',
      secondary: '#757575',
      disabled: '#BDBDBD',
      hint: '#9E9E9E'
    }
  },
  
  // Spacing
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px'
  },
  
  // Border Radius
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px'
  },
  
  // Shadows
  shadows: {
    sm: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)',
    md: '0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23)',
    lg: '0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.23)'
  }
};

export default theme;

