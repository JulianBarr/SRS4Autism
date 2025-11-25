/**
 * Consistent color coding scheme for UI
 * Based on Material Design color palette
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
  
  // Action Colors (for buttons and interactive elements)
  actions: {
    primary: '#1976d2',      // Blue - Main actions (Send, Sync, Generate)
    success: '#4CAF50',      // Green - Positive actions (Approve, Save, Add)
    danger: '#F44336',       // Red - Destructive actions (Delete, Remove)
    warning: '#FF9800',      // Orange - Caution actions
    secondary: '#757575',    // Gray - Secondary actions (Edit, Cancel, Clear)
    info: '#2196F3'          // Cyan - Informational actions
  },
  
  // Status Colors
  status: {
    // Learning Status
    mastered: '#4CAF50',           // Green - Item is mastered
    inProgress: '#FFC107',          // Yellow - Currently learning
    notStarted: '#9E9E9E',          // Gray - Not yet started
    recommended: '#2196F3',          // Blue - Recommended for learning
    alreadyMastered: '#FF9800',      // Orange - Warning: already mastered
    
    // Card Status
    pending: '#FF9800',              // Orange - Card is pending approval
    approved: '#4CAF50',             // Green - Card is approved
    synced: '#2196F3',               // Blue - Card is synced to Anki
    
    // System Status
    error: '#F44336',                // Red - Error state
    warning: '#FF9800',              // Orange - Warning state
    info: '#2196F3',                 // Blue - Info state
    success: '#4CAF50'               // Green - Success state
  },
  
  // UI Colors
  ui: {
    background: '#FFFFFF',
    surface: '#F5F5F5',
    border: '#E0E0E0',
    divider: '#E0E0E0',
    
    // Text Colors
    text: {
      primary: '#212121',            // Main text (almost black)
      secondary: '#757575',          // Secondary text (gray)
      disabled: '#BDBDBD',           // Disabled text (light gray)
      hint: '#9E9E9E',               // Hint text (very light gray)
      inverse: '#FFFFFF'             // Text on dark backgrounds
    },
    
    // Background Colors
    backgrounds: {
      default: '#FFFFFF',
      surface: '#F5F5F5',
      hover: '#FAFAFA',
      selected: '#E3F2FD',            // Light blue for selected items
      disabled: '#F5F5F5'
    }
  },
  
  // Status Background Colors (for badges and tags)
  statusBackgrounds: {
    pending: '#FFF3E0',              // Light orange
    approved: '#E8F5E9',              // Light green
    synced: '#E3F2FD',                // Light blue
    error: '#FFEBEE',                 // Light red
    warning: '#FFF3E0',               // Light orange
    info: '#E0F7FA',                  // Light cyan
    success: '#E8F5E9'                 // Light green
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
    xl: '16px',
    round: '50%'
  },
  
  // Shadows
  shadows: {
    sm: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)',
    md: '0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23)',
    lg: '0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.23)'
  },
  
  // Button Styles (predefined combinations)
  buttons: {
    primary: {
      backgroundColor: '#1976d2',
      color: '#FFFFFF',
      hover: '#1565C0',
      active: '#0D47A1'
    },
    success: {
      backgroundColor: '#4CAF50',
      color: '#FFFFFF',
      hover: '#45A049',
      active: '#2E7D32'
    },
    danger: {
      backgroundColor: '#F44336',
      color: '#FFFFFF',
      hover: '#E53935',
      active: '#C62828'
    },
    warning: {
      backgroundColor: '#FF9800',
      color: '#FFFFFF',
      hover: '#FB8C00',
      active: '#E65100'
    },
    secondary: {
      backgroundColor: '#757575',
      color: '#FFFFFF',
      hover: '#616161',
      active: '#424242'
    },
    outline: {
      backgroundColor: 'transparent',
      color: '#1976d2',
      border: '1px solid #1976d2',
      hover: '#E3F2FD'
    }
  }
};

export default theme;
