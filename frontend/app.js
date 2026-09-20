/**
 * InsureGPT Frontend Application Controller
 * Pure Vanilla JavaScript handling state, SSE streaming, conversation management, and theme.
 */

// Application State
const state = {
  currentConversationId: null,
  conversations: [],
  isStreaming: false,
  abortController: null,
  currentTheme: localStorage.getItem('insuregpt_theme') || 'dark',
  lastUserQuery: ''
};

// DOM Element References
const elements = {
  sidebar: document.getElementById('sidebar'),
  sidebarOverlay: document.getElementById('sidebarOverlay'),
  mobileMenuBtn: document.getElementById('mobileMenuBtn'),
  closeSidebarBtn: document.getElementById('closeSidebarBtn'),
  newChatBtn: document.getElementById('newChatBtn'),
  listToday: document.getElementById('listToday'),
  listYesterday: document.getElementById('listYesterday'),
  listPrevious: document.getElementById('listPrevious'),
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  currentChatTitle: document.getElementById('currentChatTitle'),
  chatViewport: document.getElementById('chatViewport'),
  heroContainer: document.getElementById('heroContainer'),
  messagesContainer: document.getElementById('messagesContainer'),
  quickTopicsContainer: document.getElementById('quickTopicsContainer'),
  composerForm: document.getElementById('composerForm'),
  messageInput: document.getElementById('messageInput'),
  sendBtn: document.getElementById('sendBtn'),
  attachBtn: document.getElementById('attachBtn'),
  fileUploadInput: document.getElementById('fileUploadInput'),
};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  applyTheme(state.currentTheme);
  setupEventListeners();
  loadConversations();
  autoResizeInput();
});

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
  // Theme Toggle
  elements.themeToggleBtn.addEventListener('click', toggleTheme);

  // Mobile Sidebar
  elements.mobileMenuBtn.addEventListener('click', openSidebar);
  elements.closeSidebarBtn.addEventListener('click', closeSidebar);
  elements.sidebarOverlay.addEventListener('click', closeSidebar);

  // New Chat
  elements.newChatBtn.addEventListener('click', startNewChat);

  // Textarea input and auto-resize
  elements.messageInput.addEventListener('input', () => {
    autoResizeInput();
    updateSendButtonState();
  });

  // Enter to send, Shift+Enter for newline
  elements.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!state.isStreaming && elements.messageInput.value.trim().length > 0) {
        sendMessage(elements.messageInput.value.trim());
      }
    }
  });

  // Composer Form Submit
  elements.composerForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (state.isStreaming) {
      stopStreaming();
      return;
    }
    const message = elements.messageInput.value.trim();
    if (message) {
      sendMessage(message);
    }
  });

  // Prompt Suggestion Cards
  document.querySelectorAll('.suggestion-card').forEach(card => {
    card.addEventListener('click', () => {
      const prompt = card.getAttribute('data-prompt');
      if (prompt) {
        elements.messageInput.value = prompt;
        autoResizeInput();
        updateSendButtonState();
        sendMessage(prompt);
      }
    });
  });

  // Quick Topics Chips for Non-Tech Users
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt) {
        elements.messageInput.value = prompt;
        autoResizeInput();
        updateSendButtonState();
        sendMessage(prompt);
      }
    });
  });

  // Attachment Button
  elements.attachBtn.addEventListener('click', () => {
    elements.fileUploadInput.click();
  });

  elements.fileUploadInput.addEventListener('change', handleFileUpload);
}

// ============================================================================
// Theme Management
// ============================================================================

function applyTheme(theme) {
  state.currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('insuregpt_theme', theme);
}

function toggleTheme() {
  const newTheme = state.currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

// ============================================================================
// Responsive Sidebar
// ============================================================================

function openSidebar() {
  elements.sidebar.classList.add('open');
  elements.sidebarOverlay.classList.add('active');
}

function closeSidebar() {
  elements.sidebar.classList.remove('open');
  elements.sidebarOverlay.classList.remove('active');
}

// ============================================================================
// Conversation Management
// ============================================================================

async function loadConversations() {
  try {
    const res = await fetch('/api/conversations');
    if (!res.ok) throw new Error('Failed to load conversations');
    state.conversations = await res.json();
    renderConversations();
  } catch (err) {
    console.error('Error fetching conversations:', err);
  }
}

function renderConversations() {
  elements.listToday.innerHTML = '';
  elements.listYesterday.innerHTML = '';
  elements.listPrevious.innerHTML = '';

  const now = new Date();
  const oneDayAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000));
  const twoDaysAgo = new Date(now.getTime() - (48 * 60 * 60 * 1000));

  let countToday = 0;
  let countYesterday = 0;
  let countPrevious = 0;

  state.conversations.forEach(conv => {
    const updated = new Date(conv.updated_at);
    const item = createConversationItemElement(conv);

    if (updated.toDateString() === now.toDateString()) {
      elements.listToday.appendChild(item);
      countToday++;
    } else if (updated.toDateString() === oneDayAgo.toDateString() || updated >= twoDaysAgo) {
      elements.listYesterday.appendChild(item);
      countYesterday++;
    } else {
      elements.listPrevious.appendChild(item);
      countPrevious++;
    }
  });

  document.getElementById('historyToday').style.display = countToday > 0 ? 'block' : 'none';
  document.getElementById('historyYesterday').style.display = countYesterday > 0 ? 'block' : 'none';
  document.getElementById('historyPrevious').style.display = countPrevious > 0 ? 'block' : 'none';
}

