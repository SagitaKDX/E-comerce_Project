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
                try {
                    chatSocket.send(JSON.stringify({
                        'type': 'close_chat',
                        'session_id': chatSessionId,
                        'reason': 'page_unload'
                    }));
                } catch (error) {
                    console.error('[DEBUG floating_chat.js] Error sending close message:', error);
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
    }
    
    // Function to clear chat session data
    function clearChatSession() {
        localStorage.removeItem('chat_session_id');
        chatSessionId = null;
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
            } else {
                console.log('[DEBUG floating_chat.js] Chat panel closed');
                disconnectWebSocket();
            }
        });
        
        // 2. Minimize chat when minimize button is clicked
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', function() {
                console.log('[DEBUG floating_chat.js] Minimize button clicked');
                chatPanel.classList.remove('active');
                disconnectWebSocket();
            });
        }
        
        // 3. Close chat when close button is clicked
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                console.log('[DEBUG floating_chat.js] Close button clicked');
                chatPanel.classList.remove('active');
                disconnectWebSocket();
                
                // Optional: Clear chat session to start fresh next time
                clearChatSession();
                
                // Reset UI state to welcome screen
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
            
            // Force chat input and button visibility
            if (chatInput) {
                chatInput.style.display = 'block';
                chatInput.style.visibility = 'visible';
                // Input enabled state will be handled by WebSocket connection status
                chatInput.focus();
                console.log('[DEBUG floating_chat.js] Input styles applied');
            }
            
            if (sendButton) {
                sendButton.style.display = 'flex';
                sendButton.style.visibility = 'visible';
                // Button enabled state will be handled by WebSocket connection status
                console.log('[DEBUG floating_chat.js] Button styles applied');
            }
            
            // Connect to WebSocket, potentially passing subject/email
            connectWebSocket();
            
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
                        chatSocket.send(JSON.stringify({
                            'type': 'chat_message',
                            'message': message,
                            'sender': 'user',
                            'session_id': chatSessionId
                        }));
                        
                        // Add user message to chat UI immediately for responsive UX
                        addMessage('You', message, false);
                    } else {
                        console.warn('[DEBUG floating_chat.js] Cannot send message: WebSocket not connected');
                        addMessage('System', 'Message not sent. Connection offline.', true);
                        
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
                            chatSocket.send(JSON.stringify({
                                'type': 'chat_message',
                                'message': message,
                                'sender': 'user',
                                'session_id': chatSessionId
                            }));
                            
                            // Add user message to chat UI
                            addMessage('You', message, false);
                        } else {
                            addMessage('System', 'Message not sent. Connection offline.', true);
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
            // Logic: If we're on localhost:8000, the Daphne server might be on a different port
            const currentHost = window.location.host;
            let wsHost = currentHost;
            
            // Replace localhost with 127.0.0.1 to avoid DNS issues
            wsHost = wsHost.replace('localhost', '127.0.0.1');
            
            // If we're on port 8000 (Django runserver), Daphne might be on 8001
            // Try both 8000 and the port that's likely running Daphne
            let wsUrl = `${wsProtocol}${wsHost}/ws/chat/${chatSessionId}/`;
            
            // Log all the details of the connection we're trying to make
            console.log('[DEBUG floating_chat.js] Connecting details:', {
                protocol: wsProtocol,
                originalHost: currentHost,
                wsHost: wsHost,
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
                    chatSocket.send(JSON.stringify({
                        'type': 'chat_connect', 
                        'session_id': chatSessionId
                    }));
                    
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
                    // but only if we haven't exceeded max attempts
                    if (e.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                        if (chatActive.classList.contains('active')) {
                            reconnectAttempts++;
                            
                            // Exponential backoff: 2s, 4s, 8s
                            const delay = 2000 * Math.pow(2, reconnectAttempts - 1);
                            console.log(`[DEBUG floating_chat.js] Will try to reconnect in ${delay/1000} seconds (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
                            
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
                        addMessage('System', 'Could not connect to chat server after multiple attempts. Please try again later or refresh the page.', true);
                    }
                    
                    chatSocket = null;
                };

                chatSocket.onerror = function(e) {
                    console.error('[DEBUG floating_chat.js] WebSocket error observed:', e);
                    updateChatStatus('Connection Error', 'error');
                    updateConnectionStatus('error');
                    
                    // No need to disable inputs here as onclose will be called
                };

                chatSocket.onmessage = function(e) {
                    console.log('[DEBUG floating_chat.js] WebSocket message received:', e.data);
                    try {
                        const data = JSON.parse(e.data);
                        
                        // Handle different message types
                        if (data.type === 'message' && data.message) {
                            const isSystem = data.username === 'System';
                            const sender = data.is_agent ? 'Support' : (data.username || 'You');
                            addMessage(sender, data.message, isSystem);
                        } else if (data.type === 'system') {
                            addMessage('System', data.message, true);
                        } else if (data.type === 'status_update') {
                            updateChatStatus(data.status, data.status.toLowerCase());
                        } else if (data.type === 'agent_assigned') {
                            addMessage('System', `${data.agent_name} has joined the chat`, true);
                            updateChatStatus('Connected with ' + data.agent_name, 'online');
                        } else if (data.type === 'pong') {
                            console.log('[DEBUG floating_chat.js] Heartbeat pong received');
                        }
                    } catch (error) {
                        console.error('[DEBUG floating_chat.js] Error processing message:', error);
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
        
        // Set up heartbeat to keep connection alive
        function setupHeartbeat() {
            if (heartbeatInterval) {
                clearInterval(heartbeatInterval);
            }
            
            // Send ping every 30 seconds to keep connection alive
            heartbeatInterval = setInterval(() => {
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    console.log('[DEBUG floating_chat.js] Sending heartbeat ping');
                    chatSocket.send(JSON.stringify({
                        'type': 'ping',
                        'session_id': chatSessionId
                    }));
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
                    chatSocket.send(JSON.stringify({
                        'type': 'close_chat',
                        'session_id': chatSessionId
                    }));
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
        
        console.log('[DEBUG floating_chat.js] Chat initialization complete');
    }
    
    // Simple message rendering function
    function addMessage(sender, text, isSystem) {
        console.log('[DEBUG floating_chat.js] Adding message from', sender, ':', text);
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) {
            console.error('[DEBUG floating_chat.js] Cannot add message: chat-messages element not found');
            return;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = isSystem ? 
            'message message-system' : 
            (sender === 'You' ? 'message message-user' : 'message message-agent');
        
        // Create message content
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = text;
        
        // Add sender name for non-system messages
        if (!isSystem) {
            const senderDiv = document.createElement('div');
            senderDiv.className = 'message-sender';
            senderDiv.textContent = sender;
            messageDiv.appendChild(senderDiv);
        }
        
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to the latest message
        chatMessages.scrollTop = chatMessages.scrollHeight;
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
        const testWs = new WebSocket(`${wsProtocol}${host}/ws/test/`);
        
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
            
            // Suggest checking if server is running on a different port
            const alternativePort = host.includes('8000') ? '8001' : (host.includes(':') ? host.split(':')[0] + ':8001' : host + ':8001');
            console.log(`[DIAGNOSTIC] Try connecting to ws://${alternativePort}/ws/chat/ if Daphne runs on a different port`);
        };
    }

    function testWebSocketConnection() {
        console.log('[DEBUG] Testing WebSocket connection...');
        
        let wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        let wsUrl = wsProtocol + window.location.host + '/ws/test/';
        
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
})(); 