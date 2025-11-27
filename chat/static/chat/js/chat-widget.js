/**
 * Chat Widget JavaScript
 * Handles floating chat widget functionality - available on all pages
 */

// Chat Widget State
let chatState = {
    isOpen: false,
    isMinimized: false,
    currentView: 'list', // 'list' or 'detail'
    currentRoom: null,
    currentUserId: null,
    currentUserAvatar: null,
    currentOtherUserId: null,
    currentOtherUserAvatar: null,
    currentIsBot: false,  // Track if current room is bot room
    filter: 'all',
    searchQuery: '',
    chatRooms: [],
    chatSocket: null
};

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.currentUserId !== 'undefined') {
        chatState.currentUserId = window.currentUserId;
        chatState.currentUserAvatar = window.currentUserAvatar || null;
        
        // Update input avatar
        updateInputAvatar();
        
        loadChatRooms();
        setupEventListeners();
    }
});

// Update input avatar
function updateInputAvatar() {
    const avatarImg = document.getElementById('chatInputAvatar');
    const avatarPlaceholder = document.querySelector('.chat-input-avatar-placeholder');
    
    if (chatState.currentUserAvatar && avatarImg) {
        avatarImg.src = chatState.currentUserAvatar;
        avatarImg.style.display = 'block';
        if (avatarPlaceholder) avatarPlaceholder.style.display = 'none';
    } else {
        if (avatarImg) avatarImg.style.display = 'none';
        if (avatarPlaceholder) avatarPlaceholder.style.display = 'flex';
    }
}

// Setup Event Listeners
function setupEventListeners() {
    const toggleBtn = document.getElementById('chatToggleBtn');
    const closeBtn = document.getElementById('closeBtn');
    const closeDetailBtn = document.getElementById('closeDetailBtn');
    const minimizeBtn = document.getElementById('minimizeBtn');
    const minimizeDetailBtn = document.getElementById('minimizeDetailBtn');
    const backToListBtn = document.getElementById('backToListBtn');
    const searchInput = document.getElementById('chatSearchInput');
    const sendBtn = document.getElementById('chatSendBtn');
    const messageInput = document.getElementById('chatMessageInput');

    if (!toggleBtn) return; // Chat widget not present

    // Toggle chat window
    toggleBtn.addEventListener('click', toggleChatWindow);
    
    // Close buttons
    if (closeBtn) closeBtn.addEventListener('click', closeChatWindow);
    if (closeDetailBtn) closeDetailBtn.addEventListener('click', closeChatWindow);
    
    // Minimize buttons
    if (minimizeBtn) minimizeBtn.addEventListener('click', minimizeChatWindow);
    if (minimizeDetailBtn) minimizeDetailBtn.addEventListener('click', minimizeChatWindow);
    
    // Back to list
    if (backToListBtn) backToListBtn.addEventListener('click', showChatList);
    
    // Search input
    if (searchInput) searchInput.addEventListener('input', handleSearch);
    
    // Filter buttons
    document.querySelectorAll('.chat-filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.chat-filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            chatState.filter = this.dataset.filter;
            renderChatList();
        });
    });
    
    // Send message
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
    
    // Icon buttons
    const attachBtn = document.getElementById('chatAttachBtn');
    const emojiBtn = document.getElementById('chatEmojiBtn');
    const sendIconBtn = document.getElementById('chatSendIconBtn');
    
    if (attachBtn) {
        attachBtn.addEventListener('click', function(e) {
            e.preventDefault();
            alert('Chức năng đang phát triển');
        });
    }
    
    if (emojiBtn) {
        emojiBtn.addEventListener('click', function(e) {
            e.preventDefault();
            alert('Chức năng đang phát triển');
        });
    }
    
    if (sendIconBtn) {
        sendIconBtn.addEventListener('click', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }
}

// Toggle Chat Window
function toggleChatWindow() {
    chatState.isOpen = !chatState.isOpen;
    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow) {
        if (chatState.isOpen) {
            chatWindow.classList.add('active');
            loadChatRooms();
        } else {
            chatWindow.classList.remove('active');
        }
    }
}

// Open Chat Widget and optionally open a specific room
window.openChatWidget = function(userId = null) {
    const chatWindow = document.getElementById('chatWindow');
    const toggleBtn = document.getElementById('chatToggleBtn');
    
    if (!chatWindow || !toggleBtn) {
        console.error('Chat widget not found');
        return;
    }
    
    // Open widget if closed
    if (!chatState.isOpen) {
        toggleChatWindow();
    }
    
    // If userId provided, find and open that room
    if (userId) {
        // First load chat rooms, then find and open the room
        loadChatRooms().then(() => {
            setTimeout(() => {
                const room = chatState.chatRooms.find(r => r.userId === parseInt(userId));
                if (room) {
                    showChatDetail(room.roomName, {
                        full_name: room.name,
                        user_id: room.userId,
                        email: room.email || ''
                    }, room.isBot || false);
                } else {
                    // Room not found, might need to create it
                    // For now, just show the list
                    console.log('Room not found for userId:', userId);
                }
            }, 500);
        });
    }
};