function createConversationItemElement(conv) {
  const div = document.createElement('div');
  div.className = `history-item ${conv.id === state.currentConversationId ? 'active' : ''}`;
  div.dataset.id = conv.id;

  const titleSpan = document.createElement('span');
  titleSpan.className = 'history-title';
  titleSpan.textContent = conv.title || 'Untitled Inquiry';
  titleSpan.title = conv.title;

  const actionsDiv = document.createElement('div');
  actionsDiv.className = 'history-actions';

  // Rename Button
  const renameBtn = document.createElement('button');
  renameBtn.className = 'item-action-btn';
  renameBtn.title = 'Rename';
  renameBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 20h9"></path>
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
    </svg>
  `;
  renameBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    promptRenameConversation(conv);
  });

  // Delete Button
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'item-action-btn delete';
  deleteBtn.title = 'Delete';
  deleteBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="3 6 5 6 21 6"></polyline>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
    </svg>
  `;
  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    confirmDeleteConversation(conv.id);
  });

  actionsDiv.appendChild(renameBtn);
  actionsDiv.appendChild(deleteBtn);

  div.appendChild(titleSpan);
  div.appendChild(actionsDiv);

  div.addEventListener('click', () => {
    if (state.currentConversationId !== conv.id) {
      selectConversation(conv.id);
      closeSidebar();
    }
  });

  return div;
}

function startNewChat() {
  state.currentConversationId = null;
  state.lastUserQuery = '';
  elements.currentChatTitle.textContent = 'Insurance Policy Advisor';
  elements.messagesContainer.innerHTML = '';
  elements.heroContainer.style.display = 'flex';
  if (elements.quickTopicsContainer) elements.quickTopicsContainer.style.display = 'flex';
  elements.messageInput.value = '';
  autoResizeInput();
  updateSendButtonState();
  renderConversations();
  closeSidebar();
  elements.messageInput.focus();
}

async function selectConversation(id) {
  try {
    const res = await fetch(`/api/conversations/${id}`);
    if (!res.ok) throw new Error('Conversation not found');
    const conv = await res.json();

    state.currentConversationId = conv.id;
    elements.currentChatTitle.textContent = conv.title || 'Insurance Policy Advisor';
    elements.heroContainer.style.display = 'none';
    if (elements.quickTopicsContainer) elements.quickTopicsContainer.style.display = 'none';
    elements.messagesContainer.innerHTML = '';

    conv.messages.forEach(msg => {
      appendMessageToDOM(msg.role, msg.content, msg.id, false);
    });

    renderConversations();
    scrollToBottom();
  } catch (err) {
    console.error('Error loading conversation:', err);
  }
}

