// Add a global flag to check if the script runs
window.floatingChatInitialized = false;

(function() {
    'use strict';
    console.log('[DEBUG floating_chat.js] IIFE Started.'); // Log 1
    
    window.floatingChatInitialized = true;
    console.log('[DEBUG floating_chat.js] window.floatingChatInitialized set to:', window.floatingChatInitialized); // Log 2
    
    console.log('Floating Chat JS Loaded');

    let chatSocket = null;
    const chatPanel = document.getElementById('chat-panel');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('chat-send-btn');
    const chatStatus = document.getElementById('chat-status');

    function initializeChat() {
        console.log('[DEBUG floating_chat.js] initializeChat() called.'); // Log 3
        console.log('DOM Loaded, initializing chat elements...');

        const chatToggleBtn = document.getElementById('chat-toggle-btn');
        const minimizeBtn = document.getElementById('chat-minimize-btn');
        const closeBtn = document.getElementById('chat-close-btn');

        // Basic element checks
        if (!chatToggleBtn || !chatPanel || !chatInput || !sendButton || !chatStatus) {
            console.error('Error: Critical chat elements missing!');
            if (!chatToggleBtn) console.error('- chatToggleBtn missing');
            if (!chatPanel) console.error('- chatPanel missing');
            if (!chatInput) console.error('- chatInput missing');
            if (!sendButton) console.error('- sendButton missing');
            if (!chatStatus) console.error('- chatStatus missing');
            return;
        }
        console.log('All critical chat elements found.');

        // Toggle chat panel visibility & WebSocket connection
        chatToggleBtn.addEventListener('click', function() {
            console.log('[DEBUG floating_chat.js] Toggle button CLICKED!'); // Log 4
            console.log('Toggle button clicked');
            const isActive = chatPanel.classList.toggle('active');
            
            if (isActive) {
                console.log('Chat panel opened');
                connectWebSocket(); // Connect when panel opens
                setTimeout(() => chatInput.focus(), 100);
            } else {
                console.log('Chat panel closed');
                disconnectWebSocket(); // Disconnect when panel closes
            }
        });

        // Minimize button
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', function() {
                console.log('Minimize button clicked');
                chatPanel.classList.remove('active');
                disconnectWebSocket(); // Disconnect when minimized
            });
        }

        // Close button
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                console.log('Close button clicked');
                chatPanel.classList.remove('active');
                disconnectWebSocket(); // Disconnect when closed
            });
        }

        // -- WebSocket Functions --

        function connectWebSocket() {
            // Prevent multiple connections
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                console.log('WebSocket already connected.');
                return;
            }
            if (chatSocket && chatSocket.readyState === WebSocket.CONNECTING) {
                console.log('WebSocket connection already in progress.');
                return;
            }

            console.log('Attempting to connect WebSocket...');
            updateChatStatus('Connecting...', 'connecting');
            
            // *** Replace with your actual WebSocket endpoint ***
            // Example: ws://localhost:8000/ws/livechat/some_room_id/
            // For now, using a placeholder that will likely fail but allows testing UI
            const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = `${wsProtocol}${window.location.host}/ws/livechat/test_room/`; // <-- Needs dynamic room ID later
            console.log('Connecting to:', wsUrl);

            try {
                chatSocket = new WebSocket(wsUrl);

                chatSocket.onopen = function(e) {
                    console.log('WebSocket connection opened successfully.');
                    updateChatStatus('Connected', 'online');
                    chatInput.disabled = false;
                    sendButton.disabled = false;
                    // Add logic here to maybe request chat history or send user info
                };

                chatSocket.onclose = function(e) {
                    console.warn(`WebSocket closed unexpectedly. Code: ${e.code}, Reason: ${e.reason}`);
                    updateChatStatus('Disconnected', 'offline');
                    chatInput.disabled = true;
                    sendButton.disabled = true;
                    chatSocket = null; // Clear the socket object
                    // Optional: Implement reconnection logic here
                };

                chatSocket.onerror = function(e) {
                    console.error('WebSocket error observed:', e);
                    updateChatStatus('Connection Error', 'error');
                    chatInput.disabled = true;
                    sendButton.disabled = true;
                };

                chatSocket.onmessage = function(e) {
                    console.log('WebSocket message received:', e.data);
                    // We will handle message processing in the next step
                    // const data = JSON.parse(e.data);
                    // handleIncomingMessage(data);
                };

            } catch (error) {
                console.error('Failed to create WebSocket:', error);
                updateChatStatus('Failed to connect', 'error');
            }
        }

        function disconnectWebSocket() {
            if (chatSocket) {
                console.log('Closing WebSocket connection.');
                chatSocket.close(1000, 'User closed chat panel'); // 1000 = Normal closure
                // onclose handler will update status and disable input
            }
            chatSocket = null; // Ensure it's nullified
            updateChatStatus('Offline', 'offline'); // Set status immediately
            chatInput.disabled = true;
            sendButton.disabled = true;
        }

        function updateChatStatus(statusText, statusClass) {
            if (chatStatus) {
                chatStatus.textContent = statusText;
                // Optional: Add CSS classes for styling based on status
                chatStatus.className = `chat-subtitle status-${statusClass}`;
                console.log('Chat status updated:', statusText);
            }
        }
        
        console.log('Chat UI initialized.');
        updateChatStatus('Offline', 'offline'); // Set initial status
    }

    // --- Run Initialization ---
    // Use DOMContentLoaded to ensure HTML is parsed, but run slightly delayed 
    // just in case base.html script loading is slower.
    console.log('[DEBUG floating_chat.js] Setting up initializeChat trigger. readyState:', document.readyState);
    if (document.readyState === 'loading') { 
        document.addEventListener('DOMContentLoaded', initializeChat);
    } else { 
        // DOMContentLoaded has already fired
        setTimeout(initializeChat, 0); // Execute async but immediately
    }

})(); 