// Close Chat Window
function closeChatWindow() {
    chatState.isOpen = false;
    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow) {
        chatWindow.classList.remove('active');
    }
    
    // Close WebSocket connection
    if (chatState.chatSocket) {
        chatState.chatSocket.close();
        chatState.chatSocket = null;
    }
    
    showChatList();
}

// Minimize Chat Window
function minimizeChatWindow() {
    chatState.isMinimized = !chatState.isMinimized;
    const chatWindow = document.getElementById('chatWindow');
    if (chatWindow) {
        if (chatState.isMinimized) {
            chatWindow.classList.add('minimized');
        } else {
            chatWindow.classList.remove('minimized');
        }
    }
}

// Show Chat List
function showChatList() {
    chatState.currentView = 'list';
    chatState.currentRoom = null;
    chatState.currentOtherUserId = null;
    chatState.currentOtherUserAvatar = null;
    chatState.currentIsBot = false;
    
    // Close WebSocket connection
    if (chatState.chatSocket) {
        chatState.chatSocket.close();
        chatState.chatSocket = null;
    }
    
    const listView = document.getElementById('chatListView');
    const detailView = document.getElementById('chatDetailView');
    if (listView) listView.style.display = 'flex';
    if (detailView) detailView.classList.remove('active');
}

// Show Chat Detail
function showChatDetail(roomName, otherUser, isBot = false) {
    console.log('showChatDetail called', roomName, otherUser, 'isBot:', isBot);
    
    if (!roomName || !otherUser) {
        console.error('Missing roomName or otherUser', { roomName, otherUser });
        return;
    }
    
    chatState.currentView = 'detail';
    chatState.currentRoom = roomName;
    chatState.currentOtherUserId = otherUser.user_id;
    chatState.currentOtherUserAvatar = otherUser.avatar || null;
    chatState.currentIsBot = isBot || false;
    
    // Hide list view and show detail view
    const listView = document.getElementById('chatListView');
    const detailView = document.getElementById('chatDetailView');
    const detailName = document.getElementById('chatDetailName');
    
    if (listView) listView.style.display = 'none';
    if (detailView) detailView.classList.add('active');
    if (detailName) detailName.textContent = otherUser.full_name || otherUser.email || 'User';
    
    // Clear previous messages and show loading
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = '<div class="text-center text-muted py-4"><i class="fas fa-spinner fa-spin"></i> Loading messages...</div>';
    }
    

    // Load messages
    loadChatMessages(roomName);
    
    // Connect WebSocket for real-time messaging
    connectWebSocket(roomName);
}

// Load Chat Rooms
function loadChatRooms() {
    if (!window.chatRoomsApiUrl) {
        console.error('chatRoomsApiUrl not defined');
        return Promise.resolve();
    }

    return fetch(window.chatRoomsApiUrl)
        .then(response => response.json())
        .then(data => {
            chatState.chatRooms = data.chat_rooms.map(room => ({
                userId: room.other_user.user_id,
                name: room.other_user.full_name,
                email: room.other_user.email,
                avatar: room.other_user.avatar,
                lastMessage: room.last_message.content,
                time: formatTime(room.last_message.created_at),
                roomName: room.room_name,
                unreadCount: room.unread_count,
                isBot: room.is_bot || false
            }));
            
            renderChatList();
            updateUnreadBadge(data.total_unread);
        })
        .catch(error => {
            console.error('Error loading chat rooms:', error);
            const chatList = document.getElementById('chatList');
            if (chatList) {
                chatList.innerHTML = '<div class="text-center text-muted py-4">Error loading chat list</div>';
            }
        });
}

// Format time
function formatTime(isoString) {
    if (!isoString) return 'Just now';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    if (diffDays < 7) return `${diffDays}d`;
    
    return date.toLocaleDateString('en-US', { day: '2-digit', month: '2-digit' });
}

