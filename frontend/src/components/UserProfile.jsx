import React, { useState, useEffect } from 'react';
import { cloudApi } from '../utils/api';

function UserProfile({ currentUser, onUserUpdate }) {
  const [institutions, setInstitutions] = useState([]);
  const [selectedInst, setSelectedInst] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchInstitutions();
  }, []);

  const fetchInstitutions = async () => {
    setLoading(true);
    try {
      const res = await cloudApi.get('/api/v1/institutions');
      setInstitutions(res.data);
    } catch (err) {
      console.error('Error fetching institutions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!selectedInst) return;
    setSubmitting(true);
    setMessage('');
    try {
      const res = await cloudApi.post('/api/v1/users/me/institution', {
        institution_id: parseInt(selectedInst, 10)
      });
      setMessage(res.data.message || '申请已提交');
      
      // Update local user state
      if (onUserUpdate) {
        const updatedUser = {
          ...currentUser,
          institution_id: parseInt(selectedInst, 10),
          institution_status: 'PENDING'
        };
        onUserUpdate(updatedUser);
        localStorage.setItem('user_info', JSON.stringify(updatedUser));
      }
    } catch (err) {
      console.error('Error applying to institution:', err);
      setMessage(err.response?.data?.detail || '申请失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!currentUser) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm p-8 border border-slate-100 max-w-2xl mx-auto my-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">个人设置</h2>
      
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-slate-600 mb-1">账号</label>
          <div className="text-slate-800 p-3 bg-slate-50 rounded-lg">{currentUser.email}</div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-slate-600 mb-1">角色</label>
          <div className="text-slate-800 p-3 bg-slate-50 rounded-lg">
            {currentUser.role === 'teacher' ? '教师' : 
             currentUser.role === 'qcq_admin' ? '机构管理员' : 
             currentUser.role === 'parent' ? '家长' : currentUser.role}
          </div>
        </div>

        <div className="border-t border-slate-100 pt-6">
          <h3 className="text-lg font-semibold text-slate-800 mb-4">我的机构</h3>
          
          {currentUser.institution_status === 'APPROVED' ? (
            <div className="p-4 bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-200 flex items-center">
              <span className="mr-2">✅</span> 
              已加入：{institutions.find(i => i.id === currentUser.institution_id)?.name || `机构 ID: ${currentUser.institution_id}`}
            </div>
          ) : currentUser.institution_status === 'PENDING' ? (
            <div className="p-4 bg-slate-50 text-slate-500 rounded-lg border border-slate-200 flex items-center">
              <span className="mr-2">⏳</span> 机构审批中...
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex space-x-4">
                <select
                  value={selectedInst}
                  onChange={(e) => setSelectedInst(e.target.value)}
                  className="flex-1 p-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-slate-700"
                  disabled={loading || submitting}
                >
                  <option value="">-- 请选择机构 --</option>
                  {institutions.map(inst => (
                    <option key={inst.id} value={inst.id}>{inst.name}</option>
                  ))}
                </select>
                <button
                  onClick={handleApply}
                  disabled={!selectedInst || submitting}
                  className={`px-6 py-3 rounded-lg font-medium transition-all ${
                    !selectedInst || submitting 
                      ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {submitting ? '提交中...' : '申请加入'}
                </button>
              </div>
              {message && (
                <div className={`text-sm ${message.includes('失败') ? 'text-red-600' : 'text-emerald-600'}`}>
                  {message}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default UserProfile;
