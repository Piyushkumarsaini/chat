const messagesContainer = document.getElementById('chat-messages');
const roomName = messagesContainer?.dataset.roomName || '';
const meId = Number(messagesContainer?.dataset.meId || 0);              // Logged-in user

// Make otherUserId mutable and initialise from dataset if present
let otherUserId = Number(messagesContainer?.dataset.receiverId || 0); // Chat partner (may change)

// Create WebSocket connection
const chatSocket = new WebSocket(
    (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
    window.location.host +
    '/ws/chat/global_chat/'
);

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

// Create message div element (incoming or outgoing)
function createMessageDiv(msgText, isSender, timestampText, status, msgId) {
    const msgDiv = document.createElement('div');
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

    msgDiv.style.opacity = 0;
    msgDiv.style.transition = "opacity 0.2s ease-in-out";
    requestAnimationFrame(() => (msgDiv.style.opacity = 1));

    return msgDiv;
}

// Update presence UI for the receiver
function updatePresenceUI(userId, isOnline, lastSeen) {
    // only update if this presence is for currently-open chat partner
    if (Number(userId) !== Number(otherUserId)) return;

    const dot = document.getElementById('presence-dot');
    const text = document.getElementById('presence-text');
    if (!dot || !text) return;

    if (isOnline) {
        dot.style.background = '#2ecc71'; // green
        text.textContent = 'Online';
    } else {
        dot.style.background = '#bdc3c7'; // grey

        if (lastSeen) {
            const lastSeenDate = new Date(lastSeen);
            const now = new Date();
            const diffMs = now - lastSeenDate;
            const diffMinutes = Math.floor(diffMs / 60000);

            if (diffMinutes < 1) text.textContent = 'Last seen just now';
            else if (diffMinutes < 60) text.textContent = `Last seen ${diffMinutes} min ago`;
            else text.textContent = `Last seen at ${lastSeenDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        } else {
            text.textContent = 'Offline';
        }
    }
}

// Mark messages as read
function markReadNow() {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            action: 'mark_read',
            reader_id: meId,
            other_user_id: otherUserId,
        }));
    }
}

// ------------------ WebSocket Handlers ------------------

chatSocket.onopen = function () {
    console.log('WebSocket connected');

    // Heartbeat
    setInterval(() => {
        if (chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({
                action: 'heartbeat',
                user_id: meId
            }));
        }
    }, 20000); // every 20 seconds

    // Identify current user to backend (so presence = online)
    chatSocket.send(JSON.stringify({
        action: 'identify_user',
        user_id: meId
    }));

    // Inform server this client is connected (so pending -> delivered)
    chatSocket.send(JSON.stringify({
        action: 'receiver_connected',
        receiver_id: meId,
    }));

    // Mark messages read for open chat
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
            hour: "2-digit",
            minute: "2-digit",
            })
        : "Just now";

        // Only show if message is for the open chat
        if (
        (isSender && receiver_id === otherUserId) ||
        (!isSender && sender_id === otherUserId)
        ) {
        let html = "";

        // 📎 Attachment Handling
        if (data.attachment_url) {
            const url = data.attachment_url;
            const type = data.attachment_type || "";

            // 🖼️ Image
            if (type.startsWith("image") || url.match(/\.(jpg|jpeg|png|gif|webp)$/i)) {
            html = `<img src="${url}" class="chat-image" alt="image">`;

            // 🎥 Video
            } else if (type.startsWith("video") || url.match(/\.(mp4|webm|ogg)$/i)) {
            html = `<video controls class="chat-video"><source src="${url}" type="video/mp4"></video>`;

            // 📄 Document or other file types
            } else {
            html = `<a href="${url}" target="_blank" rel="noopener noreferrer">📄 Download File</a>`;
            }
        } else {
            // 💬 Regular Text Message
            html = escapeHtml(data.message || "");
        }

        // Create the message bubble
        const msgDiv = createMessageDiv(html, isSender, ts, status, msgId);

        // Add to chat box
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // 🟠 If current user is receiver → mark message as delivered
        if (!isSender && receiver_id === meId) {
        chatSocket.send(
            JSON.stringify({
            action: "receiver_connected",
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

// ------------------ Event Listeners ------------------

// Mark read on focus/visibility
window.addEventListener('focus', markReadNow);
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') markReadNow();
});

// Scroll to bottom & initial presence on DOM load
window.addEventListener('DOMContentLoaded', () => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // initial presence from dataset (if any)
    const receiverIdFromDataset = Number(messagesContainer.dataset.receiverId || 0);
    if (receiverIdFromDataset) {
        otherUserId = receiverIdFromDataset;
    }

    const isOnline = messagesContainer.dataset.receiverOnline === 'true';
    const lastSeen = messagesContainer.dataset.receiverLastSeen || null;
    updatePresenceUI(otherUserId, isOnline, lastSeen);
});

// When user clicks a chat from list
document.querySelectorAll('.chat-item').forEach(item => {
    item.addEventListener('click', function() {
        const number = this.dataset.number;
        const name = this.dataset.name;
        const userId = Number(this.dataset.userid);

        // Update mutable variable
        otherUserId = userId;

        // Update receiver info in the header
        document.querySelector('.chat-contact-name').textContent = name;

        // Reset presence display
        const dot = document.querySelector('.presence-dot');
        const text = document.querySelector('.presence-indicator small');
        if (dot && text) {
            dot.style.background = '#bdc3c7';
            text.textContent = 'Checking...';
        }

        // Change URL without reload
        window.history.pushState({}, '', `/chat/${number}/`);

        // Load chat dynamically
        loadChat(number, name, userId);
    });
});

function loadChat(number, name, userId) {
    otherUserId = Number(userId); // store globally
    document.querySelector('.chat-contact-name').textContent = name;
    document.getElementById('presence-text').textContent = 'Checking...';
    document.getElementById('presence-dot').style.background = '#bdc3c7';

    // Load chat messages
    fetch(`/api/chat/${number}/messages/`)
        .then(res => res.json())
        .then(data => {
            // Use the same container used elsewhere
            const msgContainer = document.getElementById('chat-messages');
            msgContainer.innerHTML = '';

            data.messages.forEach(msg => {
                // reuse createMessageDiv so structure & ticks are consistent
                const div = createMessageDiv(msg.content, msg.is_sender, msg.timestamp, msg.status || (msg.is_sender ? 'sent' : ''), msg.id);
                msgContainer.appendChild(div);
            });

            msgContainer.scrollTop = msgContainer.scrollHeight;

            // Ask backend for presence info (after messages load)
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN && otherUserId) {
                chatSocket.send(JSON.stringify({
                    action: 'get_presence',
                    target_user_id: otherUserId
                }));
            }

            // mark as read after loading messages
            markReadNow();
        })
        .catch(err => console.error('Failed to load chat:', err));
}

// Handle back navigation
window.addEventListener('popstate', () => {
    const parts = window.location.pathname.split('/chat/');
    const number = parts[1]?.replace('/', '');
    if (number) loadChat(number, number);
    else {
        document.getElementById('chatArea').innerHTML =
            '<div class="default-chat-view"><h2>Select a chat to start messaging</h2></div>';
    }
});


// ========================== PROFILE MODAL LOGIC ==========================

// Avatar in navbar
const userProfileBtn = document.getElementById('userProfileBtn');

// Modal and its elements
const userProfileModal = document.getElementById('userProfileModal');
const closeUserProfile = document.getElementById('closeUserProfile');

// Inside modal
const editProfileName = document.getElementById('editProfileName');
const editProfileStatus = document.getElementById('editProfileStatus');
const editProfileImage = document.getElementById('editProfileImage');
const nameInput = document.getElementById('nameInput');
const statusInput = document.getElementById('statusInput');
const imageInput = document.getElementById('imageInput');
const profileName = document.getElementById('profileName');
const profileStatus = document.getElementById('profileStatus');
const profileImage = document.getElementById('profileImage');

// -------------------- Modal Open/Close --------------------
if (userProfileBtn && userProfileModal && closeUserProfile) {
    userProfileBtn.addEventListener('click', () => {
        userProfileModal.style.display = 'block';
    });

    closeUserProfile.addEventListener('click', () => {
        saveProfileData(); // 🟢 auto-save before closing
        userProfileModal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === userProfileModal) {
            saveProfileData(); // 🟢 auto-save when clicking outside
            userProfileModal.style.display = 'none';
        }
    });
}

// -------------------- Edit Name --------------------
// -------------------- Edit Name --------------------
if (editProfileName) {
    editProfileName.addEventListener('click', () => {
        profileName.style.display = 'none';
        nameInput.style.display = 'inline-block';
        nameInput.focus();
    });

    // When clicking outside or tabbing out
    nameInput.addEventListener('blur', () => {
        saveNameIfChanged();
    });

    // 🟢 NEW: Save when pressing Enter
    nameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveNameIfChanged();
            nameInput.blur(); // close edit mode
        }
    });

    function saveNameIfChanged() {
        profileName.style.display = 'block';
        nameInput.style.display = 'none';

        const newName = nameInput.value.trim();
        const oldName = profileName.textContent.trim();

        if (newName && newName !== oldName) {
            updateProfileField('name', newName);
        } else {
            nameInput.value = oldName; // restore if empty
        }
    }
}


// -------------------- Edit Status --------------------
// -------------------- Edit Status --------------------
if (editProfileStatus) {
    editProfileStatus.addEventListener('click', () => {
        profileStatus.style.display = 'none';
        statusInput.style.display = 'inline-block';
        statusInput.focus();
    });

    statusInput.addEventListener('blur', () => {
        saveStatusIfChanged();
    });

    // 🟢 NEW: Save when pressing Enter
    statusInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveStatusIfChanged();
            statusInput.blur();
        }
    });

    function saveStatusIfChanged() {
        profileStatus.style.display = 'block';
        statusInput.style.display = 'none';

        const newStatus = statusInput.value.trim();
        const oldStatus = profileStatus.textContent.trim();

        if (newStatus && newStatus !== oldStatus) {
            updateProfileField('status', newStatus);
        } else {
            statusInput.value = oldStatus; // restore old value
        }
    }
}

// -------------------- Edit Image --------------------
if (editProfileImage && imageInput) {
    editProfileImage.addEventListener('click', () => {
        imageInput.click();
    });

    imageInput.addEventListener('change', () => {
        const file = imageInput.files[0];
        if (file) updateProfileField('image', file);
    });
}

// -------------------- Update Profile (AJAX) --------------------
function updateProfileField(field, value) {
    const formData = new FormData();
    formData.append(field, value);

    // include CSRF token
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) formData.append('csrfmiddlewaretoken', csrfToken);

    fetch('/update_profile/', {
        method: 'POST',
        body: formData,
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                console.log('Profile updated:', data);

                // 🟢 update DOM immediately — no reload
                if (field === 'name') {
                    profileName.textContent = data.name;
                    nameInput.value = data.name;

                    // Update navbar name (if exists)
                    const navbarName = document.querySelector('.navbar-user-name');
                    if (navbarName) navbarName.textContent = data.name;
                }

                if (field === 'status') {
                    profileStatus.textContent = data.status;
                    statusInput.value = data.status;
                }

                if (field === 'image') {
                    profileImage.src = data.image_url;

                    const navbarAvatar = document.querySelector('.nav-bottom-avatar img');
                    if (navbarAvatar) navbarAvatar.src = data.image_url;
                }
            } else {
                console.error('Update failed:', data.error);
            }
        })
        .catch((err) => console.error('Profile update failed:', err));
}

// -------------------- Helper: CSRF Token --------------------
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


// -------------------- Auto-Save on Close/Outside --------------------
function saveProfileData() {
    const newName = nameInput.value.trim();
    const newStatus = statusInput.value.trim();

    // Only send if changed
    if (newName !== profileName.textContent.trim()) {
        updateProfileField('name', newName);
    }
    if (newStatus !== profileStatus.textContent.trim()) {
        updateProfileField('status', newStatus);
    }
}
// ===================== USER INFO POPUP LOGIC =====================

// Elements
const userInfoModal = document.getElementById('userInfoModal');
const closeUserInfo = document.getElementById('closeUserInfo');
const contentArea = document.getElementById('contentArea');
const navItems = document.querySelectorAll('#navSidebar .nav-item');

// Profile triggers (username & avatar)
const chatAvatar = document.querySelector('.chat-avatar-large');
const chatName = document.querySelector('.chat-contact-name');

// Function to open modal
function openUserInfoModal(userData) {
    userInfoModal.style.display = 'flex';

    // 🟢 Fill user data dynamically
    document.getElementById('userModalName').textContent = userData.name;
    document.getElementById('userModalStatus').textContent = userData.status;
    document.getElementById('userModalPhone').textContent = userData.phone;
    document.getElementById('userModalAbout').textContent = userData.about;
    const avatar = document.getElementById('userModalAvatar');
    avatar.style.backgroundImage = `url('${userData.image}')`;
    avatar.style.backgroundSize = 'cover';
    avatar.style.backgroundPosition = 'center';
}

// Event listeners to open modal
if (chatAvatar) {
    chatAvatar.addEventListener('click', () => {
        openUserInfoModal({
            name: 'John Doe',
            status: 'Available 🌟',
            phone: '+91 98765 43210',
            about: 'Building cool apps 👨‍💻',
            image: '/static/images/sample_avatar.jpg',
        });
    });
}

if (chatName) {
    chatName.addEventListener('click', () => {
        openUserInfoModal({
            name: 'John Doe',
            status: 'Available 🌟',
            phone: '+91 98765 43210',
            about: 'Building cool apps 👨‍💻',
            image: '/static/images/sample_avatar.jpg',
        });
    });
}

// Close modal
if (closeUserInfo) {
    closeUserInfo.addEventListener('click', () => {
        userInfoModal.style.display = 'none';
    });
}

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === userInfoModal) {
        userInfoModal.style.display = 'none';
    }
});

// Sidebar tab switching
navItems.forEach((item) => {
    item.addEventListener('click', () => {
        // Remove active state from all
        navItems.forEach((i) => i.classList.remove('active'));
        item.classList.add('active');

        // Hide all sections
        document.querySelectorAll('.section').forEach((sec) => {
            sec.style.display = 'none';
        });

        // Show selected
        const sectionId = item.dataset.section + 'Section';
        document.getElementById(sectionId).style.display = 'block';
    });
});


// ------------------ Form Submission ------------------

document.getElementById('chat-form').onsubmit = function (e) {
    e.preventDefault();
    const inputField = document.getElementById('chat-message-input');
    const message = inputField.value.trim();

    // 🧱 Validate input
    if (!message) return;
    if (!otherUserId) {
        alert('Select a chat first.');
        return;
    }

    // 🕒 Prepare timestamp and temp ID
    const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const tempId = 'temp-' + Date.now();

    // ✅ Instantly show the message in UI
    if (typeof createMessageDiv === 'function' && typeof messagesContainer !== 'undefined') {
        const msgDiv = createMessageDiv(message, true, ts, 'sent', tempId);
        messagesContainer.appendChild(msgDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 🟢 Send message via WebSocket
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            action: 'send_message',
            message: message,
            sender_id: meId,
            receiver_id: otherUserId,
        }));
    } else {
        console.error('❌ WebSocket not connected.');
        alert('Connection lost. Try reloading the page.');
    }

    // Clear input field
    inputField.value = '';
};

// ------------------ Popup & Attachment Logic ------------------

const emojiPopup = document.getElementById('emojiPopup');
const emojiButton = document.querySelector('.chat-input-area .fa-smile');
const messageInput = document.getElementById('chat-message-input');
const attachmentPopup = document.getElementById('attachmentPopup');
const attachButton = document.querySelector('.chat-input-area .fa-paperclip');
const attachmentInput = document.getElementById('attachmentInput');



// ================== CSRF TOKEN HELPER ==================
function getCSRFToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith('csrftoken=')) {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken='.length));
                break;
            }
        }
    }
    return cookieValue;
}
const csrfToken = getCSRFToken();

document.addEventListener('DOMContentLoaded', () => {

    // ======= Helper: Close all popups =======
    function closeAllPopups() {
        if (emojiPopup) emojiPopup.style.display = 'none';
        if (attachmentPopup) attachmentPopup.style.display = 'none';
    }

    // =============== EMOJI PICKER LOGIC =================
    if (emojiButton && emojiPopup) {
        emojiButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (emojiPopup.style.display === 'block') {
                emojiPopup.style.display = 'none';
            } else {
                closeAllPopups();
                emojiPopup.style.display = 'block';
            }
        });
    }

    const emojiPicker = document.querySelector('emoji-picker');
    if (emojiPicker) {
        emojiPicker.addEventListener('emoji-click', (event) => {
            messageInput.value += event.detail.unicode;  // Add emoji to input
            messageInput.focus();
        });
    }

    // =============== ATTACHMENT POPUP LOGIC ==============
    if (attachButton && attachmentPopup) {
        attachButton.addEventListener('click', (e) => {
            e.stopPropagation();
            attachmentPopup.style.display =
                attachmentPopup.style.display === 'block' ? 'none' : 'block';
        });
    }

    // Close attachment popup when clicking outside
    window.addEventListener('click', (e) => {
        if (
            attachmentPopup &&
            !attachmentPopup.contains(e.target) &&
            !attachButton.contains(e.target)
        ) {
            attachmentPopup.style.display = 'none';
        }
    });

    // Handle attachment option click
    document.querySelectorAll('.attachment-option').forEach((option) => {
        option.addEventListener('click', () => {
            const type = option.dataset.type;
            attachmentPopup.style.display = 'none';

            let acceptTypes = '';
            if (type === 'photo') acceptTypes = 'image/*';
            else if (type === 'video') acceptTypes = 'video/*';
            else if (type === 'document')
                acceptTypes = '.pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx,.zip,.rar';
            else if (type === 'camera') {
                acceptTypes = 'image/*';
                attachmentInput.capture = 'camera';
            }

            attachmentInput.accept = acceptTypes;
            attachmentInput.dataset.fileType = type;
            attachmentInput.click();
        });
    });


    // ================== UPLOAD FILE & SHOW IMMEDIATELY ==================
    attachmentInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const fileType = attachmentInput.dataset.fileType || 'document';
        const localUrl = URL.createObjectURL(file);

        // Show local preview instantly
        renderAttachmentBubble(localUrl, fileType, true);

        // Prepare form data for upload
        const formData = new FormData();
        formData.append('sender_id', meId);
        formData.append('receiver_id', otherUserId);
        formData.append('file', file);
        formData.append('file_type', fileType);

        try {
            const response = await fetch('/chat/upload_attachment/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            });

            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            console.log('Uploaded successfully:', data);

            // Update preview with final server URL if available
            if (data.attachment_url) {
                const lastMsg = messagesContainer.lastElementChild;
                if (lastMsg && lastMsg.querySelector('img, video, a')) {
                    const element = lastMsg.querySelector('img, video, a');
                    if (element.tagName === 'IMG') element.src = data.attachment_url;
                    else if (element.tagName === 'VIDEO') {
                        const source = element.querySelector('source');
                        if (source) source.src = data.attachment_url;
                        element.load();
                    } else if (element.tagName === 'A') {
                        element.href = data.attachment_url;
                    }
                }
            }
        } catch (err) {
            console.error('⚠️ Upload error:', err);
            alert('Error uploading file. Try again.');
        } finally {
            attachmentInput.value = '';
            attachmentInput.capture = '';
        }
    });

    // ================== CLOSE ON OUTSIDE CLICK ==================
    document.addEventListener('click', (event) => {
        if (
            !event.target.closest('.emoji-popup') &&
            !event.target.closest('.fa-smile') &&
            !event.target.closest('.attachment-popup') &&
            !event.target.closest('.fa-paperclip')
        ) {
            closeAllPopups();
        }
    });
});
// ================== RENDER ATTACHMENT MESSAGE ==================
function renderAttachmentBubble(url, type, isSender) {
    const msgDiv = document.createElement('div');
    msgDiv.className = isSender ? 'msg sent' : 'msg received';

    let html = '';
    if (type === 'image' || url.match(/\.(jpg|jpeg|png|gif|webp)$/i)) {
        html = `<img src="${url}" class="chat-image" alt="image">`;
    } else if (type === 'video' || url.match(/\.(mp4|webm|ogg)$/i)) {
        html = `<video controls class="chat-video"><source src="${url}" type="video/mp4"></video>`;
    } else {
        html = `<a href="${url}" target="_blank" rel="noopener noreferrer">📄 Download File</a>`;
    }

    msgDiv.innerHTML = html;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}