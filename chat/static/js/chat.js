// ======================= chat.js =======================

// Grab chat-related elements
const messagesContainer = document.getElementById('chat-messages');
const roomName = messagesContainer.dataset.roomName;
const meId = Number(messagesContainer.dataset.meId);              // Logged-in user
const otherUserId = Number(messagesContainer.dataset.receiverId); // Chat partner

// Create WebSocket connection
const chatSocket = new WebSocket(
    (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
    window.location.host +
    '/ws/chat/' +
    roomName +
    '/'
);

// ------------------ Helper Functions ------------------

// Update ticks for a message by msgId
function updateTicksForMsg(msgId, newStatus) {
    if (!msgId) return;
    const elem = document.querySelector(`[data-msg-id='${msgId}']`);
    if (!elem) return;
    const ticksSpan = elem.querySelector('.ticks');
    if (!ticksSpan) return;

    if (newStatus === 'sent') ticksSpan.innerHTML = '✓';
    else if (newStatus === 'delivered') ticksSpan.innerHTML = '✓✓';
    else if (newStatus === 'read')
        ticksSpan.innerHTML = "<span class='read-ticks'>✓✓</span>";
}

// ✅ Create message div element (incoming or outgoing)
function createMessageDiv(msgText, isSender, timestampText, status, msgId) {
    const msgDiv = document.createElement('div');
    // FIXED: Use 'message-bubble' instead of 'message'
    msgDiv.classList.add('message-bubble', isSender ? 'sent' : 'received');
    if (msgId) msgDiv.setAttribute('data-msg-id', msgId);

    const ticksHtml = isSender
        ? status === 'read'
            ? "<i class='fas fa-check-double read-ticks'></i>"
            : status === 'delivered'
            ? "<i class='fas fa-check-double grey-tick'></i>"
            : "<i class='fas fa-check'></i>"
        : '';

    msgDiv.innerHTML = `
        <p>${msgText}</p>
        <span class="message-time">
            ${timestampText}
            <span class="ticks">${isSender ? ticksHtml : ''}</span>
        </span>
    `;

    // Optional: add a small fade-in animation
    msgDiv.style.opacity = 0;
    msgDiv.style.transition = "opacity 0.2s ease-in-out";
    requestAnimationFrame(() => (msgDiv.style.opacity = 1));

    return msgDiv;
}

// Update presence UI for the receiver
function updatePresenceUI(userId, isOnline, lastSeen) {
    if (Number(userId) !== otherUserId) return;

    const dot = document.getElementById(`presence-dot-${otherUserId}`);
    const text = document.getElementById(`presence-text-${otherUserId}`);
    if (!dot || !text) return;

    if (isOnline) {
        dot.style.background = '#2ecc71'; // green
        text.textContent = 'Online';
        return;
    }

    dot.style.background = '#bdc3c7'; // grey
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

    const formattedTime = lastSeenDate.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
    });
    const formattedDate = lastSeenDate.toLocaleDateString([], {
        month: 'short',
        day: 'numeric',
    });

    if (diffMinutes < 1) text.textContent = 'Last seen just now';
    else if (diffMinutes < 60) text.textContent = `Last seen ${diffMinutes} min ago`;
    else if (diffHours < 24 && now.getDate() === lastSeenDate.getDate())
        text.textContent = `Last seen today ${formattedTime}`;
    else if (diffDays === 1)
        text.textContent = `Last seen yesterday ${formattedTime}`;
    else text.textContent = `Last seen on ${formattedDate}, ${formattedTime}`;
}

// Mark messages as read
function markReadNow() {
    chatSocket.send(
        JSON.stringify({
            action: 'mark_read',
            reader_id: meId,
            other_user_id: otherUserId,
        })
    );
}

// ------------------ WebSocket Handlers ------------------

chatSocket.onopen = function () {
    console.log('WebSocket connected');

    // Inform server this user is connected
    chatSocket.send(
        JSON.stringify({
            action: 'receiver_connected',
            receiver_id: meId,
        })
    );

    // Mark messages read
    markReadNow();
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
        const ts = data.timestamp
            ? new Date(data.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
              })
            : 'Just now';

        const msgDiv = createMessageDiv(message, isSender, ts, status, msgId);
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // If this client is the receiver, mark delivered
        if (!isSender && receiver_id === meId) {
            chatSocket.send(
                JSON.stringify({
                    action: 'receiver_connected',
                    receiver_id: meId,
                })
            );
        }
    } else if (eventType === 'status_update') {
        const ids = data.msg_ids || [];
        const newStatus = data.new_status;
        ids.forEach((id) => updateTicksForMsg(id, newStatus));
    } else if (eventType === 'presence_update') {
        updatePresenceUI(data.user_id, data.is_online, data.last_seen);
    }
};

