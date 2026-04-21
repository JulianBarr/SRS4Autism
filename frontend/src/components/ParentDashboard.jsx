import React from 'react';
import ReviewInterventionWorkbench from './ReviewInterventionWorkbench';

const ParentDashboard = ({ currentUser, currentProfile }) => {
  if (!currentProfile) {
    return (
      <div className="flex items-center justify-center h-full min-h-[50vh]">
        <p className="text-gray-500 text-lg">请先在上方选择或创建一个孩子档案</p>
      </div>
    );
  }

  return (
    <ReviewInterventionWorkbench
      dailyDeckProps={{
        childName: currentProfile.name,
        childId: currentProfile.id,
      }}
    />
  );
};

export default ParentDashboard;
