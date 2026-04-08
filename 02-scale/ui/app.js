document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');
    const statusVal = document.getElementById('orchestrator-status');

    // Node elements for state visualization
    const nodes = {
        'START': document.getElementById('node-start'),
        'control_room_orchestrator': document.getElementById('node-orchestrator'),
        'replanner_agent': document.getElementById('node-replanner'),
        'COMPLETED': document.getElementById('node-completed')
    };

    function setActiveNode(nodeId) {
        Object.values(nodes).forEach(node => node.classList.remove('active'));
        if (nodes[nodeId]) {
            nodes[nodeId].classList.add('active');
        } else if (nodeId.startsWith('replanner_agent')) {
            nodes['replanner_agent'].classList.add('active');
        }
    }

    function appendMessage(content, sender, type = 'normal') {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender} ${type}`;
        
        if (sender === 'agent') {
            msgDiv.innerHTML = marked.parse(content);
        } else {
            msgDiv.textContent = content;
        }
        
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage(text, 'user');
        userInput.value = '';
        
        setActiveNode('control_room_orchestrator');
        statusVal.textContent = 'Running...';
        statusVal.className = 'value running';

        try {
            const formData = new FormData();
            formData.append('prompt', text);

            const response = await fetch('/api/chat', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);

            const data = await response.json();
            
            // Process Events for detailed visualization
            data.events.forEach(event => {
                if (event.node_name !== 'N/A') {
                    setActiveNode(event.node_name);
                }
                
                // If it's a replanning event, highlight it
                if (event.node_name.startsWith('replanner_agent')) {
                    appendMessage(`💡 **Re-planner Triggered:** Broadening objective...`, 'agent', 'replanning');
                }
            });

            // Handle final outcome
            const outcome = data.final_outcome;
            let type = 'normal';
            
            if (outcome.includes('SECURITY BLOCK')) {
                type = 'security';
                setActiveNode('COMPLETED'); // End on security block
            } else if (outcome.includes('Failed')) {
                setActiveNode('COMPLETED');
            } else {
                setActiveNode('COMPLETED');
            }

            appendMessage(outcome, 'agent', type);
            statusVal.textContent = 'Idle';
            statusVal.className = 'value idle';

        } catch (error) {
            appendMessage(`Error: ${error.message}`, 'agent', 'security');
            statusVal.textContent = 'Error';
            statusVal.className = 'value idle';
            setActiveNode('START');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});