chatSocket.onclose = function () {
    console.error('Chat socket closed unexpectedly');
};

// ------------------ Form Submission ------------------

document.getElementById('chat-form').onsubmit = function (e) {
    e.preventDefault();
    const inputField = document.getElementById('chat-message-input');
    const message = inputField.value.trim();
    if (message === '') return;

    chatSocket.send(
        JSON.stringify({
            action: 'send_message',
            message: message,
            sender_id: meId,
            receiver_id: otherUserId,
        })
    );

    inputField.value = '';
};

// ------------------ Event Listeners ------------------

// Mark read on focus/visibility
window.addEventListener('focus', markReadNow);
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') markReadNow();
});

// Scroll to bottom & initial presence on DOM load
window.addEventListener('DOMContentLoaded', () => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    const receiverId = Number(messagesContainer.dataset.receiverId);
    const isOnline =
        messagesContainer.dataset.receiverOnline.toLowerCase() === 'true';
    const lastSeen = messagesContainer.dataset.receiverLastSeen || null;

    updatePresenceUI(receiverId, isOnline, lastSeen);
});



// === USER PROFILE MODAL CODE (UPDATED) ===

// References
const userProfileModal = document.getElementById('userProfileModal');
const closeUserProfileBtn = document.getElementById('closeUserProfile');
const navBottomAvatar = document.querySelector('.nav-bottom-avatar');
const navAvatar = document.querySelector('.nav-avatar');

// Utility functions
function closeAllModals() {
    userProfileModal.style.display = 'none';
}

function closeAllPopups() {
    document.querySelectorAll('.emoji-popup, .attachment-popup, .chat-menu-popup')
        .forEach(popup => popup.style.display = 'none');
}

function resetIconHighlights() {
    document.querySelectorAll('.nav-icons i').forEach(icon => icon.classList.remove('active'));
    document.getElementById('chatsIcon')?.classList.add('active'); // default highlight
}

// === OPEN PROFILE MODAL ===
navAvatar?.addEventListener('click', (e) => {
    e.stopPropagation();
    closeAllModals();
    closeAllPopups();
    userProfileModal.style.display = 'block';
    resetIconHighlights();
});

navBottomAvatar?.addEventListener('click', (e) => {
    e.stopPropagation();
    closeAllModals();
    closeAllPopups();
    userProfileModal.style.display = 'block';
    resetIconHighlights();
});

// === CLOSE PROFILE MODAL ===
closeUserProfileBtn?.addEventListener('click', () => {
    userProfileModal.style.display = 'none';
    resetIconHighlights();
});

// === CLICK OUTSIDE TO CLOSE ===
window.addEventListener('click', (event) => {
    if (event.target === userProfileModal) {
        userProfileModal.style.display = 'none';
        resetIconHighlights();
    }
});

// === EDIT PROFILE ICONS (NEW FUNCTIONALITY) ===
const editProfileImage = document.getElementById('editProfileImage');
const editProfileName = document.getElementById('editProfileName');
const editProfileStatus = document.getElementById('editProfileStatus');
const nameInput = document.getElementById('nameInput');
const statusInput = document.getElementById('statusInput');
const imageInput = document.getElementById('imageInput');
const profileName = document.getElementById('profileName');
const profileStatus = document.getElementById('profileStatus');
const profileImage = document.getElementById('profileImage');

// --- Edit Name ---
editProfileName?.addEventListener('click', () => {
    profileName.style.display = 'none';
    nameInput.style.display = 'inline-block';
    nameInput.focus();

    const saveName = () => {
        updateProfile({ name: nameInput.value });
        nameInput.removeEventListener('blur', saveName);
        nameInput.removeEventListener('keydown', handleEnter);
    };

    const handleEnter = (e) => {
        if (e.key === 'Enter') nameInput.blur();
    };

    nameInput.addEventListener('blur', saveName);
    nameInput.addEventListener('keydown', handleEnter);
});

