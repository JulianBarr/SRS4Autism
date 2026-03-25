import React, { useState, useEffect } from 'react';
import businessApi from '../utils/api';
import DailyDeck from './DailyDeck';

const ParentDashboard = ({ currentUser }) => {
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProfiles = async () => {
      try {
        setLoading(true);
        const response = await businessApi.get('/profiles');
        setProfiles(response.data);
      } catch (err) {
        setError('Failed to load profiles.');
        console.error('Error fetching profiles:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProfiles();
  }, [currentUser]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-xl text-gray-700">Loading training babies...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-red-50">
        <p className="text-xl text-red-700">Error: {error}</p>
      </div>
    );
  }

  if (selectedProfile) {
    return (
      <div className="min-h-screen bg-gray-50 p-4">
        <div className="flex justify-between items-center mb-6">
          <button 
            onClick={() => setSelectedProfile(null)}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-75"
          >
            <span className="text-xl mr-2">⬅️</span> 切换宝贝
          </button>
          <h2 className="text-3xl font-extrabold text-gray-900">{selectedProfile.name} 的今日任务</h2>
          <div></div> {/* Placeholder for right alignment */}
        </div>
        <DailyDeck profileId={selectedProfile.id} />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-purple-100 to-pink-100 p-8">
      <h1 className="text-5xl font-extrabold text-gray-900 mb-12 drop-shadow-lg">请选择今天的训练宝贝</h1>

      <div className="flex flex-wrap justify-center gap-10">
        {profiles.length > 0 ? (
          profiles.map((profile) => (
            <div
              key={profile.id}
              onClick={() => setSelectedProfile(profile)}
              className="relative w-64 h-80 bg-white rounded-3xl shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-105 cursor-pointer overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-b from-purple-400 to-pink-500 opacity-70 group-hover:opacity-80 transition-opacity duration-300"></div>
              <img 
                src={profile.avatar || 'https://via.placeholder.com/150'} 
                alt={profile.name}
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[calc(50%+20px)] w-40 h-40 rounded-full object-cover border-4 border-white shadow-md group-hover:border-indigo-200 transition-all duration-300"
              />
              <div className="absolute bottom-0 left-0 right-0 p-6 text-center bg-white bg-opacity-90 backdrop-blur-sm rounded-b-3xl">
                <h3 className="text-3xl font-bold text-gray-900 group-hover:text-indigo-600 transition-colors duration-300">{profile.name}</h3>
                <p className="text-lg text-gray-600 mt-2">{profile.age ? `${profile.age} 岁` : '暂无年龄信息'}</p>
                {profile.description && <p className="text-sm text-gray-500 mt-1 truncate">{profile.description}</p>}
              </div>
            </div>
          ))
        ) : (
          <p className="text-2xl text-gray-700">暂无儿童档案，请联系管理员添加。</p>
        )}
      </div>
    </div>
  );
};

export default ParentDashboard;
