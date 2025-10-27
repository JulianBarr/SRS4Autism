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
      alert('Failed to save template');
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
    if (window.confirm('Are you sure you want to delete this template?')) {
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
      <h2>Prompt Templates</h2>
      <p>Define custom templates to guide the AI in generating specific types of flashcards.</p>

      <div className="profiles-header">
        <button onClick={() => setShowForm(true)} className="btn">
          Add New Template
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h3>{editingTemplate ? 'Edit Template' : 'Add New Template'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Template Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder="e.g., Sentence Builder, Vocabulary with Examples"
                required
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                placeholder="Brief description of what this template does"
              />
            </div>

            <div className="form-group">
              <label>Template Instructions *</label>
              <textarea
                value={formData.template_text}
                onChange={(e) => setFormData({...formData, template_text: e.target.value})}
                rows="10"
                placeholder={`Free-form instructions and examples for the AI:

Example:
Create interactive cloze cards for sentence practice.

Format:
- Use [[c1::word]] syntax for blanks
- Include Chinese translation in parentheses
- Add pinyin for Chinese words

Example card:
The [[c1::sky]] is [[c2::blue]]. 天空 (tiānkōng) 是蓝色的。

Make cards engaging and age-appropriate.`}
                required
              />
              <small style={{color: '#666', fontSize: '12px'}}>
                Provide examples, format preferences, and any specific instructions for the AI.
              </small>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn">
                {editingTemplate ? 'Update Template' : 'Create Template'}
              </button>
              <button type="button" onClick={handleCancel} className="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="profiles-list">
        {templates.length === 0 ? (
          <p>No templates created yet.</p>
        ) : (
          templates.map(template => (
            <div key={template.id} className="profile-card">
              <div className="profile-header">
                <h3>{template.name}</h3>
                <div className="profile-actions">
                  <button onClick={() => handleEdit(template)} className="btn btn-secondary">
                    Edit
                  </button>
                  <button onClick={() => handleDelete(template.id)} className="btn btn-secondary">
                    Delete
                  </button>
                </div>
              </div>
              <div className="profile-details">
                {template.description && (
                  <div className="detail-row">
                    <strong>Description:</strong> {template.description}
                  </div>
                )}
                <div className="detail-row template-preview">
                  <strong>Instructions:</strong>
                  <pre>{template.template_text}</pre>
                </div>
                <div className="detail-row">
                  <strong>Usage:</strong> 
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

