// Scale Agents Dashboard Logic v1.10 - DIAGNOSTIC MODE
console.log('[DEBUG] Script v1.10 starting load...');

// Global state
let currentSessionId = 'demo_session_1';

async function sendMessage() {
    console.log('[DEBUG] sendMessage() called');
    lastMessageText = ''; // Clear deduplication for new request
    const input = document.getElementById('user-input');
    const btn = document.getElementById('send-btn');
    const status = document.getElementById('orchestrator-status');
    
    if (!input || !btn) {
        console.error('[DEBUG] Required DOM elements not found');
        return;
    }

    const text = input.value.trim();
    if (!text) {
        console.log('[DEBUG] No text, ignoring');
        return;
    }

    // Visual feedback
    btn.disabled = true;
    btn.textContent = 'Processing...';
    if (status) status.textContent = 'Running...';

    appendMessage(text, 'user');
    input.value = '';

    try {
        const formData = new FormData();
        formData.append('prompt', text);

        console.log('[DEBUG] Fetching /api/chat...');
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Server returned ' + response.status);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.replace('data: ', '').trim();
                    if (!jsonStr) continue;
                    try {
                        const event = JSON.parse(jsonStr);
                        console.log('[DEBUG] SSE Event:', event);
                        handleEvent(event);
                    } catch (e) {
                        console.error('[DEBUG] JSON Parse Error:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('[DEBUG] Chat Error:', error);
        appendMessage('Error: ' + error.message, 'agent', 'security');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Dispatch';
        if (status) status.textContent = 'Idle';
    }
}

function handleEvent(event) {
    const nodes = {
        'START': document.getElementById('node-start'),
        'control_room_orchestrator': document.getElementById('node-orchestrator'),
        'COMPLETED': document.getElementById('node-completed')
    };

    function setActiveNode(nodeId) {
        Object.values(nodes).forEach(n => n && n.classList.remove('active'));
        if (nodeId.startsWith('replanner_agent')) {
            const replannerNode = document.getElementById('node-replanner');
            if (replannerNode) replannerNode.classList.add('active');
        } else if (nodes[nodeId]) {
            nodes[nodeId].classList.add('active');
        }
    }

    if (event.type === 'status') {
        appendMessage(event.text, 'agent', event.name);
        if (event.name === 'replanning') {
            const replannerNode = document.getElementById('node-replanner');
            if (replannerNode) {
                Object.values(nodes).forEach(n => n && n.classList.remove('active'));
                replannerNode.classList.add('active');
            }
        }
    } else if (event.type === 'adk_event') {
        if (event.node_name && event.node_name !== 'N/A') setActiveNode(event.node_name);
        if (event.output) {
            const output = event.output;
            const text = typeof output === 'string' ? output : (output.report || '');
            if (text) {
                appendMessage(text, 'agent', output.status === 'Blocked' ? 'security' : 'normal');
                setActiveNode('COMPLETED');
            }
        }
    }
}

let lastMessageText = '';

function appendMessage(content, sender, type = 'normal') {
    const chatWindow = document.getElementById('chat-window');
    if (!chatWindow) return;
    
    // Normalize and deduplicate
    const normalized = content.trim();
    if (sender === 'agent' && normalized === lastMessageText) {
        console.log('[DEBUG] Ignoring duplicate agent message');
        return;
    }
    if (sender === 'agent') lastMessageText = normalized;
    
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender} ${type}`;
    
    if (sender === 'agent' && window.marked) {
        msgDiv.innerHTML = marked.parse(content);
    } else {
        msgDiv.textContent = content;
    }
    
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Expose globally
window.sendMessage = sendMessage;

document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] DOM Content Loaded - v1.10');
    const input = document.getElementById('user-input');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});
