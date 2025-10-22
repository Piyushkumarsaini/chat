
const messagesContainer = document.getElementById('chat-messages');
const roomName = messagesContainer.dataset.roomName; 
const meId = Number("{{ current_user.id }}");        // logged in user (this browser)
const otherUserId = Number("{{ receiver.id }}");    // the chat partner

const chatSocket = new WebSocket(
    (window.location.protocol === 'https:' ? 'wss://' : 'ws://')
    + window.location.host + '/ws/chat/' + roomName + '/'
);


// Helper to update ticks for a message element with given msgId
function updateTicksForMsg(msgId, newStatus) {
    if (!msgId) return;
    const elem = document.querySelector(`[data-msg-id='${msgId}']`);
    if (!elem) return;
    const ticksSpan = elem.querySelector('.ticks');
    if (!ticksSpan) return;

    if (newStatus === 'sent') ticksSpan.innerHTML = '✓';
    else if (newStatus === 'delivered') ticksSpan.innerHTML = '✓✓';
    else if (newStatus === 'read') ticksSpan.innerHTML = "<span style='color:#4fc3f7;'>✓✓</span>";
}

// Create DOM for a message (used for incoming messages)
function createMessageDiv(msgText, isSender, timestampText, status, msgId) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', isSender ? 'sent' : 'received');
    if (msgId) msgDiv.setAttribute('data-msg-id', msgId);
    msgDiv.style.cssText = `
        margin-bottom:12px;max-width:70%;padding:10px 16px;border-radius:18px;clear:both;
        ${isSender ? 'background:#dcf8c6;margin-left:auto;text-align:right;' : 'background:#fff;margin-right:auto;text-align:left;border:1px solid #ddd;'}
    `;
    const ticksHtml = isSender ? (status === 'read' ? "<span style='color:#4fc3f7;'>✓✓</span>" : (status === 'delivered' ? '✓✓' : '✓')) : '';
    msgDiv.innerHTML = `<div>${msgText}</div><small style="color:#888;">${timestampText} <span class="ticks">${ticksHtml}</span></small>`;
    return msgDiv;
}

// Update presence UI in header for the receiver
function updatePresenceUI(userId, isOnline, lastSeen) {
    // we only show presence of the chat partner in header (otherUserId)
    if (Number(userId) !== otherUserId) return;
    const dot = document.getElementById(`presence-dot-${otherUserId}`);
    const text = document.getElementById(`presence-text-${otherUserId}`);
    if (!dot || !text) return;

    if (isOnline) {
        dot.style.background = '#2ecc71'; // green
        text.textContent = 'Online';
        return;
    }

    // Offline state
    dot.style.background = '#bdc3c7';
    if (!lastSeen) {
        text.textContent = 'Offline';
        return;
    }
    
    const lastSeenDate = new Date(lastSeen);
    const now = new Date();
    const diffMs = now - lastSeenDate;
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    const formattedTime = lastSeenDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    const formattedDate = lastSeenDate.toLocaleDateString([], { month: 'short', day: 'numeric' });

    if (diffMinutes < 1) {
        text.textContent = 'Last seen just now';
    } else if (diffMinutes < 60) {
        text.textContent = `Last seen ${diffMinutes} min ago`;
    } else if (diffHours < 24 && now.getDate() === lastSeenDate.getDate()) {
        text.textContent = `Last seen today ${formattedTime}`;
    } else if (diffDays === 1) {
        text.textContent = `Last seen yesterday ${formattedTime}`;
    } else {
        text.textContent = `Last seen on ${formattedDate}, ${formattedTime}`;
    }
}


chatSocket.onopen = function () {
    console.log("WebSocket connected");

    // Inform server this user is connected to the chat -> server may mark messages delivered
    chatSocket.send(JSON.stringify({
        'action': 'receiver_connected',
        'receiver_id': meId
    }));

    // Immediately mark messages read (optional; we also do this on focus/visibility)
    chatSocket.send(JSON.stringify({
        'action': 'mark_read',
        'reader_id': meId,
        'other_user_id': otherUserId
    }));
};

chatSocket.onmessage = function (e) {
    const data = JSON.parse(e.data);
    const eventType = data.event;

    if (eventType === 'chat_message') {
        const message = data.message;
        const sender_id = Number(data.sender_id);
        const receiver_id = Number(data.receiver_id);
        const isSender = sender_id === meId;
        const status = data.status;
        const msgId = data.msg_id;
        const ts = data.timestamp ? new Date(data.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'Just now';

        const msgDiv = createMessageDiv(message, isSender, ts, status, msgId);
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // If this client is the receiver of this message, ask server to mark delivered
        if (!isSender && receiver_id === meId) {
            chatSocket.send(JSON.stringify({
                'action': 'receiver_connected',
                'receiver_id': meId
            }));
        }
    } else if (eventType === 'status_update') {
        const ids = data.msg_ids || [];
        const newStatus = data.new_status;
        ids.forEach(id => updateTicksForMsg(id, newStatus));
    } else if (eventType === 'presence_update') {
        // presence update: contains user_id, is_online, optional last_seen
        updatePresenceUI(data.user_id, data.is_online, data.last_seen);
    }
};

chatSocket.onclose = function (e) {
    console.error('Chat socket closed unexpectedly');
};

// Send message
document.getElementById('chat-form').onsubmit = function (e) {
    e.preventDefault();
    const inputField = document.getElementById('chat-message-input');
    const message = inputField.value.trim();
    if (message === '') return;

    chatSocket.send(JSON.stringify({
        'action': 'send_message',
        'message': message,
        'sender_id': meId,
        'receiver_id': otherUserId
    }));

    inputField.value = '';
};

// Mark messages read when window/tab gets focus or becomes visible
function markReadNow() {
    chatSocket.send(JSON.stringify({
        'action': 'mark_read',
        'reader_id': meId,
        'other_user_id': otherUserId
    }));
}

window.addEventListener('focus', markReadNow);
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') markReadNow();
});

// Optional: scroll to bottom on load
window.onload = function () {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    const receiverElem = document.getElementById('chat-messages');
    const receiverId = Number(receiverElem.dataset.receiverId);
    const isOnline = receiverElem.dataset.receiverOnline === 'True';
    const lastSeen = receiverElem.dataset.receiverLastSeen || null;

    updatePresenceUI(receiverId, isOnline, lastSeen);
};
