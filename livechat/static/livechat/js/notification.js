document.addEventListener('DOMContentLoaded', function() {
    const notificationSound = new Audio('/static/livechat/sounds/notification.mp3');
    
    function createNotification(message, sender) {
        const notification = document.createElement('div');
        notification.className = 'message-notification';
        
        const avatar = document.createElement('div');
        avatar.className = 'notification-avatar';
        if (sender.avatar) {
            avatar.innerHTML = `<img src="${sender.avatar}" alt="${sender.name}">`;
        } else {
            avatar.innerHTML = `<div class="avatar-placeholder">${sender.name.charAt(0)}</div>`;
        }
        
        const content = document.createElement('div');
        content.className = 'notification-content';
        
        const senderName = document.createElement('div');
        senderName.className = 'notification-sender';
        senderName.textContent = sender.name;
        
        const messageText = document.createElement('div');
        messageText.className = 'notification-message';
        messageText.textContent = message.substring(0, 60) + (message.length > 60 ? '...' : '');
        
        content.appendChild(senderName);
        content.appendChild(messageText);
        
        notification.appendChild(avatar);
        notification.appendChild(content);
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', function() {
            document.body.removeChild(notification);
        });
        
        notification.appendChild(closeBtn);
        
        // Add click handler to open the chat
        notification.addEventListener('click', function(e) {
            if (e.target !== closeBtn) {
                window.location.href = `/livechat/admin/`;
            }
        });
        
        return notification;
    }
    
    function showNotification(message, sender) {
        // Play sound
        notificationSound.play().catch(e => console.warn('Could not play notification sound', e));
        
        // Create and show notification
        const notification = createNotification(message, sender);
        document.body.appendChild(notification);
        
        // Position the notification
        notification.style.bottom = '20px';
        notification.style.right = '20px';
        
        // Add appear animation
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        }, 50);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 5000);
    }
    
    // Add CSS for notifications
    const style = document.createElement('style');
    style.textContent = `
        .message-notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 300px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            padding: 12px;
            z-index: 9999;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .notification-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            overflow: hidden;
            margin-right: 12px;
            background: #f0f0f0;
        }
        
        .notification-avatar img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .avatar-placeholder {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #4a90e2;
            color: white;
            font-weight: bold;
        }
        
        .notification-content {
            flex: 1;
        }
        
        .notification-sender {
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .notification-message {
            color: #555;
        }
        
        .notification-close {
            background: none;
            border: none;
            color: #999;
            font-size: 20px;
            cursor: pointer;
            padding: 0 6px;
            align-self: flex-start;
            margin: -5px -5px 0 0;
        }
        
        .notification-close:hover {
            color: #333;
        }
    `;
    document.head.appendChild(style);
    
    // Expose the function globally
    window.showChatNotification = showNotification;
}); 