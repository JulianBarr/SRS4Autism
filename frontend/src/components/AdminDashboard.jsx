import React, { useState, useEffect } from 'react';
import { cloudApi } from '../utils/api';

function AdminDashboard() {
  const [teachers, setTeachers] = useState([]);
  const [pendingTeachers, setPendingTeachers] = useState([]);
  const [children, setChildren] = useState([]);
  const [selectedTeacher, setSelectedTeacher] = useState('');
  const [selectedChild, setSelectedChild] = useState('');
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [message, setMessage] = useState({ text: '', type: '' });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Parallel requests for teachers, pending teachers, and children
      const [teachersRes, pendingRes, childrenRes] = await Promise.all([
        cloudApi.get('/api/v1/admin/teachers'),
        cloudApi.get('/api/v1/admin/pending_teachers'),
        cloudApi.get('/api/v1/admin/children')
      ]);

      setTeachers(teachersRes.data);
      setPendingTeachers(pendingRes.data);
      setChildren(childrenRes.data);
    } catch (err) {
      console.error("Error fetching admin data:", err);
      setMessage({ 
        text: err.response?.data?.detail || "无法加载数据，请确保您拥有管理员权限。", 
        type: 'error' 
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (userId) => {
    try {
      await cloudApi.post(`/api/v1/admin/teachers/${userId}/approve`);
      setMessage({ text: "✅ 教师审批通过", type: 'success' });
      fetchData(); // Refresh the lists
    } catch (err) {
      console.error("Error approving teacher:", err);
      setMessage({ text: "❌ 审批通过失败", type: 'error' });
    }
  };

  const handleReject = async (userId) => {
    try {
      await cloudApi.post(`/api/v1/admin/teachers/${userId}/reject`);
      setMessage({ text: "✅ 教师审批已拒绝", type: 'success' });
      fetchData(); // Refresh the lists
    } catch (err) {
      console.error("Error rejecting teacher:", err);
      setMessage({ text: "❌ 拒绝审批失败", type: 'error' });
    }
  };

  const handleAssign = async () => {
    if (!selectedTeacher || !selectedChild) {
      setMessage({ text: "请先选择一位特教老师和一位目标儿童", type: 'warning' });
      return;
    }

    setAssigning(true);
    setMessage({ text: '', type: '' });

    try {
      const response = await cloudApi.post(
        '/api/v1/admin/assign',
        { 
          user_id: parseInt(selectedTeacher, 10), 
          child_id: selectedChild 
        }
      );

      setMessage({ text: "✅ " + (response.data.message || "分配成功"), type: 'success' });
      
      // Optionally reset selections
      // setSelectedTeacher('');
      // setSelectedChild('');
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        setMessage({ text: '', type: '' });
      }, 3000);
      
    } catch (err) {
      console.error("Error assigning teacher:", err);
      setMessage({ 
        text: err.response?.data?.detail || "分配失败，请稍后重试", 
        type: 'error' 
      });
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="admin-dashboard-container min-h-screen bg-slate-50 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-slate-800">CUMA 机构授权控制台</h1>
          <p className="text-slate-500 mt-2">将特教老师分配给对应的儿童，闭环多租户系统权限。</p>
        </header>

        {/* Main Card */}
        <div className="bg-white rounded-xl shadow-sm p-8 border border-slate-100">
          {loading ? (
            <div className="flex justify-center items-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-500"></div>
              <span className="ml-3 text-slate-500">加载数据中...</span>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Message Banner */}
              {message.text && (
                <div className={`p-4 rounded-lg text-sm ${
                  message.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                  message.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                  'bg-amber-50 text-amber-700 border border-amber-200'
                }`}>
                  {message.text}
                </div>
              )}

              {/* Pending Teachers Section */}
              {pendingTeachers.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 mb-8">
                  <h2 className="text-xl font-bold text-amber-800 mb-4 flex items-center">
                    <span className="mr-2">⏳</span> 待审批教师
                  </h2>
                  <div className="space-y-4">
                    {pendingTeachers.map((t) => (
                      <div key={t.id} className="flex items-center justify-between bg-white p-4 rounded-lg shadow-sm border border-amber-100">
                        <div>
                          <p className="font-medium text-slate-800">{t.name}</p>
                          <p className="text-sm text-slate-500">{t.username}</p>
                        </div>
                        <div className="flex space-x-3">
                          <button
                            onClick={() => handleApprove(t.id)}
                            className="px-4 py-2 bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors font-medium text-sm flex items-center"
                          >
                            ✅ 通过
                          </button>
                          <button
                            onClick={() => handleReject(t.id)}
                            className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors font-medium text-sm flex items-center"
                          >
                            ❌ 拒绝
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Selection Area */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Teacher Select */}
                <div className="flex flex-col space-y-2">
                  <label htmlFor="teacher-select" className="font-medium text-slate-700">
                    选择特教老师
                  </label>
                  <select
                    id="teacher-select"
                    value={selectedTeacher}
                    onChange={(e) => setSelectedTeacher(e.target.value)}
                    className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-slate-700"
                  >
                    <option value="">-- 请选择老师 --</option>
                    {teachers.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.username})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Child Select */}
                <div className="flex flex-col space-y-2">
                  <label htmlFor="child-select" className="font-medium text-slate-700">
                    选择目标儿童
                  </label>
                  <select
                    id="child-select"
                    value={selectedChild}
                    onChange={(e) => setSelectedChild(e.target.value)}
                    className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-slate-700"
                  >
                    <option value="">-- 请选择儿童 --</option>
                    {children.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-6 mt-6 border-t border-slate-100 flex justify-end">
                <button
                  onClick={handleAssign}
                  disabled={assigning || !selectedTeacher || !selectedChild}
                  className={`px-6 py-3 rounded-lg font-medium transition-all shadow-sm flex items-center
                    ${(assigning || !selectedTeacher || !selectedChild)
                      ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-md active:bg-blue-800'
                    }`}
                >
                  {assigning ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      分配中...
                    </>
                  ) : (
                    '确认分配'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