// Render Chat List
function renderChatList() {
    const chatList = document.getElementById('chatList');
    if (!chatList) return;

    let filteredRooms = chatState.chatRooms;
    
    // Apply search filter
    if (chatState.searchQuery) {
        filteredRooms = filteredRooms.filter(room => 
            room.name.toLowerCase().includes(chatState.searchQuery.toLowerCase())
        );
    }
    
    // Apply read/unread filter
    if (chatState.filter === 'unread') {
        filteredRooms = filteredRooms.filter(room => room.unreadCount > 0);
    }
    
    if (filteredRooms.length === 0) {
        chatList.innerHTML = '<div class="text-center text-muted py-4">No conversations</div>';
        return;
    }
    
    chatList.innerHTML = filteredRooms.map((room, index) => {
        const avatarHtml = room.avatar 
            ? `<img src="${room.avatar}" class="chat-item-avatar" alt="${room.name}">`
            : `<div class="chat-item-avatar-placeholder"><i class="fas fa-user"></i></div>`;
        
        // Store room data in a way that can be accessed by onclick
        const roomDataId = `room_${index}_${Date.now()}`;
        window[roomDataId] = {
            roomName: room.roomName,
            otherUser: {
                full_name: room.name,
                user_id: room.userId,
                email: room.email || '',
                avatar: room.avatar || null
            },
            isBot: room.isBot || false
        };
        
        return `
            <div class="chat-item" onclick="handleChatItemClick('${roomDataId}')">
                ${avatarHtml}
                <div class="chat-item-content">
                    <div class="chat-item-header">
                        <div class="chat-item-name">${escapeHtml(room.name)}</div>
                        <div class="chat-item-time">${room.time}</div>
                    </div>
                    <div class="chat-item-message-row">
                        <div class="chat-item-message">${escapeHtml(room.lastMessage)}</div>
                        ${room.unreadCount > 0 ? `<span class="chat-item-badge">${room.unreadCount}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    const chatCount = document.getElementById('chatCount');
    if (chatCount) chatCount.textContent = filteredRooms.length;
}

// Handle Search
function handleSearch(e) {
    chatState.searchQuery = e.target.value;
    renderChatList();
}

// Load Chat Messages
function loadChatMessages(roomName) {
    // Extract user ID from room name
    const parts = roomName.split('_');
    if (parts.length < 3) {
        console.error('Invalid room name format:', roomName);
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.innerHTML = '<div class="text-center text-muted py-4">Error: Invalid chat room format</div>';
        }
        return;
    }
    
    const userId1 = parseInt(parts[1]);
    const userId2 = parseInt(parts[2]);
    const otherUserId = userId1 === chatState.currentUserId ? userId2 : userId1;
    
    console.log('Loading messages for room:', roomName, 'otherUserId:', otherUserId);
    
    fetch(`/chat/api/messages/${otherUserId}/`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Messages loaded:', data);
            const chatMessages = document.getElementById('chatMessages');
            if (!chatMessages) return;
            
            if (!data.messages || data.messages.length === 0) {
                chatMessages.innerHTML = '<div class="text-center text-muted py-4">No messages yet</div>';
                return;
            }
            
            chatMessages.innerHTML = data.messages.map(msg => {
                const isSent = msg.sender_id === chatState.currentUserId;
                const time = new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
                
                // Get avatar - use sender_avatar from API or fallback
                let avatarUrl = msg.sender_avatar;
                if (!avatarUrl) {
                    if (isSent) {
                        avatarUrl = chatState.currentUserAvatar;
                    } else {
                        avatarUrl = chatState.currentOtherUserAvatar;
                    }
                }
                
                const avatarHtml = avatarUrl 
                    ? `<img src="${avatarUrl}" alt="${escapeHtml(msg.sender_name)}" class="chat-message-avatar">`
                    : `<div class="chat-message-avatar-placeholder"><i class="fas fa-user"></i></div>`;
                
                return `
                    <div class="chat-message-row ${isSent ? 'sent' : 'received'}">
                        ${!isSent ? avatarHtml : ''}
                        <div class="chat-message-content">
                            <div class="chat-message-bubble">${escapeHtml(msg.content)}</div>
                            <div class="chat-message-time">${escapeHtml(msg.sender_name)} - ${time}</div>
                        </div>
                        ${isSent ? avatarHtml : ''}
                    </div>
                `;
            }).join('');
            
            markMessagesAsRead(otherUserId);

            // Scroll to bottom
            setTimeout(() => {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 100);
        })
        .catch(error => {
            console.error('Error loading messages:', error);
            const chatMessages = document.getElementById('chatMessages');
            if (chatMessages) {
                chatMessages.innerHTML = '<div class="text-center text-muted py-4">Error loading messages: ' + escapeHtml(error.message) + '</div>';
            }
        });
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Connect WebSocket
function connectWebSocket(roomName) {
    // Close existing connection if any
    if (chatState.chatSocket) {
        chatState.chatSocket.close();
        chatState.chatSocket = null;
    }
    
    // Create new WebSocket connection
    const isBot = chatState.currentIsBot || false;
    const wsPath = isBot ? '/ws/chat/bot/' : '/ws/chat/private/';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${wsPath}${roomName}/`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    console.log('Is bot room:', isBot);
    
    chatState.chatSocket = new WebSocket(wsUrl);
    
    chatState.chatSocket.onopen = function(e) {
        console.log('WebSocket connected successfully for room:', roomName);
    };
    
    chatState.chatSocket.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            console.log('Received WebSocket message:', data);
            
            // Add message to chat UI (only if from other user, or from bot)
            const isFromBot = data.is_bot || false;
            const isBotRoom = chatState.currentIsBot || false;
            if (data.sender_id && (data.sender_id !== chatState.currentUserId || isBotRoom)) {
                addMessageToChat(data.message, data.username || 'Bot', false, data.sender_id, data.sender_avatar || null);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
            console.error('Raw data:', e.data);
        }
    };
    
    chatState.chatSocket.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
    
    chatState.chatSocket.onclose = function(e) {
        console.log('WebSocket closed', e.code, e.reason);
    };
}

// Add message to chat UI
function addMessageToChat(content, senderName, isSent, senderId, senderAvatar = null) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    // Remove "no messages" placeholder if exists
    const placeholder = chatMessages.querySelector('.text-center.text-muted');
    if (placeholder) {
        placeholder.remove();
    }
    
    // Get avatar
    let avatarUrl = senderAvatar;
    if (!avatarUrl) {
        if (isSent) {
            avatarUrl = chatState.currentUserAvatar;
        } else {
            avatarUrl = chatState.currentOtherUserAvatar;
        }
    }
    
    const avatarHtml = avatarUrl 
        ? `<img src="${avatarUrl}" alt="${escapeHtml(senderName)}" class="chat-message-avatar">`
        : `<div class="chat-message-avatar-placeholder"><i class="fas fa-user"></i></div>`;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message-row ${isSent ? 'sent' : 'received'}`;
    
    const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    
    messageDiv.innerHTML = `
        ${!isSent ? avatarHtml : ''}
        <div class="chat-message-content">
            <div class="chat-message-bubble">${escapeHtml(content)}</div>
            <div class="chat-message-time">${escapeHtml(senderName)} - ${time}</div>
        </div>
        ${isSent ? avatarHtml : ''}
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Send Message
function sendMessage() {
    const input = document.getElementById('chatMessageInput');
    if (!input) return;

    const message = input.value.trim();
    
    if (!message) {
        return;
    }
    
    if (!chatState.currentRoom) {
        console.error('No current room selected');
        alert('Please select a conversation');
        return;
    }
    
    // Show message immediately in UI
    addMessageToChat(message, 'You', true, chatState.currentUserId);
    
    // Send via WebSocket
    if (chatState.chatSocket && chatState.chatSocket.readyState === WebSocket.OPEN) {
        console.log('Sending message via WebSocket:', message);
        chatState.chatSocket.send(JSON.stringify({
            'message': message
        }));
    } else {
        console.warn('WebSocket is not connected, attempting to reconnect...');
        // Try to reconnect
        connectWebSocket(chatState.currentRoom);
        
        // Wait a bit and try again
        setTimeout(() => {
            if (chatState.chatSocket && chatState.chatSocket.readyState === WebSocket.OPEN) {
                chatState.chatSocket.send(JSON.stringify({
                    'message': message
                }));
            } else {
                console.error('WebSocket still not connected, message not sent');
                alert('Unable to connect. Please try again.');
            }
        }, 500);
    }
    
    input.value = '';
}

// Update Unread Badge
function updateUnreadBadge(totalUnread) {
    const badge = document.getElementById('unreadBadge');
    if (!badge) return;

    if (totalUnread > 0) {
        badge.textContent = totalUnread > 99 ? '99+' : totalUnread;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

// Handle chat item click (global function)
window.handleChatItemClick = function(roomDataId) {
    console.log('handleChatItemClick called with roomDataId:', roomDataId);
    const roomData = window[roomDataId];
    if (roomData && roomData.roomName && roomData.otherUser) {
        console.log('Opening chat detail:', roomData);
        showChatDetail(roomData.roomName, roomData.otherUser, roomData.isBot || false);
        // Clean up after a delay to ensure it's used
        setTimeout(() => {
            delete window[roomDataId];
        }, 1000);
    } else {
        console.error('Invalid room data:', roomData);
    }
};

// Mark Messages as Read
function markMessagesAsRead(otherUserId) {
    fetch(`/chat/api/mark-read/${otherUserId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': window.csrfToken,
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Marked ${data.updated} messages as read`);
            // Update unread badge
            loadChatRooms();
        }
    })
    .catch(error => {
        console.error('Error marking messages as read:', error);
    });
}