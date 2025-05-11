document.addEventListener('DOMContentLoaded', function() {
    const chatRooms = document.querySelectorAll('.chat-room-item');
    const mainChat = document.querySelector('.main-chat');
    const emptyState = document.querySelector('.empty-state');
    const chatMessages = document.querySelector('.chat-messages');
    const chatInput = document.querySelector('.chat-input');
    const sendButton = document.querySelector('.send-button');
    const quickReplies = document.querySelectorAll('.quick-reply');
    
    // WebSocket connection
    let chatSocket = null;
    let activeRoomId = null;
    let notificationTimeout = null;
    let unreadMessages = {};

    // Initialize unread counts
    chatRooms.forEach(room => {
        const roomId = room.getAttribute('data-room-id');
        unreadMessages[roomId] = 0;
    });
    
    // Auto-connect to first room if available
    if (chatRooms.length > 0) {
        const firstRoom = chatRooms[0];
        const roomId = firstRoom.getAttribute('data-room-id');
        activateRoom(roomId);
    }

    // Add function to update connection status visually
    function updateConnectionStatus(status) {
        const agentStatus = document.querySelector('.agent-status');
        if (!agentStatus) return;
        
        agentStatus.classList.remove('online', 'offline', 'connecting');
        
        if (status === 'connected') {
            agentStatus.classList.add('online');
            agentStatus.textContent = 'Online';
        } else if (status === 'disconnected') {
            agentStatus.classList.add('offline');
            agentStatus.textContent = 'Offline';
        } else if (status === 'connecting') {
            agentStatus.classList.add('connecting');
            agentStatus.textContent = 'Connecting...';
        }
    }

    function connectWebSocket(roomId) {
        // Close existing connection if any
        if (chatSocket) {
            chatSocket.close();
        }
        
        // Update status
        updateConnectionStatus('connecting');

        // Create new WebSocket connection
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsPath = `${wsProtocol}${window.location.host}/ws/chat/${roomId}/`;

        try {
            chatSocket = new WebSocket(wsPath);
            console.log('Attempting WebSocket connection to:', wsPath);
            
            chatSocket.onopen = function(e) {
                console.log('WebSocket connection established');
                updateConnectionStatus('connected');
                // Request chat history
                chatSocket.send(JSON.stringify({
                    'command': 'fetch_messages'
                }));
            };

            chatSocket.onmessage = function(e) {
                const data = JSON.parse(e.data);
                
                if (data.command === 'new_message') {
                    displayMessage(data.message);
                    scrollToBottom();
                    
                    // Update last message in sidebar for this room
                    const room = document.querySelector(`[data-room-id="${data.room_id}"]`);
                    if (room) {
                        const lastMessageEl = room.querySelector('.last-message');
                        if (lastMessageEl) {
                            lastMessageEl.textContent = data.message.content;
                        }
                        
                        // Update timestamp
                        const timestampEl = room.querySelector('.timestamp');
                        if (timestampEl) {
                            timestampEl.textContent = 'Just now';
                        }
                        
                        // If this is not the active room, show notification and increment unread count
                        if (data.room_id !== activeRoomId && data.message.sender_type === 'customer') {
                            // Increment unread badge
                            const unreadBadge = room.querySelector('.unread-badge');
                            if (unreadBadge) {
                                const currentCount = parseInt(unreadBadge.textContent) || 0;
                                unreadBadge.textContent = currentCount + 1;
                                unreadBadge.style.display = 'flex';
                            }
                            
                            // Show notification
                            showNotification(data.customer_name, data.message.content, data.room_id);
                        }
                    }
                } else if (data.command === 'messages') {
                    // Clear existing messages
                    chatMessages.innerHTML = '';
                    
                    // Display messages
                    data.messages.forEach(message => {
                        displayMessage(message);
                    });
                    
                    scrollToBottom();
                }
            };

            chatSocket.onclose = function(e) {
                console.log('WebSocket connection closed');
                updateConnectionStatus('disconnected');
                
                // Attempt to reconnect after a short delay
                if (activeRoomId === roomId) {
                    setTimeout(() => {
                        console.log('Attempting to reconnect...');
                        connectWebSocket(roomId);
                    }, 3000);
                }
            };

            chatSocket.onerror = function(e) {
                console.error('WebSocket error:', e);
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
        }
    }

    function displayMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.classList.add('message');
        
        if (message.sender_type === 'agent') {
            messageEl.classList.add('agent');
        } else {
            messageEl.classList.add('user');
        }
        
        const messageContent = document.createElement('div');
        messageContent.classList.add('message-content');
        messageContent.textContent = message.content;
        
        const messageTimestamp = document.createElement('div');
        messageTimestamp.classList.add('message-timestamp');
        
        // Format the timestamp
        const messageDate = new Date(message.timestamp);
        messageTimestamp.textContent = formatTimestamp(messageDate);
        
        messageEl.appendChild(messageContent);
        messageEl.appendChild(messageTimestamp);
        
        chatMessages.appendChild(messageEl);
    }

    function formatTimestamp(date) {
        const now = new Date();
        const diff = now - date;
        
        // If less than 24 hours, show time
        if (diff < 24 * 60 * 60 * 1000) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        // If less than a week, show day and time
        if (diff < 7 * 24 * 60 * 60 * 1000) {
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            return `${days[date.getDay()]} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }
        
        // Otherwise show date
        return date.toLocaleDateString();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage() {
        const message = chatInput.value.trim();
        
        if (message && chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({
                'command': 'new_message',
                'message': message,
                'sender_type': 'agent'
            }));
            
            chatInput.value = '';
        }
    }

    function showNotification(customer, message, roomId) {
        // Clear any existing notification
        if (notificationTimeout) {
            clearTimeout(notificationTimeout);
        }
        
        // Remove existing notification
        const existingNotification = document.querySelector('.notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        // Create notification
        const notification = document.createElement('div');
        notification.classList.add('notification');
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'assertive');
        
        const customerAvatar = document.createElement('div');
        customerAvatar.classList.add('customer-avatar');
        customerAvatar.textContent = customer.charAt(0).toUpperCase();
        
        const notificationContent = document.createElement('div');
        notificationContent.classList.add('notification-content');
        
        const notificationTitle = document.createElement('div');
        notificationTitle.classList.add('notification-title');
        notificationTitle.textContent = `${customer} sent a message`;
        
        const notificationMessage = document.createElement('div');
        notificationMessage.classList.add('notification-message');
        notificationMessage.textContent = message.length > 100 ? message.substring(0, 97) + '...' : message;
        
        notificationContent.appendChild(notificationTitle);
        notificationContent.appendChild(notificationMessage);
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.classList.add('notification-close');
        closeButton.innerHTML = '&times;';
        closeButton.setAttribute('aria-label', 'Close notification');
        closeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        });
        
        notification.appendChild(customerAvatar);
        notification.appendChild(notificationContent);
        notification.appendChild(closeButton);
        
        // Add notification to body
        document.body.appendChild(notification);
        
        // Add click event to notification
        notification.addEventListener('click', function() {
            activateRoom(roomId);
            notification.remove();
            clearTimeout(notificationTimeout);
        });
        
        // Show notification with slight delay for better animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Auto hide after 5 seconds
        notificationTimeout = setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, 5000);
    }

    // Activate room on click
    chatRooms.forEach(room => {
        room.addEventListener('click', function() {
            const roomId = this.getAttribute('data-room-id');
            const customerName = this.querySelector('.customer-name').textContent;
            
            // Update active room
            chatRooms.forEach(r => r.classList.remove('active'));
            this.classList.add('active');
            
            // Clear unread badge
            const unreadBadge = this.querySelector('.unread-badge');
            if (unreadBadge) {
                unreadBadge.textContent = '';
                unreadBadge.style.display = 'none';
            }
            
            // Update header
            const customerHeader = document.querySelector('.customer-header');
            if (customerHeader) {
                const avatar = customerHeader.querySelector('.customer-avatar');
                if (avatar) {
                    avatar.textContent = customerName.charAt(0).toUpperCase();
                }
                
                const name = customerHeader.querySelector('.customer-name');
                if (name) {
                    name.textContent = customerName;
                }
            }
            
            // Show main chat, hide empty state
            mainChat.style.display = 'flex';
            emptyState.style.display = 'none';
            
            // Connect to WebSocket for this room
            activeRoomId = roomId;
            connectWebSocket(roomId);
        });
    });

    // Send message on button click
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    // Send message on Enter key (but allow Shift+Enter for new line)
    if (chatInput) {
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Quick replies
    quickReplies.forEach(reply => {
        reply.addEventListener('click', function() {
            chatInput.value = this.textContent;
            sendMessage();
        });
    });
    
    // Search functionality
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            
            chatRooms.forEach(room => {
                const customerName = room.querySelector('.customer-name').textContent.toLowerCase();
                const lastMessage = room.querySelector('.last-message').textContent.toLowerCase();
                
                if (customerName.includes(query) || lastMessage.includes(query)) {
                    room.style.display = 'flex';
                } else {
                    room.style.display = 'none';
                }
            });
        });
    }
    
    // Mobile responsiveness
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.toggle('show');
        });
    }
    
    // Close button in mobile view
    const closeButton = document.querySelector('.close-sidebar');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.remove('show');
        });
    }

    // Activate chat room and load messages
    function activateRoom(roomId) {
        // Deactivate current room if any
        if (activeRoomId) {
            const currentRoom = document.querySelector(`.chat-room-item[data-room-id="${activeRoomId}"]`);
            currentRoom.classList.remove('active');
            
            // Close current WebSocket connection
            if (chatSocket) {
                chatSocket.close();
            }
        }
        
        // Reset unread count for this room
        if (unreadMessages[roomId]) {
            unreadMessages[roomId] = 0;
            const unreadBadge = document.querySelector(`.chat-room-item[data-room-id="${roomId}"] .unread-badge`);
            if (unreadBadge) {
                unreadBadge.textContent = '';
                unreadBadge.style.display = 'none';
            }
        }
        
        // Activate new room
        activeRoomId = roomId;
        const newActiveRoom = document.querySelector(`.chat-room-item[data-room-id="${roomId}"]`);
        newActiveRoom.classList.add('active');
        
        // Update chat header
        const customerName = newActiveRoom.querySelector('.customer-name').textContent;
        document.querySelector('.customer-header .customer-name').textContent = customerName;
        
        // Clear current messages
        chatMessages.innerHTML = '';
        
        // Hide sidebar on mobile after selection
        if (window.innerWidth < 768) {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.remove('show');
        }
        
        // Load chat history
        fetchChatHistory(roomId);
        
        // Connect to WebSocket
        connectWebSocket(roomId);
    }
    
    function fetchChatHistory(roomId) {
        fetch(`/livechat/api/messages/${roomId}/`)
            .then(response => response.json())
            .then(data => {
                data.forEach(message => {
                    displayMessage(message);
                });
                scrollToBottom();
            })
            .catch(error => console.error('Error fetching chat history:', error));
    }
}); 