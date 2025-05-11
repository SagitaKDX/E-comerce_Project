console.log('[DEBUG] floating_chat.js script is being parsed.');

(function() {
    'use strict';
    
    console.log('[DEBUG floating_chat.js] IIFE Started.');
    
    // Clear stale session data on initial load
    clearStaleSessionData();
    
    if (window.floatingChatInitialized) {
        console.log('[DEBUG floating_chat.js] Chat already initialized, skipping.');
        return;
    }
    
    window.floatingChatInitialized = true;
    console.log('[DEBUG floating_chat.js] window.floatingChatInitialized set to: true');
    
    // WebSocket reference and session variables
    let chatSocket = null;
    let chatSessionId = null;
    let heartbeatInterval = null;
    let reconnectAttempts = 0;
    let isReconnecting = false;
    let reconnectTimeout = null;
    const maxReconnectAttempts = 3; // Reduce max reconnect attempts from 5 to 3
    
    // More reliable way to initialize the chat
    // Check if DOM is already loaded
    if (document.readyState === 'loading') {
        console.log('[DEBUG floating_chat.js] Setting up initializeChat trigger for DOMContentLoaded');
        document.addEventListener('DOMContentLoaded', initializeChat);
    } else {
        console.log('[DEBUG floating_chat.js] Setting up initializeChat trigger for setTimeout');
        // DOM already loaded, give extra time for other scripts to complete
        setTimeout(initializeChat, 100);
    }
    
    // Check again after a delay to ensure chat is initialized
    setTimeout(function() {
        if (!window.floatingChatInitialized) {
            console.log('[DEBUG floating_chat.js] Initialization check failed, trying again');
            initializeChat();
        }
    }, 1500);
    
    console.log('[DEBUG floating_chat.js] Setting up initializeChat trigger...');
    
    // Function to generate a unique session ID if one doesn't exist
    function generateChatSessionId() {
        // Try to retrieve from localStorage first (persist across page refresh)
        let sessionId = localStorage.getItem('chat_session_id');
        
        // If session ID starts with 'new-', it's a temporary emergency ID
        // Replace it with a proper UUID
        if (sessionId && sessionId.startsWith('new-')) {
            console.log('[DEBUG floating_chat.js] Replacing temporary session ID');
            localStorage.removeItem('chat_session_id');
            sessionId = null;
        }
        
        if (!sessionId) {
            // Generate a UUID-like identifier
            sessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
            localStorage.setItem('chat_session_id', sessionId);
            console.log('[DEBUG floating_chat.js] Generated new chat session ID:', sessionId);
        } else {
            console.log('[DEBUG floating_chat.js] Retrieved existing chat session ID:', sessionId);
        }
        
        return sessionId;
    }
    
    // Function to handle page unload/close events
    function setupPageUnloadHandler() {
        window.addEventListener('beforeunload', function(e) {
            // Clean up WebSocket connections
            if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || 
                            chatSocket.readyState === WebSocket.CONNECTING)) {
                console.log('[DEBUG floating_chat.js] Page unloading, closing WebSocket and clearing session');
                
                // Send a "user_leaving" message to the server
                if (chatSocket.readyState === WebSocket.OPEN) {
                    safeSend({
                        'type': 'close_chat',
                        'session_id': chatSessionId,
                        'reason': 'page_unload',
                        'permanent': true
                    });
                }
                
                // Close the WebSocket connection
                chatSocket.close(1000, 'User left page');
                
                // Clear heartbeat interval
                if (heartbeatInterval) {
                    clearInterval(heartbeatInterval);
                }
                
                // Clear chat session data
                clearChatSession();
            }
        });
        
        // Also handle visibility change to detect when user switches tabs or minimizes
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'hidden') {
                console.log('[DEBUG floating_chat.js] Page hidden, sending status update');
                // Notify server the user is away but don't close the session
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    safeSend({
                        'type': 'status_update',
                        'session_id': chatSessionId,
                        'status': 'away',
                        'permanent': false
                    });
                }
            } else if (document.visibilityState === 'visible') {
                console.log('[DEBUG floating_chat.js] Page visible again, sending status update');
                // Notify server the user is back
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    safeSend({
                        'type': 'status_update',
                        'session_id': chatSessionId,
                        'status': 'active',
                        'permanent': false
                    });
                }
            }
        });
    }
    
    // Function to clear chat session data
    function clearChatSession() {
        console.log('[DEBUG floating_chat.js] Clearing chat session data');
        localStorage.removeItem('chat_session_id');
        localStorage.removeItem('lastMessageTime');
        
        // Clear any stored message cache or other chat-related data
        chatSessionId = null;
        reconnectAttempts = 0;
        isReconnecting = false;
        
        // Clear any pending reconnect attempts
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
    }
    
    function initializeChat() {
        console.log('[DEBUG floating_chat.js] initializeChat() called.');
        
        // Set up page unload handler
        setupPageUnloadHandler();
        
        // Element references - get only once
        const chatToggleBtn = document.getElementById('chat-toggle-btn');
        const chatPanel = document.getElementById('chat-panel');
        const chatForm = document.getElementById('chat-message-form');
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('chat-send-btn');
        const minimizeBtn = document.getElementById('chat-minimize-btn');
        const closeBtn = document.getElementById('chat-close-btn');
        const chatMessages = document.getElementById('chat-messages');
        const welcomeBtn = document.getElementById('welcome-start-chat-btn');
        const initialWelcome = document.getElementById('initial-welcome');
        const chatActive = document.getElementById('chat-active');
        const chatInputContainer = document.querySelector('.chat-input-container');
        const chatStatus = document.getElementById('chat-status');
        const subjectSelectionState = document.getElementById('subject-selection');
        const subjectForm = document.getElementById('subject-form');
        const chatEmailInput = document.getElementById('chat-email');
        const waitingState = document.getElementById('waiting-state');
        const connectionStatus = document.getElementById('chat-connection-status');
        
        // Debug logging
        console.log('[DEBUG floating_chat.js] Chat elements found:', {
            chatToggleBtn: !!chatToggleBtn,
            chatPanel: !!chatPanel,
            chatForm: !!chatForm,
            chatInput: !!chatInput,
            sendButton: !!sendButton,
            chatMessages: !!chatMessages,
            welcomeBtn: !!welcomeBtn,
            initialWelcome: !!initialWelcome,
            chatActive: !!chatActive,
            chatInputContainer: !!chatInputContainer,
            chatStatus: !!chatStatus,
            subjectSelectionState: !!subjectSelectionState,
            subjectForm: !!subjectForm,
            chatEmailInput: !!chatEmailInput,
            waitingState: !!waitingState,
            connectionStatus: !!connectionStatus
        });
        
        // Early check if all essential elements are found
        if (!chatToggleBtn || !chatPanel || !chatForm || !chatInput || 
            !sendButton || !chatMessages || !chatActive || !initialWelcome || !welcomeBtn) {
            console.error('[DEBUG floating_chat.js] Floating chat initialization failed: Critical UI elements not found');
            if (!chatToggleBtn) console.error('- chatToggleBtn missing');
            if (!chatPanel) console.error('- chatPanel missing');
            if (!chatForm) console.error('- chatForm missing');
            if (!chatInput) console.error('- chatInput missing');
            if (!sendButton) console.error('- sendButton missing');
            if (!chatMessages) console.error('- chatMessages missing');
            if (!chatActive) console.error('- chatActive missing');
            if (!initialWelcome) console.error('- initialWelcome missing');
            if (!welcomeBtn) console.error('- welcomeBtn missing');
            return;
        }
        
        // Set initial state - start with welcome view
        initialWelcome.classList.add('active');
        chatActive.classList.remove('active');
        chatActive.style.display = 'none';
        
        if (waitingState) {
            waitingState.classList.remove('active');
            waitingState.style.display = 'none';
        }
        
        // Initialize chat status if available
        if (chatStatus) {
            updateChatStatus('Offline', 'offline');
        }
        
        // Show connection status element if available
        if (connectionStatus) {
            connectionStatus.style.display = 'none';
        }
        
        // Enable chat inputs initially (will be disabled if needed by WebSocket state)
        if (chatInput) chatInput.disabled = false;
        if (sendButton) sendButton.disabled = false;
        
        // Function to ensure chat toggle button is properly displayed
        function resetChatToggleButton() {
            if (chatToggleBtn) {
                chatToggleBtn.style.display = 'flex';
            }
        }
        
        // 1. Open/close chat panel when toggle button is clicked
        chatToggleBtn.addEventListener('click', function() {
            console.log('[DEBUG floating_chat.js] Toggle button CLICKED!');
            const isActive = chatPanel.classList.toggle('active');
            
            if (isActive) {
                console.log('[DEBUG floating_chat.js] Chat panel opened');
                if (chatInput) chatInput.focus();
                // Only connect if we're already in chat active state
                if (chatActive.classList.contains('active')) {
                    connectWebSocket();
                }
                
                // Hide toggle button on mobile when chat is opened
                if (window.innerWidth <= 768) {
                    chatToggleBtn.style.display = 'none';
                }
            } else {
                console.log('[DEBUG floating_chat.js] Chat panel closed');
                disconnectWebSocket();
                
                // Always make sure the toggle button is visible when chat is closed
                resetChatToggleButton();
            }
        });
        
        // 2. Minimize chat when minimize button is clicked
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', function() {
                console.log('[DEBUG floating_chat.js] Minimize button clicked');
                chatPanel.classList.remove('active');
                disconnectWebSocket();
                
                // Always make sure the toggle button is visible when chat is minimized
                resetChatToggleButton();
            });
        }
        
        // 3. Close chat when close button is clicked
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                console.log('[DEBUG floating_chat.js] Close button clicked');
                
                // Notify server that chat is being closed permanently
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    safeSend({
                        'type': 'close_chat',
                        'session_id': chatSessionId,
                        'permanent': true,
                        'reason': 'user_closed'
                    });
                }
                
                chatPanel.classList.remove('active');
                disconnectWebSocket();
                
                // Always make sure the toggle button is visible when chat is closed
                resetChatToggleButton();
                
                // Clear chat session completely to start fresh next time
                chatMessages.innerHTML = ''; // Clear messages
                chatActive.classList.remove('active');
                chatActive.style.display = 'none';
                initialWelcome.classList.add('active');
                initialWelcome.style.display = 'block';
                
                if (connectionStatus) {
                    connectionStatus.style.display = 'none';
                }
            });
        }
        
        // 4. Start chat workflow when welcome button is clicked
        if (welcomeBtn) {
            welcomeBtn.addEventListener('click', function() {
                console.log('[DEBUG floating_chat.js] Welcome button clicked, transitioning to subject selection state');
                
                // Hide welcome
                initialWelcome.classList.remove('active');
                initialWelcome.style.display = 'none';
                
                // Show subject selection state
                if (subjectSelectionState) {
                    subjectSelectionState.classList.add('active');
                    subjectSelectionState.style.display = 'flex';
                    console.log('[DEBUG floating_chat.js] Subject selection state activated');
                } else {
                    console.error('[DEBUG floating_chat.js] Subject selection state element not found!');
                    // Fallback: Go directly to waiting state
                    showWaitingState();
                }
            });
        }
        
        // 4b. Handle Subject Form Submission
        if (subjectForm) {
            subjectForm.addEventListener('submit', function(e) {
                e.preventDefault();
                console.log('[DEBUG floating_chat.js] Subject form submitted');
                
                const selectedSubjectRadio = subjectForm.querySelector('input[name="subject"]:checked');
                const subject = selectedSubjectRadio ? selectedSubjectRadio.value : 'General Inquiry';
                const email = chatEmailInput ? chatEmailInput.value.trim() : null;
                
                console.log(`[DEBUG floating_chat.js] Subject selected: ${subject}, Email: ${email || 'N/A'}`);
                
                // Hide subject selection
                subjectSelectionState.classList.remove('active');
                subjectSelectionState.style.display = 'none';
                
                // Show waiting state before activating chat
                showWaitingState(subject, email);
            });
        }
        
        // Function to show waiting state
        function showWaitingState(subject = 'General Inquiry', email = null) {
            console.log('[DEBUG floating_chat.js] Showing waiting state');
            
            if (waitingState) {
                waitingState.classList.add('active');
                waitingState.style.display = 'flex';
                
                // Store subject/email for later
                waitingState.dataset.subject = subject;
                waitingState.dataset.email = email;
                
                // Connect WebSocket to notify agents
                createChatSession(subject, email);
                
                // Set a timeout to transition to active chat after a short delay
                // In a real app, this would happen when an agent connects
                setTimeout(() => {
                    // Simulate agent accepting the chat
                    waitingState.classList.remove('active');
                    waitingState.style.display = 'none';
                    
                    // Activate the chat UI
                    activateChatActiveState(subject, email);
                }, 3000); // 3 second delay for demonstration
            } else {
                console.error('[DEBUG floating_chat.js] Waiting state element not found. Going directly to chat.');
                activateChatActiveState(subject, email);
            }
        }
        
        // Function to create a new chat session
        function createChatSession(subject, email) {
            console.log('[DEBUG floating_chat.js] Creating new chat session');
            
            // Generate a new chat session ID
            chatSessionId = generateChatSessionId();
            
            // Connect to notification WebSocket to alert agents
            fetch('/livechat/api/create_session/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    subject: subject,
                    email: email,
                    session_id: chatSessionId
                })
            })
            .then(response => {
                if (!response.ok) {
                    // If we get a server error, clear the stored session ID
                    // This helps resolve duplicate key issues
                    console.error('[DEBUG floating_chat.js] Server error creating session, clearing stored ID');
                    localStorage.removeItem('chat_session_id');
                    
                    // Generate a completely new ID with timestamp to avoid collisions
                    chatSessionId = 'new-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                    console.log('[DEBUG floating_chat.js] Generated emergency session ID:', chatSessionId);
                    
                    return { success: false, error: `Status: ${response.status}` };
                }
                return response.json();
            })
            .then(data => {
                console.log('[DEBUG floating_chat.js] Chat session created:', data);
                if (data.success !== false) {
                if (data.session_id) {
                    chatSessionId = data.session_id;
                    localStorage.setItem('chat_session_id', chatSessionId);
                    }
                } else {
                    // If server returned success: false, ensure we don't store this failed ID
                    console.warn('[DEBUG floating_chat.js] Failed to create chat session:', data.error);
                    // Don't store the ID that caused the error
                    localStorage.removeItem('chat_session_id');
                }
            })
            .catch(error => {
                console.error('[DEBUG floating_chat.js] Error creating chat session:', error);
                // Don't store the ID that caused the error
                localStorage.removeItem('chat_session_id');
            });
        }
        
        // Function to get CSRF token
        function getCsrfToken() {
            const csrfCookie = document.cookie.split(';')
                .map(cookie => cookie.trim())
                .find(cookie => cookie.startsWith('csrftoken='));
                
            return csrfCookie ? csrfCookie.split('=')[1] : '';
        }
        
        // Function to activate the main chat interface
        function activateChatActiveState(subject = 'General Inquiry', email = null) {
            console.log('[DEBUG floating_chat.js] Activating chat active state');
            
            // Show chat active - with multiple approaches to ensure it works
            chatActive.classList.add('active');
            chatActive.style.display = 'flex';
            chatActive.style.visibility = 'visible';
            chatActive.style.opacity = '1';
            chatActive.style.height = '100%';
            
            // Show connection status if available
            if (connectionStatus) {
                connectionStatus.style.display = 'flex';
                const statusText = connectionStatus.querySelector('.status-text');
                const statusIndicator = connectionStatus.querySelector('.status-indicator');
                
                if (statusText) statusText.textContent = 'Connecting...';
                if (statusIndicator) {
                    statusIndicator.className = 'status-indicator waiting';
                }
            }
            
            // Force chat input container visibility
            if (chatInputContainer) {
                chatInputContainer.style.display = 'block';
                chatInputContainer.style.visibility = 'visible';
                chatInputContainer.style.opacity = '1';
                console.log('[DEBUG floating_chat.js] Input container styles applied');
            }
            
            // Force chat form visibility
            if (chatForm) {
                chatForm.style.display = 'flex';
                chatForm.style.visibility = 'visible';
                chatForm.style.opacity = '1';
                console.log('[DEBUG floating_chat.js] Form styles applied');
            }
            
            // Force chat input and button visibility but disabled until agent accepts
            if (chatInput) {
                chatInput.style.display = 'block';
                chatInput.style.visibility = 'visible';
                chatInput.disabled = true;
                chatInput.placeholder = 'Waiting for agent to accept chat...';
                console.log('[DEBUG floating_chat.js] Input styles applied');
            }
            
            if (sendButton) {
                sendButton.style.display = 'flex';
                sendButton.style.visibility = 'visible';
                sendButton.disabled = true;
                console.log('[DEBUG floating_chat.js] Button styles applied');
            }
            
            // Connect to WebSocket, potentially passing subject/email
            connectWebSocket();
            
            // Try to load previous messages if this is a returning user
            if (chatSessionId) {
                fetchPreviousMessages(chatSessionId);
            }
            
            // Debug final state
            console.log('[DEBUG floating_chat.js] After transition - chatActive is visible:', 
                chatActive.style.display, 
                'input container visible:', 
                chatInputContainer.style.display);
        }
        
        // 5. Send message when form is submitted
        if (chatForm) {
            chatForm.addEventListener('submit', function(e) {
                e.preventDefault();
                console.log('[DEBUG floating_chat.js] Form submitted');
                
                const message = chatInput.value.trim();
                if (message) {
                    console.log('[DEBUG floating_chat.js] Sending message:', message);
                    
                    // Send message via WebSocket if connected
                    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                        safeSend({
                            'type': 'chat_message',
                            'message': message,
                            'sender': 'user',
                            'session_id': chatSessionId
                        });
                        
                        // Add user message to chat UI immediately for responsive UX
                        addMessage('You', message, false);
                    } else {
                        console.warn('[DEBUG floating_chat.js] Cannot send message: WebSocket not connected');
                        showChatHint('Message not sent. Connection offline.');
                        
                        // Attempt to reconnect
                        connectWebSocket();
                    }
                    
                    // Clear input and focus it again
                    chatInput.value = '';
                    chatInput.focus();
                }
            });
        }
        
        // Additional click handler for the send button
        if (sendButton) {
            sendButton.addEventListener('click', function(e) {
                console.log('[DEBUG floating_chat.js] Send button clicked');
                e.preventDefault();
                
                // Trigger the form submit event
                if (chatForm) {
                    chatForm.dispatchEvent(new Event('submit'));
                } else {
                    // Fallback if form reference is lost
                    const message = chatInput.value.trim();
                    if (message) {
                        // Send message via WebSocket if connected
                        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                            safeSend({
                                'type': 'chat_message',
                                'message': message,
                                'sender': 'user',
                                'session_id': chatSessionId
                            });
                            
                            // Add user message to chat UI
                            addMessage('You', message, false);
                        } else {
                            showChatHint('Message not sent. Connection offline.');
                            connectWebSocket(); // Attempt to reconnect
                        }
                        
                        chatInput.value = '';
                        chatInput.focus();
                    }
                }
            });
        }
        
        // Force visibility of all chat elements periodically
        const forceVisibility = function() {
            if (chatActive && chatActive.classList.contains('active')) {
                chatActive.style.display = 'flex';
                chatActive.style.visibility = 'visible';
                chatActive.style.opacity = '1';
                
                if (chatInputContainer) {
                    chatInputContainer.style.display = 'block';
                    chatInputContainer.style.visibility = 'visible';
                    chatInputContainer.style.opacity = '1';
                }
                
                if (chatForm) {
                    chatForm.style.display = 'flex';
                    chatForm.style.visibility = 'visible';
                    chatForm.style.opacity = '1';
                }
                
                if (chatInput) {
                    chatInput.style.display = 'block';
                    chatInput.style.visibility = 'visible';
                }
                
                if (sendButton) {
                    sendButton.style.display = 'flex';
                    sendButton.style.visibility = 'visible';
                }
            }
        };
        
        // Call initially and set interval
        setTimeout(forceVisibility, 500);
        setInterval(forceVisibility, 2000);
        
        // WebSocket Connection Functions
        function connectWebSocket() {
            // Cannot connect without a session ID
            if (!chatSessionId) {
                chatSessionId = generateChatSessionId();
            }
            
            // Prevent multiple connections
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                console.log('[DEBUG floating_chat.js] WebSocket already connected.');
                updateConnectionStatus('connected');
                return;
            }
            if (chatSocket && chatSocket.readyState === WebSocket.CONNECTING) {
                console.log('[DEBUG floating_chat.js] WebSocket connection already in progress.');
                return;
            }

            // Don't attempt to reconnect if we've hit the limit
            if (reconnectAttempts >= maxReconnectAttempts) {
                console.log('[DEBUG floating_chat.js] Maximum reconnection attempts reached. Stopping reconnection.');
                updateConnectionStatus('error');
                return;
            }

            // Set reconnecting flag to prevent multiple connection attempts
            if (isReconnecting) {
                console.log('[DEBUG floating_chat.js] Already attempting to reconnect, skipping.');
                return;
            }
            
            isReconnecting = true;
            console.log(`[DEBUG floating_chat.js] Attempting to connect WebSocket for session: ${chatSessionId}`);
            updateChatStatus('Connecting...', 'connecting');
            updateConnectionStatus('connecting');
            
            // Get protocol (ws or wss)
            const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            
            // Try to detect the correct host for connection
            const currentHost = window.location.host;
            let wsHost = currentHost;
            
            // Replace localhost with 127.0.0.1 to avoid DNS issues
            wsHost = wsHost.replace('localhost', '127.0.0.1');
            
            // Create the base host without port
            const baseHost = wsHost.includes(':') ? wsHost.split(':')[0] : wsHost;
            
            // Try port 8001 first (Daphne ASGI server), then fall back to current port
            let wsUrl = `${wsProtocol}${baseHost}:8001/ws/chat/${chatSessionId}/`;
            
            // Log all the details of the connection we're trying to make
            console.log('[DEBUG floating_chat.js] Connecting details:', {
                protocol: wsProtocol,
                originalHost: currentHost,
                wsHost: wsHost,
                baseHost: baseHost,
                wsUrl: wsUrl,
                connectionAttempt: reconnectAttempts + 1
            });
            
            console.log('[DEBUG floating_chat.js] Connecting to:', wsUrl);

            try {
                chatSocket = new WebSocket(wsUrl);

                chatSocket.onopen = function(e) {
                    console.log('[DEBUG floating_chat.js] WebSocket connection opened successfully.');
                    updateChatStatus('Connected', 'online');
                    updateConnectionStatus('connected');
                    chatInput.disabled = false;
                    sendButton.disabled = false;
                    
                    // Send initial connection message
                    safeSend({
                        'type': 'chat_connect', 
                        'session_id': chatSessionId
                    });
                    
                    // Set up heartbeat to keep connection alive
                    setupHeartbeat();
                };

                chatSocket.onclose = function(e) {
                    console.warn(`[DEBUG floating_chat.js] WebSocket closed. Code: ${e.code}, Reason: ${e.reason || 'No reason provided'}, wasClean: ${e.wasClean}`);
                    updateChatStatus('Disconnected', 'offline');
                    updateConnectionStatus('disconnected');
                    chatInput.disabled = true;
                    sendButton.disabled = true;
                    
                    // Clear heartbeat interval
                    if (heartbeatInterval) {
                        clearInterval(heartbeatInterval);
                        heartbeatInterval = null;
                    }
                    
                    // Reset reconnection flag
                    isReconnecting = false;
                    
                    // Attempt to reconnect after a delay if closing was not intentional
                    // but only if we haven't exceeded max attempts and we're not trying to close the connection explicitly
                    if (e.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                        if (chatActive.classList.contains('active')) {
                            reconnectAttempts++;
                            
                            // Exponential backoff: 2s, 4s, 8s
                            const delay = 2000 * Math.pow(2, reconnectAttempts - 1);
                            console.log(`[DEBUG floating_chat.js] Will try to reconnect in ${delay/1000} seconds (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
                            
                            // Show reconnection hint to user
                            showChatHint(`Connection lost. Reconnecting in ${delay/1000}s (Attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
                            
                            // Update connection status with reconnect countdown
                            const statusText = connectionStatus.querySelector('.status-text');
                            if (statusText) {
                                statusText.textContent = `Reconnecting in ${delay/1000}s (${reconnectAttempts}/${maxReconnectAttempts})`;
                            }
                            
                            reconnectTimeout = setTimeout(function() {
                                reconnectTimeout = null;
                                connectWebSocket();
                            }, delay);
                        }
                    } else if (reconnectAttempts >= maxReconnectAttempts) {
                        console.log('[DEBUG floating_chat.js] Maximum reconnection attempts reached.');
                        updateConnectionStatus('error');
                        
                        // Display message to user
                        showChatHint('Could not connect to chat server after multiple attempts. Please try again later or refresh the page.');
                    }
                    
                    chatSocket = null;
                };

                chatSocket.onerror = function(e) {
                    console.error('[DEBUG floating_chat.js] WebSocket error observed:', e);
                    updateChatStatus('Connection Error', 'error');
                    updateConnectionStatus('error');
                    
                    // Show error as a hint to the user
                    showChatHint('Connection error. Please check your internet connection.');
                    
                    // No need to disable inputs here as onclose will be called
                };

                chatSocket.onmessage = function(e) {
                    console.log('[DEBUG floating_chat.js] Message received:', e.data);
                    
                    try {
                        const data = JSON.parse(e.data);
                        console.log('[DEBUG floating_chat.js] Parsed message data:', data);
                        
                        // Handle AsyncToSync errors specifically
                        if (data.type === 'error' && data.message && 
                            (data.message.includes('AsyncToSync') || data.message.includes('async event loop'))) {
                            console.error('[DEBUG floating_chat.js] AsyncToSync error detected');
                            handleAsyncError();
                            return;
                        }
                        
                        // Try to ensure chat-messages element exists before attempting to add message
                        const chatMessages = document.getElementById('chat-messages');
                        if (!chatMessages) {
                            console.error('[DEBUG floating_chat.js] chat-messages element not found! Forcing element refresh...');
                            // Force a refresh of the chat UI
                            if (chatActive && chatActive.classList.contains('active')) {
                                forceVisibility(); // Call visibility function to try to restore UI
                                setTimeout(() => {
                                    // Retry adding the message after a small delay
                                    handleMessageData(data);
                                }, 100);
                                return;
                            }
                        }
                        
                        // If we got here, proceed with handling the message
                        handleMessageData(data);
                    } catch (error) {
                        console.error('[DEBUG floating_chat.js] Error parsing message:', error, e.data);
                        
                        // Special handling for AsyncToSync errors that might be in raw text
                        if (typeof e.data === 'string' && 
                            (e.data.includes('AsyncToSync') || e.data.includes('async event loop'))) {
                            console.error('[DEBUG floating_chat.js] Raw AsyncToSync error detected');
                            handleAsyncError();
                        }
                    }
                };

            } catch (error) {
                console.error('[DEBUG floating_chat.js] Failed to create WebSocket:', error);
                updateChatStatus('Failed to connect', 'error');
                updateConnectionStatus('error');
                
                // Clean up failed connection
                chatSocket = null;
            }
        }
        
        // Handle AsyncToSync errors specifically
        function handleAsyncError() {
            showChatHint('Server connection issue detected. Refreshing connection...');
            
            // Disconnect and reconnect with a delay
            disconnectWebSocket();
            
            // Reset counter and try again with a clean connection
            reconnectAttempts = 0;
            setTimeout(() => {
                connectWebSocket();
            }, 2000);
        }
        
        // Safe send function to handle connection issues
        function safeSend(data) {
            if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
                console.error('[DEBUG floating_chat.js] Cannot send message: WebSocket not connected');
                
                // Try to reconnect and queue the message
                if (!isReconnecting && reconnectAttempts < maxReconnectAttempts) {
                    connectWebSocket();
                }
                return false;
            }
            
            try {
                chatSocket.send(JSON.stringify(data));
                return true;
            } catch (error) {
                console.error('[DEBUG floating_chat.js] Error sending message:', error);
                return false;
            }
        }
        
        // Set up heartbeat to keep connection alive
        function setupHeartbeat() {
            if (heartbeatInterval) {
                clearInterval(heartbeatInterval);
            }
            
            // Send ping every 30 seconds to keep connection alive
            heartbeatInterval = setInterval(() => {
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    console.log('[DEBUG floating_chat.js] Sending heartbeat ping');
                    safeSend({
                        'type': 'ping',
                        'session_id': chatSessionId
                    });
                } else {
                    clearInterval(heartbeatInterval);
                    heartbeatInterval = null;
                }
            }, 30000); // 30 seconds
        }
        
        // Update the connection status indicator if present
        function updateConnectionStatus(status) {
            if (!connectionStatus) return;
            
            // Remove any existing reconnect buttons to prevent duplicates
            const existingReconnectBtns = connectionStatus.querySelectorAll('.reconnect-btn');
            existingReconnectBtns.forEach(btn => btn.remove());
            
            connectionStatus.style.display = 'flex';
            const statusText = connectionStatus.querySelector('.status-text');
            const statusIndicator = connectionStatus.querySelector('.status-indicator');
            
            if (statusText && statusIndicator) {
                switch (status) {
                    case 'connected':
                        statusText.textContent = 'Connected';
                        statusIndicator.className = 'status-indicator connected';
                        break;
                    case 'connecting':
                        statusText.textContent = 'Connecting...';
                        statusIndicator.className = 'status-indicator waiting';
                        break;
                    case 'disconnected':
                        statusText.textContent = 'Disconnected';
                        statusIndicator.className = 'status-indicator disconnected';
                        break;
                    case 'error':
                        statusText.textContent = 'Connection Error';
                        statusIndicator.className = 'status-indicator disconnected';
                        
                        // Add only one reconnect button
                        const reconnectBtn = document.createElement('button');
                        reconnectBtn.className = 'reconnect-btn';
                        reconnectBtn.textContent = 'Reconnect';
                            reconnectBtn.addEventListener('click', function() {
                            // Prevent multiple clicks
                            this.disabled = true;
                            this.textContent = 'Connecting...';
                            
                            // Reset reconnect attempts and try to connect
                            reconnectAttempts = 0;
                                connectWebSocket();
                            
                            // Re-enable the button after a delay
                            setTimeout(() => {
                                this.disabled = false;
                                this.textContent = 'Reconnect';
                            }, 3000);
                        });
                        connectionStatus.appendChild(reconnectBtn);
                        break;
                }
            }
        }

        function disconnectWebSocket() {
            if (chatSocket) {
                console.log('[DEBUG floating_chat.js] Closing WebSocket connection.');
                
                // Send a clean closing message
                if (chatSocket.readyState === WebSocket.OPEN) {
                    safeSend({
                        'type': 'close_chat',
                        'session_id': chatSessionId,
                        'permanent': false
                    });
                }
                
                // Close with "normal closure" code
                chatSocket.close(1000, 'User closed chat panel');
                
                // Clear heartbeat
                if (heartbeatInterval) {
                    clearInterval(heartbeatInterval);
                    heartbeatInterval = null;
                }
            }
            
            chatSocket = null;
            updateChatStatus('Offline', 'offline');
            updateConnectionStatus('disconnected');
            
            if (chatInput) chatInput.disabled = true;
            if (sendButton) sendButton.disabled = true;
        }

        function updateChatStatus(statusText, statusClass) {
            if (chatStatus) {
                chatStatus.textContent = statusText;
                chatStatus.className = `chat-subtitle status-${statusClass}`;
                console.log('[DEBUG floating_chat.js] Chat status updated:', statusText);
            }
        }
        
        // Extract message handling to a separate function for better organization
        function handleMessageData(data) {
            // Handle different message types
            if (data.type === 'system') {
                console.log('[DEBUG floating_chat.js] System message received:', data.message);
                
                // Use showChatHint for all system messages instead of chat bubbles
                showChatHint(data.message);
            } 
            else if (data.type === 'status_update') {
                console.log('[DEBUG floating_chat.js] Status update received:', data.status);
                updateChatStatus(data.status === 'closed' ? 'Chat closed by agent' : 'Chat status: ' + data.status, data.status);
                
                // If agent accepted the chat, enable input
                if (data.status === 'active' || data.status === 'accepted') {
                    if (chatInput) {
                        chatInput.disabled = false;
                        chatInput.placeholder = 'Type your message...';
                        chatInput.focus();
                    }
                    if (sendButton) {
                        sendButton.disabled = false;
                    }
                    showChatHint('Agent has accepted your chat. You can now send messages.');
                }
            } 
            else if (data.type === 'message') {
                console.log('[DEBUG floating_chat.js] Chat message received from:', data.username);
                
                // Choose the right display name based on who sent the message
                const displayName = data.is_agent ? 'Support' : (data.username || 'You');
                const isSystemMessage = data.username === 'System';
                
                // Skip messages from the current user to avoid duplication
                // Messages from the current user are already added to the UI when sent
                const isFromCurrentUser = !data.is_agent && data.username !== 'System';
                if (!isFromCurrentUser) {
                    // Only add messages from other participants (not from the current user)
                    addMessage(displayName, data.message, isSystemMessage || data.is_agent);
                    
                    // If this is a message from the agent, they must be available, so enable input
                    if (data.is_agent) {
                        if (chatInput && chatInput.disabled) {
                            chatInput.disabled = false;
                            chatInput.placeholder = 'Type your message...';
                            chatInput.focus();
                        }
                        if (sendButton && sendButton.disabled) {
                            sendButton.disabled = false;
                        }
                    }
                } else {
                    console.log('[DEBUG floating_chat.js] Skipping duplicate user message');
                }
                
                // Update the lastMessageTime for session freshness
                if (window.localStorage) {
                    localStorage.setItem('lastMessageTime', Date.now().toString());
                }
            }
            else if (data.type === 'error') {
                console.error('[DEBUG floating_chat.js] Error message received:', data.message);
                updateChatStatus('Error: ' + data.message, 'error');
                showChatHint('Error: ' + data.message);
            }
            else if (data.type === 'pong') {
                console.log('[DEBUG floating_chat.js] Heartbeat pong received');
            }
            else {
                console.log('[DEBUG floating_chat.js] Unknown message type received:', data.type);
            }
        }
        
        console.log('[DEBUG floating_chat.js] Chat initialization complete');
    }
    
    // Improving the addMessage function to handle element not found errors
    function addMessage(sender, message, isFromAgent) {
        console.log('[DEBUG floating_chat.js] Adding message from:', sender, 'Message:', message, 'Agent:', isFromAgent);
        
        // Get or create chat messages container
        let chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) {
            console.error('[DEBUG floating_chat.js] chat-messages element not found during addMessage! Creating dynamically...');
            
            // Try to find the chat container first
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                // Create a new chat messages element if it doesn't exist
                chatMessages = document.createElement('div');
                chatMessages.id = 'chat-messages';
                chatMessages.className = 'chat-messages';
                chatMessages.style.display = 'block';
                chatMessages.style.visibility = 'visible';
                chatMessages.style.maxHeight = '400px'; // Increased height for better UX
                chatMessages.style.overflowY = 'auto';
                chatMessages.style.padding = '10px';
                
                // Insert it at the beginning of the chat container
                chatContainer.insertBefore(chatMessages, chatContainer.firstChild);
                console.log('[DEBUG floating_chat.js] Created new chat-messages container');
            } else {
                console.error('[DEBUG floating_chat.js] Cannot find chat container to add messages to!');
                return; // Exit early if we can't find a place to add messages
            }
        }
        
        // Create message wrapper to align messages properly
        const messageWrapper = document.createElement('div');
        messageWrapper.className = 'message-wrapper';
        messageWrapper.style.display = 'flex';
        messageWrapper.style.flexDirection = 'column';
        messageWrapper.style.alignItems = isFromAgent ? 'flex-start' : 'flex-end';
        messageWrapper.style.marginBottom = '12px';
        messageWrapper.style.width = '100%';
        
        // Create message bubble
        const messageBubble = document.createElement('div');
        messageBubble.className = isFromAgent ? 'agent-bubble' : 'user-bubble';
        messageBubble.style.maxWidth = '80%';
        messageBubble.style.padding = '10px 14px';
        messageBubble.style.borderRadius = isFromAgent ? '16px 16px 16px 4px' : '16px 16px 4px 16px';
        messageBubble.style.boxShadow = '0 1px 2px rgba(0,0,0,0.1)';
        
        // Set colors based on sender type
        if (isFromAgent) {
            messageBubble.style.backgroundColor = '#f0f0f0';
            messageBubble.style.color = '#333';
        } else {
            messageBubble.style.backgroundColor = '#0084ff';
            messageBubble.style.color = 'white';
        }
        
        // Special styling for system messages
        if (sender === 'System') {
            messageBubble.style.backgroundColor = '#f8d7da';
            messageBubble.style.color = '#721c24';
            messageBubble.style.borderRadius = '8px';
            messageBubble.style.fontStyle = 'italic';
            messageBubble.style.margin = '8px auto';
            messageBubble.style.textAlign = 'center';
            messageBubble.style.width = '90%';
            messageWrapper.style.alignItems = 'center';
        }
        
        // Create sender header if not a system message
        if (sender !== 'System') {
            const senderInfo = document.createElement('div');
            senderInfo.className = 'message-sender';
            senderInfo.textContent = sender;
            senderInfo.style.fontWeight = 'bold';
            senderInfo.style.fontSize = '0.85em';
            senderInfo.style.marginBottom = '3px';
            senderInfo.style.marginLeft = isFromAgent ? '8px' : '0';
            senderInfo.style.marginRight = isFromAgent ? '0' : '8px';
            senderInfo.style.color = isFromAgent ? '#555' : '#b3e0ff';
            messageWrapper.appendChild(senderInfo);
        }
        
        // Add message text
        const messageText = document.createElement('div');
        messageText.className = 'message-text';
        messageText.textContent = message;
        messageText.style.wordBreak = 'break-word';
        messageText.style.lineHeight = '1.4';
        messageBubble.appendChild(messageText);
        
        // Add timestamp
        const timestamp = document.createElement('div');
        timestamp.className = 'message-time';
        const now = new Date();
        timestamp.textContent = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes();
        timestamp.style.fontSize = '0.75em';
        timestamp.style.color = isFromAgent ? '#999' : 'rgba(255,255,255,0.8)';
        timestamp.style.textAlign = 'right';
        timestamp.style.marginTop = '4px';
        messageBubble.appendChild(timestamp);
        
        // Add bubble to the wrapper
        messageWrapper.appendChild(messageBubble);
        
        // Add message to chat container
        chatMessages.appendChild(messageWrapper);
        
        // Scroll to the newest message
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        console.log('[DEBUG floating_chat.js] Message added successfully');
    }

    // Function to clear stale session data that might cause issues
    function clearStaleSessionData() {
        // If URL has a query param like ?clear_chat=true, force clear the session
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('clear_chat')) {
            console.log('[DEBUG floating_chat.js] Clearing chat session data due to URL parameter');
            localStorage.removeItem('chat_session_id');
            return;
        }
        
        // Check if there's a session ID that's causing issues
        const sessionId = localStorage.getItem('chat_session_id');
        if (sessionId && (
            sessionId === '2c904465-e788-40d6-b8da-a9e99ea6fbdd' || // Known problematic ID
            sessionId.length !== 36 || // Invalid UUID format
            !sessionId.includes('-')   // Not a proper UUID
        )) {
            console.log('[DEBUG floating_chat.js] Removing problematic session ID:', sessionId);
            localStorage.removeItem('chat_session_id');
        }
        
        // Test basic WebSocket connectivity
        testWebSocketConnectivity();
    }
    
    // Test basic WebSocket connectivity to help diagnose connection issues
    function testWebSocketConnectivity() {
        console.log('[DIAGNOSTIC] Testing WebSocket connectivity...');
        
        // Test echo WebSocket server (public test server)
        const echoWs = new WebSocket('wss://echo.websocket.org');
        echoWs.onopen = function() {
            console.log('[DIAGNOSTIC] ✅ Public WebSocket test SUCCESSFUL - can connect to echo.websocket.org');
            echoWs.send('Hello from diagnostic test');
            
            // Close after successful test
            setTimeout(() => {
                echoWs.close();
            }, 1000);
        };
        echoWs.onmessage = function(e) {
            console.log('[DIAGNOSTIC] Received echo message:', e.data);
        };
        echoWs.onerror = function(e) {
            console.log('[DIAGNOSTIC] ❌ Public WebSocket test FAILED - cannot connect to echo.websocket.org');
            console.log('[DIAGNOSTIC] This suggests a general WebSocket connectivity issue in your environment');
        };
        
        // Test local WebSocket server
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const host = window.location.host.replace('localhost', '127.0.0.1');
        const baseHost = host.includes(':') ? host.split(':')[0] : host;
        // Connect to port 8001 where Daphne is running
        const testWs = new WebSocket(`${wsProtocol}${baseHost}:8001/ws/test/`);
        
        testWs.onopen = function() {
            console.log('[DIAGNOSTIC] ✅ Local WebSocket test SUCCESSFUL - can connect to the local server');
            testWs.close();
        };
        testWs.onerror = function(e) {
            console.log('[DIAGNOSTIC] ❌ Local WebSocket test FAILED - cannot connect to local WebSocket server');
            console.log('[DIAGNOSTIC] Possible causes:');
            console.log('[DIAGNOSTIC] - Daphne/ASGI server not running');
            console.log('[DIAGNOSTIC] - Routing not configured for /ws/test/ path');
            console.log('[DIAGNOSTIC] - Proxy blocking WebSocket connections');
        };
    }

    function testWebSocketConnection() {
        console.log('[DEBUG] Testing WebSocket connection...');
        
        let wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        let host = window.location.host.replace('localhost', '127.0.0.1');
        const baseHost = host.includes(':') ? host.split(':')[0] : host;
        let wsUrl = `${wsProtocol}${baseHost}:8001/ws/test/`;
        
        console.log('[DEBUG] Attempting to connect to:', wsUrl);
        
        let testSocket = new WebSocket(wsUrl);
        
        testSocket.onopen = function(e) {
            console.log('[DEBUG] Test WebSocket connection opened successfully!', e);
            testSocket.send(JSON.stringify({
                'message': 'Hello from client diagnostic test'
            }));
        };
        
        testSocket.onmessage = function(e) {
            console.log('[DEBUG] Test WebSocket message received:', e.data);
        };
        
        testSocket.onerror = function(e) {
            console.error('[DEBUG] Test WebSocket error:', e);
        };
        
        testSocket.onclose = function(e) {
            console.log('[DEBUG] Test WebSocket closed:', e.code, e.reason);
        };
        
        return testSocket;
    }

    // Add a global test function for console use
    window.testChatWebSocket = function() {
        return testWebSocketConnection();
    };

    // Function to fetch previous messages for returning users
    function fetchPreviousMessages(sessionId) {
        console.log('[DEBUG floating_chat.js] Fetching previous messages for session:', sessionId);
        
        fetch(`/livechat/api/messages/${sessionId}/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('[DEBUG floating_chat.js] Retrieved previous messages:', data.length);
                if (data && data.length > 0) {
                    // Clear any existing messages first
                    const chatMessages = document.getElementById('chat-messages');
                    if (chatMessages) {
                        chatMessages.innerHTML = '';
                    }
                    
                    // Add a hint that we're showing previous messages
                    showChatHint('Loading previous conversation...');
                    
                    // Display each message
                    data.forEach(msg => {
                        // Determine if this message is from the agent or user
                        const isFromAgent = msg.sender_type === 'agent';
                        const senderName = isFromAgent ? 'Support' : 'You';
                        
                        // Add message to UI
                        addMessage(senderName, msg.content, isFromAgent);
                    });
                }
            })
            .catch(error => {
                console.error('[DEBUG floating_chat.js] Error fetching previous messages:', error);
            });
    }
    
    // New function to show hints in the middle of the chat
    function showChatHint(message) {
        console.log('[DEBUG floating_chat.js] Showing chat hint:', message);
        
        // Get the chat-messages element
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) {
            console.error('[DEBUG floating_chat.js] Cannot show hint: chat-messages element not found!');
            return;
        }
        
        // Create a unique ID for this hint
        const hintId = 'hint-' + Date.now();
        
        // Create hint container
        const hintContainer = document.createElement('div');
        hintContainer.id = hintId;
        hintContainer.className = 'chat-hint';
        hintContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        hintContainer.style.color = 'white';
        hintContainer.style.padding = '8px 12px';
        hintContainer.style.borderRadius = '6px';
        hintContainer.style.fontSize = '0.85em';
        hintContainer.style.margin = '10px auto';
        hintContainer.style.textAlign = 'center';
        hintContainer.style.maxWidth = '90%';
        hintContainer.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        hintContainer.style.position = 'absolute';
        hintContainer.style.left = '50%';
        hintContainer.style.transform = 'translateX(-50%)';
        hintContainer.style.zIndex = '1000';
        hintContainer.style.opacity = '0';
        hintContainer.style.transition = 'opacity 0.3s ease, top 0.3s ease';
        
        // Set the hint message
        hintContainer.textContent = message;
        
        // Append to the chat
        chatMessages.appendChild(hintContainer);
        
        // Get existing hints to stack them properly
        const existingHints = chatMessages.querySelectorAll('.chat-hint');
        let topPosition = 10; // Start at 10px from the top
        
        // Stack hints by adjusting their top position
        if (existingHints.length > 1) {
            // Calculate the top position based on existing hints
            for (let i = 0; i < existingHints.length - 1; i++) {
                const hint = existingHints[i];
                if (hint.id !== hintId && hint.style.opacity !== '0') {
                    topPosition += hint.offsetHeight + 10; // Add 10px spacing between hints
                }
            }
        }
        
        // Set the top position and make visible
        hintContainer.style.top = topPosition + 'px';
        
        // Fade in with a small delay
        setTimeout(() => {
            hintContainer.style.opacity = '1';
        }, 50);
        
        // Scroll to ensure hint is visible
        chatMessages.scrollTop = 0;
        
        // Set a timeout to automatically remove the hint
        setTimeout(() => {
            // Fade out
            hintContainer.style.opacity = '0';
            
            // Remove after animation completes
            setTimeout(() => {
                if (hintContainer.parentNode) {
                    hintContainer.parentNode.removeChild(hintContainer);
                    
                    // Reposition remaining hints
                    const remainingHints = chatMessages.querySelectorAll('.chat-hint');
                    let newTop = 10;
                    
                    remainingHints.forEach(hint => {
                        hint.style.top = newTop + 'px';
                        newTop += hint.offsetHeight + 10;
                    });
                }
            }, 300); // Match transition duration
        }, 5000); // 5 seconds before fading out
        
        console.log('[DEBUG floating_chat.js] Chat hint displayed successfully');
    }

    // Window resize handler to ensure chat toggle button remains visible
    window.addEventListener('resize', function() {
        if (!chatPanel.classList.contains('active')) {
            resetChatToggleButton();
        } else if (window.innerWidth > 768) {
            // On larger screens, always show the toggle button
            resetChatToggleButton();
        }
    });

    // Additional check in case we need to reset on document load or after AJAX
    document.addEventListener('DOMContentLoaded', function() {
        if (!chatPanel.classList.contains('active')) {
            resetChatToggleButton();
        }
    });

    // Initial check on script load
    setTimeout(function() {
        if (!chatPanel.classList.contains('active')) {
            resetChatToggleButton();
        }
    }, 100);
})(); 