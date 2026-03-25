import React from 'react';
import DailyDeck from './DailyDeck';

const ParentDashboard = ({ currentUser, currentProfile }) => {
  if (!currentProfile) {
    return (
      <div className="flex flex-col items-center justify-center p-8 min-h-[60vh]">
        <div className="animate-pulse">
          <p className="text-xl text-gray-500">正在加载儿童档案...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden min-h-[80vh]">
      <DailyDeck 
        profileId={currentProfile.id} 
        childName={currentProfile.name} 
        childId={currentProfile.id} 
      />
    </div>
  );
};

export default ParentDashboard;
