import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import SearchableDropdown from './SearchableDropdown';
import RichTextEditor from './RichTextEditor';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CardImagePreview = ({ card }) => {
  const [imageData, setImageData] = useState(card?.image_data || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [requestKey, setRequestKey] = useState(0);

  const hasImageData = Boolean(card?.has_image_data);
  const isPlaceholder = card?.is_placeholder;

  React.useEffect(() => {
    setImageData(card?.image_data || null);
    setError('');
    setLoading(false);
  }, [card?.id, card?.image_data]);

  React.useEffect(() => {
    let cancelled = false;

    if (!card || !hasImageData || imageData) {
      return;
    }

    const fetchImageData = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await axios.get(`${API_BASE}/cards/${card.id}/image-data`);
        if (!cancelled) {
          setImageData(response.data?.image_data || null);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err.response?.data?.detail || 'Failed to load image';
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchImageData();

    return () => {
      cancelled = true;
    };
  }, [card?.id, hasImageData, requestKey]);

  const handleRetry = () => {
    setRequestKey((prev) => prev + 1);
  };

  if (!card) {
    return null;
  }

  const hasDescriptionOnly = !hasImageData && Boolean(card.image_description);

  if (!hasImageData && !hasDescriptionOnly) {
    return null;
  }

  const backgroundColor = isPlaceholder ? '#fff3cd' : hasImageData ? '#f8f9fa' : '#fff3cd';
  const borderColor = isPlaceholder ? '#ffeaa7' : '#dee2e6';
  const titleColor = isPlaceholder || !hasImageData ? '#856404' : '#495057';
  const titleText = isPlaceholder
    ? '🎨 Image Description (Placeholder)'
    : hasImageData
      ? '🎨 Generated Image:'
      : '🎨 Image Description:';

  return (
    <div
      className="generated-image"
      style={{
        marginTop: '15px',
        padding: '10px',
        background: backgroundColor,
        borderRadius: '8px',
        border: `1px solid ${borderColor}`
      }}
    >
      <h5 style={{ margin: '0 0 10px 0', color: titleColor }}>
        {titleText}
      </h5>

      {hasImageData && (
        <>
          {loading && (
            <div style={{ fontSize: '12px', color: '#6c757d', marginBottom: '8px' }}>
              Loading image...
            </div>
          )}
          {!loading && error && (
            <div style={{ fontSize: '12px', color: '#dc3545', marginBottom: '8px' }}>
              <strong>Error:</strong> {error}
              <button
                type="button"
                onClick={handleRetry}
                style={{
                  marginLeft: '8px',
                  fontSize: '12px',
                  padding: '4px 8px',
                  cursor: 'pointer'
                }}
              >
                Retry
              </button>
            </div>
          )}
          {!loading && !error && imageData && (
            <img
              src={imageData}
              alt="Generated for flashcard"
              style={{
                maxWidth: '100%',
                height: 'auto',
                maxHeight: '200px',
                objectFit: 'contain',
                borderRadius: '8px',
                border: '1px solid #ddd',
                marginBottom: '10px',
                display: 'block',
                marginLeft: 'auto',
                marginRight: 'auto'
              }}
            />
          )}
        </>
      )}

      {card.image_description && (
        <div style={{ fontSize: '12px', color: isPlaceholder ? '#856404' : '#6c757d' }}>
          <strong>Description:</strong> {card.image_description}
        </div>
      )}

      {isPlaceholder && (
        <div
          style={{
            marginTop: '10px',
            padding: '8px',
            background: '#e9ecef',
            borderRadius: '4px',
            fontSize: '11px',
            color: '#6c757d'
          }}
        >
          <strong>Note:</strong> This is a placeholder. To generate actual images, integrate with an
          image generation service like DALL-E 3, Midjourney, or Stable Diffusion.
        </div>
      )}
    </div>
  );
};

const CardCuration = ({ cards, onApproveCard, onRefresh }) => {
  const { t } = useLanguage();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedCards, setSelectedCards] = useState([]);
  const masterCheckboxRef = useRef(null);
  const [activeTab, setActiveTab] = useState('pending'); // 'pending', 'approved', 'synced'
  
  // Helper function to normalize tags - ensure it's always an array
  const normalizeTags = (tags) => {
    if (!tags) return [];
    if (Array.isArray(tags)) return tags;
    if (typeof tags === 'string') {
      // Handle comma-separated string or single string
      return tags.split(',').map(t => t.trim()).filter(t => t);
    }
    return [];
  };
  const [ankiProfiles, setAnkiProfiles] = useState([]);
  const [selectedDeck, setSelectedDeck] = useState(() => {
    // Load last selected deck from localStorage
    return localStorage.getItem('lastSelectedDeck') || '';
  });
  const [availableDecks, setAvailableDecks] = useState([]);
  const [editingCard, setEditingCard] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [currentPageApproved, setCurrentPageApproved] = useState(1);
  const [currentPageSynced, setCurrentPageSynced] = useState(1);
  const [cardsPerPage] = useState(10);
  const [imageGenerationState, setImageGenerationState] = useState({});
  const [expandedCards, setExpandedCards] = useState(new Set());

  React.useEffect(() => {
    loadAnkiProfiles();
    loadAvailableDecks();
  }, []);

  const loadAnkiProfiles = async () => {
    try {
      const response = await axios.get(`${API_BASE}/anki-profiles`);
      console.log('Loaded Anki profiles:', response.data);
      setAnkiProfiles(response.data);
      
      // If no profiles exist, create a default one
      if (response.data.length === 0) {
        console.log('No Anki profiles found, creating default...');
        await createDefaultProfile();
      }
    } catch (error) {
      console.error('Error loading Anki profiles:', error);
    }
  };

  const loadAvailableDecks = async () => {
    try {
      const response = await axios.get(`${API_BASE}/anki/decks`);
      console.log('Loaded Anki decks:', response.data.decks);
      setAvailableDecks(response.data.decks || []);
    } catch (error) {
      console.error('Error loading Anki decks:', error);
      // If AnkiConnect is not available, just use empty array
      setAvailableDecks([]);
    }
  };

  const createDefaultProfile = async () => {
    try {
      const defaultProfile = {
        name: 'Default',
        deck_name: 'Curious Mario',
        is_active: true
      };
      await axios.post(`${API_BASE}/anki-profiles`, defaultProfile);
      const response = await axios.get(`${API_BASE}/anki-profiles`);
      setAnkiProfiles(response.data);
      setSelectedDeck('Curious Mario');
    } catch (error) {
      console.error('Error creating default profile:', error);
    }
  };

  const handleCardSelect = (cardId) => {
    setSelectedCards(prev => 
      prev.includes(cardId) 
        ? prev.filter(id => id !== cardId)
        : [...prev, cardId]
    );
  };

  const handleToggleAllVisible = () => {
    const visibleCardIds = currentCards.map(card => card.id);
    const allSelected = visibleCardIds.length > 0 && visibleCardIds.every(id => selectedCards.includes(id));
    
    if (allSelected) {
      // Deselect all visible cards
      setSelectedCards(prev => prev.filter(id => !visibleCardIds.includes(id)));
    } else {
      // Select all visible cards
      setSelectedCards(prev => [...new Set([...prev, ...visibleCardIds])]);
    }
  };

  const handleSelectAllInTab = () => {
    const allTabCardIds = currentTabCards.map(card => card.id);
    const allSelected = allTabCardIds.length > 0 && allTabCardIds.every(id => selectedCards.includes(id));
    
    if (allSelected) {
      // Deselect all cards in current tab
      setSelectedCards(prev => prev.filter(id => !allTabCardIds.includes(id)));
    } else {
      // Select all cards in current tab (across all pages)
      setSelectedCards(prev => [...new Set([...prev, ...allTabCardIds])]);
    }
  };

  const handleSelectAllPending = () => {
    const sortedCards = [...cards].sort((a, b) => {
      const dateA = new Date(a.created_at);
      const dateB = new Date(b.created_at);
      return dateB - dateA;
    });
    const allPendingCards = sortedCards.filter(card => card.status === 'pending');
    const allPendingIds = allPendingCards.map(card => card.id);
    
    // Check if all pending are already selected
    const allSelected = allPendingIds.length > 0 && allPendingIds.every(id => selectedCards.includes(id));
    
    if (allSelected) {
      // Deselect all pending cards
      setSelectedCards(prev => prev.filter(id => !allPendingIds.includes(id)));
    } else {
      // Select all pending cards (across all pages)
      setSelectedCards(prev => [...new Set([...prev, ...allPendingIds])]);
    }
  };

  const handleApproveSelected = async () => {
    for (const cardId of selectedCards) {
      await onApproveCard(cardId);
    }
    setSelectedCards([]);
  };

  const handleDeleteCard = async (cardId) => {
    if (!window.confirm('Are you sure you want to delete this card?')) {
      return;
    }
    
    try {
      await axios.delete(`${API_BASE}/cards/${cardId}`);
      onRefresh();
    } catch (error) {
      console.error('Error deleting card:', error);
      alert('Failed to delete card');
    }
  };

  const handleDeleteSelected = async () => {
    const sortedCards = [...cards].sort((a, b) => {
      const dateA = new Date(a.created_at);
      const dateB = new Date(b.created_at);
      return dateB - dateA;
    });
    const allPendingCards = sortedCards.filter(card => card.status === 'pending');
    const allPendingIds = allPendingCards.map(card => card.id);
    const allPendingSelected = allPendingIds.length > 0 && 
      selectedCards.length === allPendingIds.length &&
      allPendingIds.every(id => selectedCards.includes(id));
    
    let confirmMessage = `Are you sure you want to delete ${selectedCards.length} card(s)?`;
    
    if (allPendingSelected) {
      confirmMessage = `⚠️ WARNING: You are about to delete ALL ${selectedCards.length} pending cards!\n\nThis action cannot be undone. Are you absolutely sure?`;
    } else if (selectedCards.length >= 10) {
      confirmMessage = `⚠️ You are about to delete ${selectedCards.length} cards.\n\nThis action cannot be undone. Are you sure?`;
    }
    
    if (!window.confirm(confirmMessage)) {
      return;
    }
    
    try {
      for (const cardId of selectedCards) {
        await axios.delete(`${API_BASE}/cards/${cardId}`);
      }
      setSelectedCards([]);
      onRefresh();
    } catch (error) {
      console.error('Error deleting cards:', error);
      alert('Failed to delete some cards');
    }
  };

  const handleEditCard = (card) => {
    setEditingCard(card.id);
    setEditForm({ ...card });
  };

  const handleEditFieldChange = (field, value) => {
    setEditForm(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveEdit = async () => {
    if (!editingCard || savingEdit) return;
    setSavingEdit(true);
    try {
      await axios.put(`${API_BASE}/cards/${editingCard}`, editForm);
      if (onRefresh && typeof onRefresh === 'function') {
        await onRefresh();
      }
      setEditingCard(null);
      setEditForm({});
    } catch (error) {
      console.error('Error saving card:', error);
      alert(t('failedToSaveCard'));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingCard(null);
    setEditForm({});
  };

  const handleGenerateImage = async (cardId, position = 'front') => {
    setImageGenerationState(prev => ({
      ...prev,
      [cardId]: { loading: true, error: null }
    }));

    try {
      // Get selected image model from localStorage (set by ChatAssistant)
      const selectedImageModel = localStorage.getItem('selectedImageModel');
      
      // Get LLM configuration from localStorage
      const llmProvider = localStorage.getItem('llm_provider') || 'gemini';
      const llmKey = localStorage.getItem('llm_key') || '';
      const llmBaseUrl = localStorage.getItem('llm_base_url') || '';
      
      const requestBody = {
        position,
        location: 'before'
      };
      
      // Include image_model if one is selected
      if (selectedImageModel) {
        requestBody.image_model = selectedImageModel;
      }
      
      // Prepare headers with LLM configuration
      const headers = {
        'X-LLM-Provider': llmProvider,
        'X-LLM-Key': llmKey,
        'X-LLM-Base-URL': llmBaseUrl
      };
      
      const response = await axios.post(
        `${API_BASE}/cards/${cardId}/generate-image`, 
        requestBody,
        { headers }
      );

      const message = response.data?.message || '';
      setImageGenerationState(prev => ({
        ...prev,
        [cardId]: { loading: false, error: null, success: true, message }
      }));

      if (message) {
        console.log(message);
      }

      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      const message = error.response?.data?.detail || t('generateImageError');
      setImageGenerationState(prev => ({
        ...prev,
        [cardId]: { loading: false, error: message }
      }));
      alert(message);
    }
  };

  const handleCardIdClick = (cardId) => {
    if (!cardId) return;
    window.dispatchEvent(new CustomEvent('card-id-clicked', { detail: `#${cardId.slice(-6)}` }));
  };

  const toggleCardExpansion = (cardId) => {
    setExpandedCards(prev => {
      const newSet = new Set(prev);
      if (newSet.has(cardId)) {
        newSet.delete(cardId);
      } else {
        newSet.add(cardId);
      }
      return newSet;
    });
  };

  const handleSyncToAnki = async (forceResync = false) => {
    console.log('🔵 Sync to Anki clicked! Force resync:', forceResync);
    console.log('Selected deck:', selectedDeck, 'Type:', typeof selectedDeck, 'Truthy?:', !!selectedDeck);
    console.log('Selected cards:', selectedCards);
    console.log('All cards:', cards);
    console.log('Button should be disabled?', selectedCards.length === 0 || !selectedDeck);
    
    if (!selectedDeck) {
      console.log('❌ No deck selected');
      alert(t('pleaseSelectAnkiProfile'));
      return;
    }

    // If forceResync, allow synced cards, otherwise only approved
    const cardsToSync = cards.filter(card => {
      if (!selectedCards.includes(card.id)) return false;
      if (forceResync) return true; // Allow any selected card
      return card.status === 'approved'; // Only approved cards
    });

    console.log('Cards to sync:', cardsToSync);

    if (cardsToSync.length === 0) {
      console.log('❌ No cards selected for sync');
      alert(forceResync ? 'Please select cards to re-sync' : t('pleaseSelectApprovedCards'));
      return;
    }

    const deckName = selectedDeck;
    console.log('Deck name:', deckName);

    try {
      const response = await axios.post(`${API_BASE}/anki/sync`, {
        deck_name: deckName,
        card_ids: cardsToSync.map(c => c.id)
      });

      alert(`✅ Success!\n${response.data.message}\n\nCards have been added to Anki deck: ${deckName}`);
      
      // Refresh the cards to show updated status
      onRefresh();
      setSelectedCards([]);
    } catch (error) {
      console.error('Error syncing to Anki:', error);
      
      let errorMessage = 'Failed to sync cards to Anki';
      
      if (error.response?.status === 503) {
        errorMessage = '❌ Cannot connect to Anki!\n\nMake sure:\n1. Anki is running\n2. AnkiConnect add-on is installed\n3. AnkiConnect is enabled';
      } else if (error.response?.data?.detail) {
        errorMessage = `Error: ${error.response.data.detail}`;
      }
      
      alert(errorMessage);
    }
  };

  const renderCompactPreview = (card) => {
    // Show only the essential question/sentence content
    switch (card.card_type) {
      case 'basic':
      case 'basic_reverse':
        const frontContent = card.front || '';
        // Strip HTML tags for compact view, but keep text content
        const frontText = frontContent.replace(/<[^>]*>/g, '').trim() || '(No front content)';
        return (
          <div className="card-preview-compact" style={{ padding: '4px 0', fontSize: '18px', lineHeight: '1.75', color: '#495057' }}>
            <strong style={{ color: '#6c757d', marginRight: '6px' }}>{t('front')}:</strong>
            <span style={{ 
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {frontText}
            </span>
          </div>
        );
      case 'interactive_cloze':
      case 'cloze':
        const textContent = card.text_field || card.cloze_text || '';
        // Strip HTML tags first
        let textOnly = textContent.replace(/<[^>]*>/g, '');
        // Replace cloze markers [[c1::answer]] with [answer] to show the actual word
        textOnly = textOnly.replace(/\[\[c\d+::([^\]]+)\]\]/g, '[$1]');
        textOnly = textOnly.trim() || '(No text content)';
        return (
          <div className="card-preview-compact" style={{ padding: '4px 0', fontSize: '18px', lineHeight: '1.75', color: '#495057' }}>
            <span style={{ 
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {textOnly}
            </span>
          </div>
        );
      default:
        return (
          <div className="card-preview-compact" style={{ padding: '4px 0', fontSize: '18px', lineHeight: '1.75', color: '#6c757d' }}>
            {card.card_type || 'Unknown card type'}
          </div>
        );
    }
  };

  const renderCardPreview = (card) => {
    const isEditing = editingCard === card.id;
    const cardData = isEditing ? editForm : card;

    if (isEditing) {
      return renderEditForm(card);
    }

    const renderRemarks = () => {
      const remarks = card.field__Remarks || card.field__remarks;
      if (!remarks || !remarks.trim()) {
        return null;
      }
      return (
        <div
          className="card-remarks"
          style={{
            marginTop: '12px',
            padding: '10px',
            background: '#f0f4ff',
            border: '1px solid #cfe2ff',
            borderRadius: '8px',
            fontSize: '12px',
            color: '#1d3557'
          }}
        >
          <strong style={{display: 'block', marginBottom: '6px'}}>CUMA Remarks</strong>
          <div style={{whiteSpace: 'pre-line', lineHeight: 1.5}}>
            {remarks}
          </div>
        </div>
      );
    };

    switch (card.card_type) {
      case 'basic':
        return (
          <div className="card-preview">
            <h4>{t('basicCard')}</h4>
            <div className="front">
              <strong>{t('front')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.front}} />
            </div>
            <div className="back">
              <strong>{t('back')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.back}} />
            </div>
            <CardImagePreview card={card} />
            {renderRemarks()}
          </div>
        );
      case 'basic_reverse':
        return (
          <div className="card-preview">
            <h4>{t('basicReverseCard')}</h4>
            <div className="front">
              <strong>{t('front')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.front}} />
            </div>
            <div className="back">
              <strong>{t('back')}:</strong> 
              <div dangerouslySetInnerHTML={{__html: card.back}} />
            </div>
            <div className="note">{t('worksBoothWays')}</div>
            <CardImagePreview card={card} />
            {renderRemarks()}
          </div>
        );
      case 'interactive_cloze':
        return (
          <div className="card-preview">
            <h4>CUMA - Interactive Cloze Card</h4>
            <div 
              className="cloze-text" 
              dangerouslySetInnerHTML={{__html: card.text_field || card.cloze_text}}
            />
            {card.extra_field && (
              <div className="extra-info">
                <strong>Extra:</strong> 
                <div dangerouslySetInnerHTML={{__html: card.extra_field}} />
              </div>
            )}
            <div className="note">Click blanks to reveal (uses [[c1::answer]] syntax)</div>
            <CardImagePreview card={card} />
            {renderRemarks()}
          </div>
        );
      case 'cloze':
        return (
          <div className="card-preview">
            <h4>{t('clozeCard')}</h4>
            <div className="cloze-text">{card.cloze_text}</div>
            <div className="note">{t('missingWordHidden')}</div>
            <CardImagePreview card={card} />
            {renderRemarks()}
          </div>
        );
      default:
        return (
          <div className="card-preview">
            <h4>{card.card_type}</h4>
            <CardImagePreview card={card} />
            {renderRemarks()}
          </div>
        );
    }
  };

  const renderEditForm = (card) => {
    return (
      <div className="card-edit-form">
        <h4>{t('editingCardTitle').replace('{type}', card.card_type || '')}</h4>
        
        {card.card_type === 'interactive_cloze' ? (
          <>
            <div className="form-group">
              <label>{t('textFieldLabel')}</label>
              <RichTextEditor
                value={editForm.text_field || ''}
                onChange={(value) => handleEditFieldChange('text_field', value)}
                placeholder={t('textFieldPlaceholder')}
              />
            </div>
            <div className="form-group">
              <label>{t('extraFieldLabel')}</label>
              <RichTextEditor
                value={editForm.extra_field || ''}
                onChange={(value) => handleEditFieldChange('extra_field', value)}
                placeholder={t('extraFieldPlaceholder')}
              />
            </div>
          </>
        ) : (
          <>
            <div className="form-group">
              <label>{t('frontLabel')}</label>
              <RichTextEditor
                value={editForm.front || ''}
                onChange={(value) => handleEditFieldChange('front', value)}
                placeholder={t('frontPlaceholder')}
              />
            </div>
            <div className="form-group">
              <label>{t('backLabel')}</label>
              <RichTextEditor
                value={editForm.back || ''}
                onChange={(value) => handleEditFieldChange('back', value)}
                placeholder={t('backPlaceholder')}
              />
            </div>
          </>
        )}
        
        <div className="form-group">
          <label>{t('tagsLabel')}</label>
          <input
            type="text"
            value={(editForm.tags || []).join(', ')}
            onChange={(e) => {
              const tags = e.target.value.split(',').map(t => t.trim()).filter(t => t);
              handleEditFieldChange('tags', tags);
            }}
          />
        </div>
        
        <div className="edit-actions">
          <button
            onClick={handleSaveEdit}
            className="btn btn-success"
            disabled={savingEdit}
          >
            {savingEdit ? t('savingChanges') : t('saveChanges')}
          </button>
          <button
            onClick={handleCancelEdit}
            className="btn btn-secondary"
            disabled={savingEdit}
          >
            {t('cancel')}
          </button>
        </div>
      </div>
    );
  };

  const getStatusBadge = (status) => {
    const statusClasses = {
      pending: 'status-pending',
      approved: 'status-approved',
      synced: 'status-synced'
    };
    const statusText = {
      pending: t('pending'),
      approved: t('approved'),
      synced: t('synced')
    };
    return (
      <span className={'status-badge ' + statusClasses[status]}>
        {statusText[status] || status.toUpperCase()}
      </span>
    );
  };

  // Reset pagination when switching tabs
  useEffect(() => {
    setCurrentPage(1);
    setCurrentPageApproved(1);
    setCurrentPageSynced(1);
  }, [activeTab]);

  // Sort cards by created_at descending (latest first)
  const sortedCards = [...cards].sort((a, b) => {
    const dateA = new Date(a.created_at);
    const dateB = new Date(b.created_at);
    return dateB - dateA;
  });
  
  const pendingCards = sortedCards.filter(card => card.status === 'pending');
  const approvedCards = sortedCards.filter(card => card.status === 'approved');
  const syncedCards = sortedCards.filter(card => card.status === 'synced');
  
  // Get current tab's cards and pagination
  const getCurrentTabCards = () => {
    switch (activeTab) {
      case 'pending':
        return pendingCards;
      case 'approved':
        return approvedCards;
      case 'synced':
        return syncedCards;
      default:
        return [];
    }
  };

  const getCurrentPage = () => {
    switch (activeTab) {
      case 'pending':
        return currentPage;
      case 'approved':
        return currentPageApproved;
      case 'synced':
        return currentPageSynced;
      default:
        return 1;
    }
  };

  const setCurrentPageForTab = (page) => {
    switch (activeTab) {
      case 'pending':
        setCurrentPage(page);
        break;
      case 'approved':
        setCurrentPageApproved(page);
        break;
      case 'synced':
        setCurrentPageSynced(page);
        break;
    }
  };

  const currentTabCards = getCurrentTabCards();
  const currentPageForTab = getCurrentPage();
  const indexOfLastCard = currentPageForTab * cardsPerPage;
  const indexOfFirstCard = indexOfLastCard - cardsPerPage;
  const currentCards = currentTabCards.slice(indexOfFirstCard, indexOfLastCard);
  const totalPages = Math.ceil(currentTabCards.length / cardsPerPage);
  
  // Calculate master checkbox state for current tab
  const visibleCardIds = currentCards.map(card => card.id);
  const selectedVisibleCount = visibleCardIds.filter(id => selectedCards.includes(id)).length;
  const allVisibleSelected = visibleCardIds.length > 0 && selectedVisibleCount === visibleCardIds.length;
  const someVisibleSelected = selectedVisibleCount > 0 && selectedVisibleCount < visibleCardIds.length;
  
  // Calculate if all cards in current tab are selected
  const allTabCardIds = currentTabCards.map(card => card.id);
  const allTabSelected = allTabCardIds.length > 0 && 
    allTabCardIds.every(id => selectedCards.includes(id));
  
  // For backward compatibility with pending-specific logic
  const allPendingIds = pendingCards.map(card => card.id);
  const allPendingSelected = allPendingIds.length > 0 && 
    allPendingIds.every(id => selectedCards.includes(id));
  
  // Update master checkbox indeterminate state
  useEffect(() => {
    if (masterCheckboxRef.current) {
      masterCheckboxRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected, selectedCards, currentCards]);
  
  // Check if sync button should be enabled
  const canSync = selectedCards.length > 0 && selectedDeck;
  const hasApprovedSelected = cards.filter(card => 
    selectedCards.includes(card.id) && card.status === 'approved'
  ).length > 0;

  const handleRefreshCards = async () => {
    if (!onRefresh || isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
        <h2 style={{ margin: 0 }}>{t('curationTitle')}</h2>
        {onRefresh && (
          <button
            type="button"
            onClick={handleRefreshCards}
            disabled={isRefreshing}
            title={t('refreshCards') || 'Refresh card list'}
            className="curation-refresh-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '6px',
              border: 'none',
              background: 'transparent',
              color: '#666',
              cursor: isRefreshing ? 'wait' : 'pointer',
              borderRadius: '4px',
            }}
            aria-label={t('refreshCards') || 'Refresh card list'}
          >
            <RefreshCw
              size={18}
              style={{
                transition: 'color 0.2s',
                animation: isRefreshing ? 'spin 0.8s linear infinite' : 'none',
              }}
            />
          </button>
        )}
      </div>
      <p>{t('curationDescription')}</p>

      {/* Global Settings */}
      <div className="card">
        <h3>{t('globalSettings')}</h3>
        <div className="form-group">
          <SearchableDropdown
            label={`${t('ankiProfile')}:`}
            options={availableDecks}
            value={selectedDeck}
            onChange={(value) => {
              console.log('✅ Deck selected:', value);
              setSelectedDeck(value);
              // Save to localStorage for next time
              localStorage.setItem('lastSelectedDeck', value);
            }}
            placeholder={!selectedDeck ? "⚠️ " + t('selectAnkiProfile') : t('selectAnkiProfile')}
            onRefresh={loadAvailableDecks}
          />
          <small style={{color: '#666', fontSize: '12px', marginTop: '5px', display: 'block'}}>
            {availableDecks.length > 0 
              ? `${availableDecks.length} decks available from Anki`
              : 'Type to create new deck or click ↻ to refresh'}
            {selectedDeck && (
              <span style={{marginLeft: '10px', color: '#28a745', fontWeight: 'bold'}}>
                ✓ Last used: {selectedDeck}
              </span>
            )}
          </small>
        </div>
      </div>

      {/* Selection Controls */}
      <div className="card">
        <h3>{t('selectionControls')}</h3>
        <div className="selection-controls" style={{display: 'flex', flexWrap: 'nowrap', gap: '8px', alignItems: 'center'}}>
          <button 
            onClick={handleApproveSelected} 
            className="btn btn-success"
            disabled={selectedCards.length === 0}
            style={{whiteSpace: 'nowrap'}}
          >
            {t('approveSelected')} ({selectedCards.length})
          </button>
          <button 
            onClick={handleDeleteSelected} 
            className="btn btn-danger"
            disabled={selectedCards.length === 0}
            style={{whiteSpace: 'nowrap'}}
            title="Delete Selected"
          >
            🗑️ {t('deleteSelected')} ({selectedCards.length})
          </button>
          <button 
            onClick={() => handleSyncToAnki(false)} 
            className="btn"
            disabled={selectedCards.length === 0 || !selectedDeck}
            title={
              !selectedDeck 
                ? t('pleaseSelectAnkiProfile')
                : selectedCards.length === 0 
                  ? t('pleaseSelectApprovedCards')
                  : !hasApprovedSelected
                    ? "Only approved cards can be synced"
                    : t('syncToAnki')
            }
          >
            {t('syncToAnki')}
          </button>
          
          <button 
            onClick={() => handleSyncToAnki(true)} 
            className="btn btn-secondary"
            disabled={selectedCards.length === 0 || !selectedDeck}
            title={
              !selectedDeck 
                ? 'Select a deck first'
                : selectedCards.length === 0 
                  ? 'Select cards to re-sync'
                  : 'Re-sync selected cards (approved or synced)'
            }
            style={{
              backgroundColor: '#6c757d',
              marginLeft: '10px'
            }}
          >
            🔄 {t('resyncSelected')}
          </button>
        </div>
        
        {/* Status message */}
        {selectedCards.length > 0 && !hasApprovedSelected && (
          <div style={{marginTop: '10px', padding: '10px', background: '#fff3cd', borderRadius: '4px', color: '#856404'}}>
            {t('warningSelectApproved').replace('{count}', selectedCards.length)}
          </div>
        )}
        
        {!selectedDeck && (
          <div style={{marginTop: '10px', padding: '10px', background: '#d1ecf1', borderRadius: '4px', color: '#0c5460'}}>
            {t('infoSelectProfile')}
          </div>
        )}
      </div>

      {/* Card List with Tabs */}
      <div className="card">
        {/* Tabs */}
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '2px solid #ddd' }}>
          <button
            onClick={() => setActiveTab('pending')}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderBottom: activeTab === 'pending' ? '3px solid #2196f3' : '3px solid transparent',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              fontWeight: activeTab === 'pending' ? 'bold' : 'normal',
              fontSize: '16px'
            }}
          >
            待处理 ({pendingCards.length})
          </button>
          <button
            onClick={() => setActiveTab('approved')}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderBottom: activeTab === 'approved' ? '3px solid #2196f3' : '3px solid transparent',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              fontWeight: activeTab === 'approved' ? 'bold' : 'normal',
              fontSize: '16px'
            }}
          >
            已批准 ({approvedCards.length})
          </button>
          <button
            onClick={() => setActiveTab('synced')}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderBottom: activeTab === 'synced' ? '3px solid #2196f3' : '3px solid transparent',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              fontWeight: activeTab === 'synced' ? 'bold' : 'normal',
              fontSize: '16px'
            }}
          >
            已同步 ({syncedCards.length})
          </button>
        </div>

        {/* Tab Content */}
        <div>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
              <input
                ref={masterCheckboxRef}
                type="checkbox"
                checked={allVisibleSelected}
                onChange={handleToggleAllVisible}
                style={{
                  width: '18px',
                  height: '18px',
                  cursor: 'pointer'
                }}
                title={
                  allVisibleSelected 
                    ? 'Deselect all visible cards'
                    : someVisibleSelected
                      ? 'Select all visible cards'
                      : 'Select all visible cards'
                }
              />
              <h3 style={{margin: 0}}>
                {activeTab === 'pending' && t('pendingCards')}
                {activeTab === 'approved' && t('approvedCards')}
                {activeTab === 'synced' && t('syncedCards')}
              </h3>
              <button 
                onClick={handleSelectAllInTab} 
                className="btn btn-secondary"
                style={{
                  whiteSpace: 'nowrap',
                  padding: '6px 12px',
                  fontSize: '14px',
                  marginLeft: '10px'
                }}
                title={allTabSelected ? '取消全选' : '全选所有卡片'}
              >
                {allTabSelected ? '取消' : '全选'}
              </button>
            </div>
            {totalPages > 1 && (
              <div className="pagination" style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                <button 
                  onClick={() => setCurrentPageForTab(Math.max(1, currentPageForTab - 1))}
                  disabled={currentPageForTab === 1}
                  className="btn btn-secondary"
                  style={{
                    padding: '6px 12px',
                    minWidth: '40px',
                    fontSize: '18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                  title="Previous page"
                >
                  ‹
                </button>
                <span style={{margin: '0 10px', fontSize: '14px'}}>
                  {currentPageForTab} / {totalPages}
                </span>
                <button 
                  onClick={() => setCurrentPageForTab(Math.min(totalPages, currentPageForTab + 1))}
                  disabled={currentPageForTab === totalPages}
                  className="btn btn-secondary"
                  style={{
                    padding: '6px 12px',
                    minWidth: '40px',
                    fontSize: '18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                  title="Next page"
                >
                  ›
                </button>
              </div>
            )}
          </div>

          {currentTabCards.length === 0 ? (
            <p>
              {activeTab === 'pending' && t('noPendingCards')}
              {activeTab === 'approved' && t('noApprovedCards')}
              {activeTab === 'synced' && t('syncedSuccessfully')}
            </p>
          ) : (
            <div className="cards-list">
              {currentCards.map(card => {
                const isExpanded = expandedCards.has(card.id);
                const isEditing = editingCard === card.id;
                
                return (
                  <div key={card.id} className="card-item" style={{ marginBottom: '12px', border: '1px solid #dee2e6', borderRadius: '6px', padding: '12px' }}>
                    <div className="card-header" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                      <input
                        type="checkbox"
                        checked={selectedCards.includes(card.id)}
                        onChange={() => handleCardSelect(card.id)}
                        style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span 
                        className="card-id"
                        onClick={() => handleCardIdClick(card.id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            handleCardIdClick(card.id);
                          }
                        }}
                        style={{ cursor: 'pointer', fontWeight: 'bold', color: '#007bff' }}
                      >
                        #{card.id.slice(-6)}
                      </span>
                      {getStatusBadge(card.status)}
                      {isExpanded && (
                        <span className="card-tags" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {normalizeTags(card.tags).map(tag => (
                            <span key={tag} className="tag" style={{ fontSize: '11px', padding: '2px 6px', background: '#e9ecef', borderRadius: '3px' }}>#{tag}</span>
                          ))}
                        </span>
                      )}
                      {editingCard !== card.id && (
                        <div className="card-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '6px', alignItems: 'center' }}>
                          {activeTab === 'pending' && (
                            <>
                              <button 
                                onClick={() => handleGenerateImage(card.id)}
                                className="btn btn-secondary"
                                disabled={imageGenerationState[card.id]?.loading}
                                style={{ fontSize: '12px', padding: '4px 8px', whiteSpace: 'nowrap' }}
                              >
                                {imageGenerationState[card.id]?.loading ? t('generatingImage') : t('generateImage')}
                              </button>
                              <button 
                                onClick={() => handleEditCard(card)}
                                className="btn btn-secondary"
                                style={{ fontSize: '12px', padding: '4px 8px', whiteSpace: 'nowrap' }}
                              >
                                {t('edit')}
                              </button>
                              <button 
                                onClick={() => onApproveCard(card.id)}
                                className="btn btn-success"
                                style={{ fontSize: '12px', padding: '4px 8px', whiteSpace: 'nowrap' }}
                              >
                                {t('approve')}
                              </button>
                            </>
                          )}
                          <button 
                            onClick={() => handleDeleteCard(card.id)}
                            className="btn btn-danger"
                            style={{ fontSize: '12px', padding: '4px 8px', whiteSpace: 'nowrap' }}
                          >
                            {t('delete')}
                          </button>
                        </div>
                      )}
                      <button
                        onClick={() => toggleCardExpansion(card.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          fontSize: '16px',
                          padding: '4px 8px',
                          color: '#6c757d',
                          display: 'flex',
                          alignItems: 'center'
                        }}
                        title={isExpanded ? 'Collapse' : 'Expand'}
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                    </div>
                    {!isExpanded && !isEditing && renderCompactPreview(card)}
                    {isExpanded && renderCardPreview(card)}
                    {isEditing && renderEditForm(card)}
                    {imageGenerationState[card.id]?.success && imageGenerationState[card.id]?.message && (
                      <div style={{marginTop: '10px', color: '#28a745', fontSize: '12px'}}>
                        {imageGenerationState[card.id].message}
                      </div>
                    )}
                    {imageGenerationState[card.id]?.error && (
                      <div style={{marginTop: '10px', color: '#dc3545', fontSize: '12px'}}>
                        {imageGenerationState[card.id].error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CardCuration;

