// Scale Agents Dashboard Logic v1.13 - COLORED ROLE BUBBLES
console.log('[DEBUG] Script v1.13 starting load...');

// Global state
let currentSessionId = 'demo_session_1';
let thinkingIndicator = null;
let lastMessageText = '';
let currentBubble = null;   // DOM element of the active bubble
let currentBubbleRole = null; // role key of the active bubble
let lastFinalReport = '';   // dedup adk_event final reports

const ROLE_LABELS = {
    control_room: 'Control Room (ADK)',
    planner: 'Planner (LangGraph)',
    executor: 'Executor (CrewAI)',
    a2a: 'A2A Protocol',
};

// Map role to CSS class for the bubble
const ROLE_STYLES = {
    control_room: 'control-room',
    planner: 'planner',
    executor: 'execution',
    a2a: 'a2a',
};

async function sendMessage() {
    console.log('[DEBUG] sendMessage() called');
    lastMessageText = '';
    currentBubble = null;
    currentBubbleRole = null;
    lastFinalReport = '';
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
        removeThinkingIndicator();
        appendMessage('Error: ' + error.message, 'agent', 'security');
    } finally {
        removeThinkingIndicator();
        btn.disabled = false;
        btn.textContent = 'Dispatch';
        if (status) status.textContent = 'Idle';
    }
}

function handleEvent(event) {
    const nodes = {
        'START': document.getElementById('node-start'),
        'control_room_orchestrator': document.getElementById('node-orchestrator'),
        'replanner': document.getElementById('node-replanner'),
        'COMPLETED': document.getElementById('node-completed')
    };

    function setActiveNode(nodeId) {
        Object.values(nodes).forEach(n => n && n.classList.remove('active'));
        if (nodeId.startsWith('replanner_agent')) {
            if (nodes['replanner']) nodes['replanner'].classList.add('active');
        } else if (nodes[nodeId]) {
            nodes[nodeId].classList.add('active');
        }
    }

    if (event.type === 'status') {
        const role = event.role || 'control_room';
        const styleType = event.name === 'replanning' ? 'replanning' : (ROLE_STYLES[role] || 'system');
        appendStatusLine(event.text, role, styleType);

        if (event.name === 'replanning') {
            setActiveNode('replanner');
        }
    } else if (event.type === 'adk_event') {
        if (event.node_name && event.node_name !== 'N/A') setActiveNode(event.node_name);
        if (event.output) {
            removeThinkingIndicator();
            currentBubble = null;
            currentBubbleRole = null;
            const output = event.output;
            const text = typeof output === 'string' ? output : (output.report || '');
            if (text && text !== lastFinalReport) {
                lastFinalReport = text;
                appendMessage(text, 'agent', output.status === 'Blocked' ? 'security' : 'result');
                setActiveNode('COMPLETED');
            }
        }
    }
}

function showThinkingIndicator() {
    removeThinkingIndicator();
    const chatWindow = document.getElementById('chat-window');
    if (!chatWindow) return;
    thinkingIndicator = document.createElement('div');
    thinkingIndicator.className = 'message agent thinking';
    thinkingIndicator.innerHTML = '<span class="thinking-dots"><span></span><span></span><span></span></span>';
    chatWindow.appendChild(thinkingIndicator);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeThinkingIndicator() {
    if (thinkingIndicator && thinkingIndicator.parentNode) {
        thinkingIndicator.parentNode.removeChild(thinkingIndicator);
    }
    thinkingIndicator = null;
}

// Append a status line — merges into the current bubble if same role
function appendStatusLine(content, role, styleType) {
    const chatWindow = document.getElementById('chat-window');
    if (!chatWindow) return;

    // Deduplicate
    const normalized = content.trim();
    if (normalized === lastMessageText) return;
    lastMessageText = normalized;

    removeThinkingIndicator();

    // If same role as current bubble, append a new line to it
    if (currentBubble && currentBubbleRole === role) {
        const line = document.createElement('div');
        line.className = 'status-line';
        if (window.marked) {
            line.innerHTML = marked.parse(content);
        } else {
            line.textContent = content;
        }
        currentBubble.appendChild(line);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        showThinkingIndicator();
        return;
    }

    // New role — create a new bubble
    const msgDiv = document.createElement('div');
    msgDiv.className = `message agent ${styleType}`;

    // Role header
    const label = ROLE_LABELS[role] || role;
    const header = document.createElement('div');
    header.className = 'role-header';
    header.textContent = label;
    msgDiv.appendChild(header);

    // First status line
    const line = document.createElement('div');
    line.className = 'status-line';
    if (window.marked) {
        line.innerHTML = marked.parse(content);
    } else {
        line.textContent = content;
    }
    msgDiv.appendChild(line);

    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    currentBubble = msgDiv;
    currentBubbleRole = role;

    showThinkingIndicator();
}

// Append a standalone message (user messages, final output, errors)
function appendMessage(content, sender, type = 'normal') {
    const chatWindow = document.getElementById('chat-window');
    if (!chatWindow) return;

    // Break the current bubble chain
    currentBubble = null;
    currentBubbleRole = null;

    if (sender === 'agent') removeThinkingIndicator();

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
    console.log('[DEBUG] DOM Content Loaded - v1.13');
    const input = document.getElementById('user-input');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});
