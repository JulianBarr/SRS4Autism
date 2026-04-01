export const sourceLabelMap = {
  'HHH': {
    stealthLabel: 'System-B',
    internalLabel: '协康会'
  },
  'QCQ': {
    stealthLabel: 'System-A',
    internalLabel: '奇思妙语'
  },
};

export const getDisplayLabel = (internalLabel, sourceId, stealthMode) => {
  if (stealthMode) {
    if (sourceId && sourceLabelMap[sourceId]) {
      return sourceLabelMap[sourceId].stealthLabel;
    } else if (internalLabel === '认知') { // Specific mapping for generic 'Cognition' label
      return '通用认知';
    }
    return internalLabel; // Fallback for other labels
  } else {
    if (sourceId && sourceLabelMap[sourceId]) {
      return sourceLabelMap[sourceId].internalLabel;
    }
    return internalLabel;
  }
};

export const getDisplaySourceId = (sourceId, stealthMode) => {
  if (stealthMode && sourceId === 'HHH') {
    return 'SYS-02';
  }
  return sourceId;
};