// --- Edit Status ---
editProfileStatus?.addEventListener('click', () => {
    profileStatus.style.display = 'none';
    statusInput.style.display = 'inline-block';
    statusInput.focus();

    const saveStatus = () => {
        updateProfile({ status: statusInput.value });
        statusInput.removeEventListener('blur', saveStatus);
        statusInput.removeEventListener('keydown', handleEnter);
    };

    const handleEnter = (e) => {
        if (e.key === 'Enter') statusInput.blur();
    };

    statusInput.addEventListener('blur', saveStatus);
    statusInput.addEventListener('keydown', handleEnter);
});

// --- Edit Image ---
editProfileImage?.addEventListener('click', () => imageInput.click());
imageInput?.addEventListener('change', () => {
    const file = imageInput.files[0];
    if (file) {
        const formData = new FormData();
        formData.append('image', file);
        sendUpdate(formData);
    }
});

// --- Send update to Django backend ---
function updateProfile(data) {
    const formData = new FormData();
    for (const key in data) formData.append(key, data[key]);
    sendUpdate(formData);
}

function sendUpdate(formData) {
    fetch("/update_profile/", {
        method: "POST",
        body: formData,
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                if (data.name) {
                    profileName.textContent = data.name;
                    profileName.style.display = "block";
                    nameInput.style.display = "none";
                }
                if (data.status) {
                    profileStatus.textContent = data.status;
                    profileStatus.style.display = "block";
                    statusInput.style.display = "none";
                }
                if (data.image_url) {
                    profileImage.src = data.image_url;
                }
            } else {
                alert("Error updating profile: " + (data.error || "Unknown error"));
            }
        })
        .catch((err) => {
            console.error("Profile update failed", err);
        });
}

// --- Get CSRF token ---
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// === LOGOUT BUTTON ===
// === LOGOUT BUTTON ===
const logoutBtn = document.getElementById('logoutBtn');
logoutBtn?.addEventListener('click', () => {
    // Optional: confirmation
    if (!confirm("Are you sure you want to log out?")) return;

    fetch("/logout/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
        },
    })
        .then((res) => {
            if (res.redirected) {
                // Django redirect will send us to login page
                window.location.href = res.url;
            } else {
                // Fallback if redirect didn't happen
                window.location.href = "/login/";
            }
        })
        .catch((err) => {
            console.error("Logout failed", err);
            alert("Logout failed. Please try again.");
        });

    userProfileModal.style.display = "none";
    resetIconHighlights();
});

// When user clicks a chat from list
document.querySelectorAll('.chat-item').forEach(item => {
    item.addEventListener('click', function() {
    const number = this.dataset.number;
    const name = this.dataset.name;

    // Change URL without reload
    window.history.pushState({}, '', `/chat/${number}/`);

    // Load chat dynamically
    loadChat(number, name);
    });
});

function loadChat(number, name) {
    const chatArea = document.getElementById('chatArea');
    chatArea.innerHTML = `<div class="chat-header">${name}</div>
                        <div class="chat-messages" id="chatMessages"><p>Loading...</p></div>`;

    fetch(`/api/chat/${number}/messages/`)
    .then(res => res.json())
    .then(data => {
        if (data.error) {
        chatArea.innerHTML = `<p>${data.error}</p>`;
        return;
        }

        const msgContainer = document.getElementById('chatMessages');
        msgContainer.innerHTML = '';

        data.messages.forEach(msg => {
        const div = document.createElement('div');
        div.classList.add('message', msg.is_sender ? 'sent' : 'received');
        div.innerHTML = `${msg.content}<span class="time">${msg.timestamp}</span>`;
        msgContainer.appendChild(div);
        });

        msgContainer.scrollTop = msgContainer.scrollHeight;
    })
    .catch(err => {
        console.error(err);
        chatArea.innerHTML = `<p>Failed to load chat.</p>`;
    });
}

// Handle back navigation
window.addEventListener('popstate', () => {
    const parts = window.location.pathname.split('/chat/');
    const number = parts[1]?.replace('/', '');
    if (number) loadChat(number, number);
    else document.getElementById('chatArea').innerHTML =
    '<div class="default-chat-view"><h2>Select a chat to start messaging</h2></div>';
});

