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
    let sentMessageIds = new Set();
    let processedMessageIds = new Set(); // New set to track all processed message IDs

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
        const currentHost = window.location.host;
        const baseHost = currentHost.includes(':') ? currentHost.split(':')[0] : currentHost;
        const wsPath = `${wsProtocol}${baseHost}:8001/ws/chat/${roomId}/`;

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
                console.log('WebSocket message received:', data);
                
                if (data.type === 'message') {
                    // Extract message ID from either client_message_id or message_id
                    const messageId = data.client_message_id || data.message_id || ('msg_' + Date.now());
                    
                    // Check if we've already processed this message (either sent or received)
                    if (processedMessageIds.has(messageId)) {
                        console.log('Skipping already processed message with ID:', messageId);
                        return;
                    }
                    
                    // Add to processed messages set
                    processedMessageIds.add(messageId);
                    
                    // Also check the old system for backwards compatibility
                    if (data.is_agent && sentMessageIds.has(messageId)) {
                        console.log('Skipping agent own message with ID:', messageId);
                        return;
                    }
                    
                    // For non-agent messages, display them
                    if (!data.is_agent) {
                        const messageObj = {
                            content: data.message,
                            sender_type: 'customer',
                            timestamp: data.timestamp || new Date().toISOString(),
                            message_id: messageId
                        };
                        
                        displayMessage(messageObj);
                        scrollToBottom();
                        
                        // Update the room in the sidebar
                        updateRoomInSidebar(data);
                    }
                    
                    // Clean up after a reasonable time
                    setTimeout(() => {
                        processedMessageIds.delete(messageId);
                        console.log('Removed message ID from processed tracking:', messageId);
                    }, 60000); // 1 minute
                } else if (data.command === 'messages') {
                    // Clear existing messages
                    chatMessages.innerHTML = '';
                    
                    // Display messages
                    data.messages.forEach(message => {
                        // Add message ID to processedMessageIds to prevent duplicates
                        const messageId = message.message_id || message.client_message_id || ('hist_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9));
                        
                        // Skip any messages we've already processed
                        if (processedMessageIds.has(messageId)) {
                            console.log('Skipping duplicate historical message with ID:', messageId);
                            return;
                        }
                        
                        // Track this message ID
                        processedMessageIds.add(messageId);
                        
                        // Display the message
                        displayMessage(message);
                    });
                    
                    scrollToBottom();
                } else if (data.type === 'system') {
                    console.log('System message:', data.message);
                    // Optionally display system messages
                } else if (data.command === 'new_message') {
                    // Legacy format support
                    const message = data.message;
                    
                    // Extract or generate message ID
                    const messageId = message.message_id || message.client_message_id || ('legacy_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9));
                    
                    // Skip if already processed
                    if (processedMessageIds.has(messageId)) {
                        console.log('Skipping duplicate legacy message with ID:', messageId);
                        return;
                    }
                    
                    // Track this message
                    processedMessageIds.add(messageId);
                    
                    // Only display customer messages, not our own
                    if (message.sender_type === 'customer') {
                        displayMessage(message);
                        scrollToBottom();
                        
                        // Update last message in sidebar for this room
                        updateRoomInSidebar(data);
                    }
                    
                    // Clean up tracker after a reasonable time
                    setTimeout(() => {
                        processedMessageIds.delete(messageId);
                    }, 60000);
                } else if (data.type === 'status_update') {
                    // Handle status updates (customer connected, disconnected, away)
                    console.log('Status update received:', data);
                    
                    // Show status in the chat
                    showStatusUpdate(data.status, data.permanent);
                    
                    // If the chat was permanently closed, update the UI
                    if (data.permanent && (data.status === 'closed' || data.status === 'ended')) {
                        markRoomAsClosed(data.room_id || activeRoomId);
                    }
                } else if (data.type === 'close_chat') {
                    // Handle customer closing the chat
                    console.log('Customer closed chat:', data);
                    
                    showStatusUpdate('left', data.permanent);
                    
                    // If permanent close, update the room status
                    if (data.permanent) {
                        markRoomAsClosed(data.room_id || activeRoomId);
                    }
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
        // Create message container with improved styling
        const messageContainer = document.createElement('div');
        messageContainer.classList.add('message-container');
        
        // Determine if this is an agent message or user message
        const isAgent = message.sender_type === 'agent';
        
        // Set appropriate alignment based on sender
        messageContainer.style.display = 'flex';
        messageContainer.style.flexDirection = 'column';
        messageContainer.style.alignItems = isAgent ? 'flex-end' : 'flex-start';
        messageContainer.style.marginBottom = '16px';
        messageContainer.style.width = '100%';
        
        // Add sender avatar if needed
        if (!isAgent) {
            const avatarContainer = document.createElement('div');
            avatarContainer.classList.add('message-avatar');
            avatarContainer.style.width = '32px';
            avatarContainer.style.height = '32px';
            avatarContainer.style.borderRadius = '50%';
            avatarContainer.style.backgroundColor = '#e1e1e1';
            avatarContainer.style.display = 'flex';
            avatarContainer.style.alignItems = 'center';
            avatarContainer.style.justifyContent = 'center';
            avatarContainer.style.marginRight = '8px';
            avatarContainer.style.marginBottom = '4px';
            avatarContainer.style.fontWeight = 'bold';
            avatarContainer.style.fontSize = '14px';
            
            // Get first letter of customer name from active room
            const activeRoom = document.querySelector('.chat-room-item.active');
            if (activeRoom) {
                const customerName = activeRoom.querySelector('.customer-name').textContent;
                avatarContainer.textContent = customerName.charAt(0).toUpperCase();
            } else {
                avatarContainer.textContent = 'U';
            }
            
            const avatarRow = document.createElement('div');
            avatarRow.style.display = 'flex';
            avatarRow.style.alignItems = 'center';
            avatarRow.appendChild(avatarContainer);
            
            // Add sender label
            const senderLabel = document.createElement('div');
            senderLabel.classList.add('sender-label');
            senderLabel.textContent = 'Customer';
            senderLabel.style.fontSize = '12px';
            senderLabel.style.color = '#666';
            senderLabel.style.marginLeft = '8px';
            avatarRow.appendChild(senderLabel);
            
            messageContainer.appendChild(avatarRow);
        }
        
        // Create message bubble with better styling
        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message-bubble');
        messageBubble.classList.add(isAgent ? 'agent-bubble' : 'user-bubble');
        
        // Style the bubble
        messageBubble.style.padding = '10px 14px';
        messageBubble.style.borderRadius = isAgent ? '18px 18px 4px 18px' : '18px 18px 18px 4px';
        messageBubble.style.maxWidth = '80%';
        messageBubble.style.boxShadow = '0 1px 2px rgba(0,0,0,0.1)';
        messageBubble.style.position = 'relative';
        
        // Set background color based on sender
        if (isAgent) {
            messageBubble.style.backgroundColor = '#007bff';
            messageBubble.style.color = 'white';
        } else {
            messageBubble.style.backgroundColor = '#f1f0f0';
            messageBubble.style.color = '#333';
        }
        
        // Add message text
        const messageText = document.createElement('div');
        messageText.classList.add('message-text');
        messageText.textContent = message.content;
        messageText.style.wordBreak = 'break-word';
        messageText.style.lineHeight = '1.4';
        messageBubble.appendChild(messageText);
        
        // Add timestamp
        const timestampEl = document.createElement('div');
        timestampEl.classList.add('message-timestamp');
        const messageDate = new Date(message.timestamp);
        timestampEl.textContent = formatTimestamp(messageDate);
        timestampEl.style.fontSize = '11px';
        timestampEl.style.marginTop = '4px';
        timestampEl.style.textAlign = 'right';
        timestampEl.style.color = isAgent ? 'rgba(255,255,255,0.8)' : '#999';
        messageBubble.appendChild(timestampEl);
        
        // If agent message, add label
        if (isAgent) {
            const agentLabel = document.createElement('div');
            agentLabel.classList.add('sender-label');
            agentLabel.textContent = 'Support Agent';
            agentLabel.style.fontSize = '12px';
            agentLabel.style.color = '#cce5ff';
            agentLabel.style.marginRight = '8px';
            agentLabel.style.marginBottom = '4px';
            agentLabel.style.textAlign = 'right';
            messageContainer.appendChild(agentLabel);
        }
        
        // Add message bubble to container
        messageContainer.appendChild(messageBubble);
        
        // Add message container to chat
        chatMessages.appendChild(messageContainer);
        
        // Scroll to view the new message
        scrollToBottom();
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
            // Generate a unique message ID to track this message
            const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            // Track this message ID in both sets to prevent duplicates
            sentMessageIds.add(messageId);
            processedMessageIds.add(messageId);
            console.log('Sending message with ID:', messageId);
            
            // Add message to UI immediately for better responsiveness
            const now = new Date();
            const messageObj = {
                content: message,
                sender_type: 'agent',
                timestamp: now.toISOString(),
                message_id: messageId  // Store ID on the message
            };
            
            // Display the message in the UI
            displayMessage(messageObj);
            scrollToBottom();
            
            // Then send via WebSocket
            chatSocket.send(JSON.stringify({
                'type': 'message',
                'message': message,
                'is_agent': true,
                'username': 'Support',
                'client_message_id': messageId  // Add ID for tracking
            }));
            
            // Clear input
            chatInput.value = '';
            
            // Automatically remove ID from sent tracking after 30 seconds
            // but keep it in processed for longer
            setTimeout(() => {
                sentMessageIds.delete(messageId);
                console.log('Removed message ID from sent tracking:', messageId);
            }, 30000);
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

    function updateRoomInSidebar(data) {
        const room = document.querySelector(`[data-room-id="${data.room_id}"]`);
        if (room) {
            const lastMessageEl = room.querySelector('.last-message');
            if (lastMessageEl) {
                lastMessageEl.textContent = data.message;
            }
            
            // Update timestamp
            const timestampEl = room.querySelector('.timestamp');
            if (timestampEl) {
                timestampEl.textContent = 'Just now';
            }
            
            // If this is not the active room, show notification and increment unread count
            if (data.room_id !== activeRoomId && data.sender_type === 'customer') {
                // Increment unread badge
                const unreadBadge = room.querySelector('.unread-badge');
                if (unreadBadge) {
                    const currentCount = parseInt(unreadBadge.textContent) || 0;
                    unreadBadge.textContent = currentCount + 1;
                    unreadBadge.style.display = 'flex';
                }
                
                // Show notification
                showNotification(data.customer_name, data.message, data.room_id);
            }
        }
    }

    // Function to show status updates in the chat
    function showStatusUpdate(status, isPermanent) {
        // Create status message element
        const statusContainer = document.createElement('div');
        statusContainer.classList.add('status-update');
        statusContainer.style.textAlign = 'center';
        statusContainer.style.margin = '10px 0';
        statusContainer.style.padding = '5px';
        statusContainer.style.color = '#666';
        statusContainer.style.fontSize = '12px';
        
        let statusMessage = '';
        
        switch(status) {
            case 'away':
                statusMessage = 'Customer is away (switched tabs or minimized browser)';
                statusContainer.style.backgroundColor = '#fff3cd';
                break;
            case 'active':
                statusMessage = 'Customer returned to the chat';
                statusContainer.style.backgroundColor = '#d4edda';
                break;
            case 'closed':
            case 'ended':
                statusMessage = isPermanent ? 'Customer ended the chat session' : 'Customer closed the chat window';
                statusContainer.style.backgroundColor = '#f8d7da';
                break;
            case 'left':
                statusMessage = isPermanent ? 'Customer left the website and ended the chat' : 'Customer navigated to another page';
                statusContainer.style.backgroundColor = '#f8d7da';
                break;
            default:
                statusMessage = `Customer status: ${status}`;
                statusContainer.style.backgroundColor = '#e2e3e5';
        }
        
        statusContainer.textContent = statusMessage;
        chatMessages.appendChild(statusContainer);
        scrollToBottom();
    }
    
    // Function to mark a room as closed in the sidebar
    function markRoomAsClosed(roomId) {
        const room = document.querySelector(`.chat-room-item[data-room-id="${roomId}"]`);
        if (room) {
            // Add visual indication that the room is closed
            room.classList.add('chat-ended');
            
            // Update the status text
            const statusEl = room.querySelector('.chat-status');
            if (statusEl) {
                statusEl.textContent = 'Ended';
                statusEl.style.color = '#dc3545';
            } else {
                // Create status element if it doesn't exist
                const newStatusEl = document.createElement('span');
                newStatusEl.classList.add('chat-status');
                newStatusEl.textContent = 'Ended';
                newStatusEl.style.color = '#dc3545';
                newStatusEl.style.fontSize = '12px';
                newStatusEl.style.marginLeft = '5px';
                
                const customerNameEl = room.querySelector('.customer-name');
                if (customerNameEl) {
                    customerNameEl.parentNode.insertBefore(newStatusEl, customerNameEl.nextSibling);
                } else {
                    room.appendChild(newStatusEl);
                }
            }
            
            // Optional: Move this room to bottom of list
            const parent = room.parentNode;
            parent.appendChild(room);
        }
    }
}); 