async function promptRenameConversation(conv) {
  const newTitle = prompt('Rename inquiry title:', conv.title);
  if (newTitle && newTitle.trim() && newTitle.trim() !== conv.title) {
    try {
      const res = await fetch(`/api/conversations/${conv.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        if (state.currentConversationId === conv.id) {
          elements.currentChatTitle.textContent = newTitle.trim();
        }
        loadConversations();
      }
    } catch (err) {
      console.error('Rename failed:', err);
    }
  }
}

async function confirmDeleteConversation(id) {
  if (confirm('Are you sure you want to delete this conversation?')) {
    try {
      const res = await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
      if (res.ok) {
        if (state.currentConversationId === id) {
          startNewChat();
        }
        loadConversations();
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  }
}

// ============================================================================
// Messaging & Streaming (SSE)
// ============================================================================

async function sendMessage(text) {
  if (!text || state.isStreaming) return;

  state.lastUserQuery = text;
  elements.heroContainer.style.display = 'none';
  if (elements.quickTopicsContainer) elements.quickTopicsContainer.style.display = 'none';
  elements.messageInput.value = '';
  autoResizeInput();
  updateSendButtonState();

  // 1. Add User Message
  appendMessageToDOM('user', text);

  // 2. Prepare Assistant Message Placeholder with Cursor
  const assistantBubble = appendMessageToDOM('assistant', '', null, true);
  scrollToBottom();

  // 3. Initiate SSE Streaming
  state.isStreaming = true;
  document.body.classList.add('is-streaming');
  state.abortController = new AbortController();

  let accumulatedContent = '';
  let assistantMessageId = null;

  try {
    const payload = {
      conversation_id: state.currentConversationId,
      message: text
    };

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: state.abortController.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep partial line in buffer

      let currentEvent = 'message';
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.replace('event:', '').trim();
        } else if (trimmed.startsWith('data:')) {
          const rawData = trimmed.replace('data:', '').trim();
          if (currentEvent === 'metadata') {
            try {
              const meta = JSON.parse(rawData);
              if (!state.currentConversationId && meta.conversation_id) {
                state.currentConversationId = meta.conversation_id;
                elements.currentChatTitle.textContent = meta.title || text.slice(0, 40);
                loadConversations();
              }
              assistantMessageId = meta.message_id;
            } catch (e) {
              console.warn('Metadata parse warning:', e);
            }
          } else if (currentEvent === 'token') {
            try {
              const tokenObj = JSON.parse(rawData);
              accumulatedContent += tokenObj.content;
              updateAssistantMessageContent(assistantBubble, accumulatedContent);
              scrollToBottom();
            } catch (e) {
              console.warn('Token parse error:', e);
            }
          } else if (currentEvent === 'done' || rawData === '[DONE]') {
            finishStreaming(assistantBubble, accumulatedContent, assistantMessageId);
            return;
          } else if (currentEvent === 'error') {
            accumulatedContent += `\n\n*Error: ${rawData}*`;
            updateAssistantMessageContent(assistantBubble, accumulatedContent);
          }
        }
      }
    }

    finishStreaming(assistantBubble, accumulatedContent, assistantMessageId);

  } catch (err) {
    if (err.name === 'AbortError') {
      finishStreaming(assistantBubble, accumulatedContent + '\n\n*(Generation stopped)*', assistantMessageId);
    } else {
      console.error('Chat error:', err);
      updateAssistantMessageContent(assistantBubble, accumulatedContent + `\n\n*(Unable to reach server: ${err.message})*`);
      finishStreaming(assistantBubble, accumulatedContent, assistantMessageId);
    }
  }
}

function stopStreaming() {
  if (state.abortController) {
    state.abortController.abort();
  }
}

function formatAssistantMarkdown(rawText) {
  if (!rawText) return '';
  let cleaned = rawText;

  // Clean up **### Header** or **###Header** -> ### Header
  cleaned = cleaned.replace(/\*\*###\s*([^\*]+)\*\*/g, '### $1');
  cleaned = cleaned.replace(/###\s*\*\*([^\*]+)\*\*/g, '### $1');

  // Convert raw "Source: Policy Document XYZ..." or "Source: Evidence [1]..." to a clean policy badge
  cleaned = cleaned.replace(/(?:\n|^)\s*\*\*?Source\*\*?:\s*(.+)$/gim, (match, p1) => {
    let cleanSource = p1.replace(/claims_procedure_and_guidelines/g, 'Claims Procedure & Guidelines 2026')
                        .replace(/health_comprehensive_policy_2026/g, 'Comprehensive Health Policy 2026')
                        .replace(/motor_private_car_policy/g, 'Private Car Motor Policy 2026')
                        .replace(/term_life_and_critical_illness_policy_2026/g, 'Term Life & Critical Illness Policy 2026')
                        .replace(/commercial_property_and_fire_policy_2026/g, 'Commercial Property Policy 2026')
                        .replace(/travel_international_insurance_policy_2026/g, 'Overseas Travel Policy 2026')
                        .replace(/\[Evidence\s*\d+\]/gi, '');
    return `\n\n<div class="policy-source-badge"><span class="source-icon">📋</span> <span class="source-label">Verified Policy Reference:</span> ${cleanSource}</div>`;
  });

  if (window.marked) {
    return marked.parse(cleaned);
  }
  return cleaned;
}

function finishStreaming(bubble, finalContent, messageId) {
  state.isStreaming = false;
  document.body.classList.remove('is-streaming');
  state.abortController = null;
  updateSendButtonState();

  // Remove cursor and render final markdown
  const cursor = bubble.querySelector('.streaming-cursor');
  if (cursor) cursor.remove();

  bubble.innerHTML = formatAssistantMarkdown(finalContent);

  if (finalContent.includes('🛡️')) {
    bubble.classList.add('guardrail-bubble');
    const row = bubble.closest('.message-row');
    if (row) row.classList.add('is-guardrail');
  }

  // Attach assistant toolbar (Copy, Regenerate, Feedback)
  const wrapper = bubble.closest('.message-content-wrapper');
  if (wrapper && !wrapper.querySelector('.message-toolbar')) {
    const toolbar = createMessageToolbar(finalContent, messageId);
    wrapper.appendChild(toolbar);
  }

  loadConversations();
  scrollToBottom();
}

// ============================================================================
// DOM Message Rendering
// ============================================================================

function appendMessageToDOM(role, content, messageId = null, withCursor = false) {
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  // Assistant Shield Avatar
  if (role === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    `;
    row.appendChild(avatar);
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'message-content-wrapper';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  if (role === 'user') {
    bubble.textContent = content;
  } else {
    if (content) {
      bubble.innerHTML = formatAssistantMarkdown(content);
      if (content.includes('🛡️')) {
        bubble.classList.add('guardrail-bubble');
        row.classList.add('is-guardrail');
      }
    }
    if (withCursor) {
      const cursor = document.createElement('span');
      cursor.className = 'streaming-cursor';
      bubble.appendChild(cursor);
    }
  }

  wrapper.appendChild(bubble);

  // Add toolbar for completed assistant messages
  if (role === 'assistant' && !withCursor && content) {
    wrapper.appendChild(createMessageToolbar(content, messageId));
  }

  row.appendChild(wrapper);
  elements.messagesContainer.appendChild(row);
  return bubble;
}

function updateAssistantMessageContent(bubble, text) {
  let cursor = bubble.querySelector('.streaming-cursor');
  if (!cursor) {
    cursor = document.createElement('span');
    cursor.className = 'streaming-cursor';
  }

  bubble.innerHTML = formatAssistantMarkdown(text);
  if (text.includes('🛡️')) {
    bubble.classList.add('guardrail-bubble');
    const row = bubble.closest('.message-row');
    if (row) row.classList.add('is-guardrail');
  }
  bubble.appendChild(cursor);
}

function createMessageToolbar(content, messageId) {
  const toolbar = document.createElement('div');
  toolbar.className = 'message-toolbar';

  // Copy Button
  const copyBtn = document.createElement('button');
  copyBtn.className = 'toolbar-btn';
  copyBtn.title = 'Copy response';
  copyBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
    <span>Copy</span>
  `;
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(content).then(() => {
      copyBtn.querySelector('span').textContent = 'Copied!';
      setTimeout(() => {
        copyBtn.querySelector('span').textContent = 'Copy';
      }, 2000);
    });
  });

  // Regenerate Button
  const regenBtn = document.createElement('button');
  regenBtn.className = 'toolbar-btn';
  regenBtn.title = 'Regenerate';
  regenBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="23 4 23 10 17 10"></polyline>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
    </svg>
    <span>Retry</span>
  `;
  regenBtn.addEventListener('click', () => {
    if (state.lastUserQuery && !state.isStreaming) {
      sendMessage(state.lastUserQuery);
    }
  });

  // Thumbs Up
  const thumbsUpBtn = document.createElement('button');
  thumbsUpBtn.className = 'toolbar-btn';
  thumbsUpBtn.title = 'Helpful';
  thumbsUpBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
    </svg>
  `;
  thumbsUpBtn.addEventListener('click', () => {
    submitFeedback(messageId, 1, thumbsUpBtn);
  });

  // Thumbs Down
  const thumbsDownBtn = document.createElement('button');
  thumbsDownBtn.className = 'toolbar-btn';
  thumbsDownBtn.title = 'Not helpful';
  thumbsDownBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
    </svg>
  `;
  thumbsDownBtn.addEventListener('click', () => {
    submitFeedback(messageId, -1, thumbsDownBtn);
  });

  toolbar.appendChild(copyBtn);
  toolbar.appendChild(regenBtn);
  toolbar.appendChild(thumbsUpBtn);
  toolbar.appendChild(thumbsDownBtn);

  return toolbar;
}

async function submitFeedback(messageId, rating, btn) {
  if (!messageId) return;
  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, rating: rating })
    });
    if (res.ok) {
      btn.classList.add('active');
    }
  } catch (err) {
    console.warn('Feedback submission error:', err);
  }
}

// ============================================================================
// File Upload (Phase 1 Skeleton & Verification)
// ============================================================================

async function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', 'policy');

  try {
    const res = await fetch('/api/documents/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    alert(`File received: ${data.filename}\n${data.message}`);
  } catch (err) {
    console.error('File upload error:', err);
    alert('Document upload failed. Please try again.');
  } finally {
    elements.fileUploadInput.value = '';
  }
}

// ============================================================================
// UI Utilities
// ============================================================================

function autoResizeInput() {
  const el = elements.messageInput;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function updateSendButtonState() {
  const hasText = elements.messageInput.value.trim().length > 0;
  elements.sendBtn.disabled = !hasText && !state.isStreaming;
}

function scrollToBottom() {
  elements.chatViewport.scrollTop = elements.chatViewport.scrollHeight;
}
