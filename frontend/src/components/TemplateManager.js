import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TemplateManager = () => {
  const { t } = useLanguage();
  const [templates, setTemplates] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    template_text: ''
  });

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await axios.get(`${API_BASE}/templates`);
      setTemplates(response.data);
    } catch (error) {
      console.error('Error loading templates:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const templateData = {
        id: editingTemplate || Date.now().toString(),
        name: formData.name,
        description: formData.description,
        template_text: formData.template_text,
        created_at: new Date().toISOString(),
        updated_at: editingTemplate ? new Date().toISOString() : null
      };

      if (editingTemplate) {
        await axios.put(`${API_BASE}/templates/${editingTemplate}`, templateData);
      } else {
        await axios.post(`${API_BASE}/templates`, templateData);
      }

      loadTemplates();
      handleCancel();
    } catch (error) {
      console.error('Error saving template:', error);
      alert(t('failedToSaveTemplate'));
    }
  };

  const handleEdit = (template) => {
    setFormData({
      name: template.name,
      description: template.description,
      template_text: template.template_text
    });
    setEditingTemplate(template.id);
    setShowForm(true);
  };

  const handleDelete = async (templateId) => {
    if (window.confirm(t('areYouSureDeleteTemplate'))) {
      try {
        await axios.delete(`${API_BASE}/templates/${templateId}`);
        loadTemplates();
      } catch (error) {
        console.error('Error deleting template:', error);
      }
    }
  };

  const handleCancel = () => {
    setFormData({ name: '', description: '', template_text: '' });
    setShowForm(false);
    setEditingTemplate(null);
  };

  return (
    <div className="card">
      <h2>{t('promptTemplates')}</h2>
      <p>{t('promptTemplatesDescription')}</p>

      <div className="profiles-header">
        <button onClick={() => setShowForm(true)} className="btn">
          {t('addNewTemplate')}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h3>{editingTemplate ? t('editTemplate') : t('addNewTemplate')}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>{t('templateName')} *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder={t('templateNamePlaceholder')}
                required
              />
            </div>

            <div className="form-group">
              <label>{t('templateDescription')}</label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                placeholder={t('templateDescriptionPlaceholder')}
              />
            </div>

            <div className="form-group">
              <label>{t('templateInstructions')} *</label>
              <textarea
                value={formData.template_text}
                onChange={(e) => setFormData({...formData, template_text: e.target.value})}
                rows="10"
                placeholder={t('templateInstructionsPlaceholder')}
                required
              />
              <small style={{color: '#666', fontSize: '12px'}}>
                {t('templateInstructionsHint')}
              </small>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn">
                {editingTemplate ? t('updateTemplate') : t('createTemplate')}
              </button>
              <button type="button" onClick={handleCancel} className="btn btn-secondary">
                {t('cancel')}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="profiles-list">
        {templates.length === 0 ? (
          <p>{t('noTemplatesYet')}</p>
        ) : (
          templates.map(template => (
            <div key={template.id} className="profile-card">
              <div className="profile-header">
                <h3>{template.name}</h3>
                <div className="profile-actions">
                  <button onClick={() => handleEdit(template)} className="btn btn-secondary">
                    {t('edit')}
                  </button>
                  <button onClick={() => handleDelete(template.id)} className="btn btn-secondary">
                    {t('delete')}
                  </button>
                </div>
              </div>
              <div className="profile-details">
                {template.description && (
                  <div className="detail-row">
                    <strong>{t('templateDescription')}:</strong> {template.description}
                  </div>
                )}
                <div className="detail-row template-preview">
                  <strong>{t('templateInstructions')}:</strong>
                  <pre>{template.template_text}</pre>
                </div>
                <div className="detail-row">
                  <strong>{t('templateUsage')}:</strong> 
                  <code>@template:{template.name.replace(/\s+/g, '_')}</code>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TemplateManager;

