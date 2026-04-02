document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');

    const imageInput = document.getElementById('image-upload');
    const uploadBtnLabel = document.querySelector('.upload-btn');

    imageInput.addEventListener('change', () => {
        if (imageInput.files.length > 0) {
            uploadBtnLabel.classList.add('active');
            uploadBtnLabel.textContent = '✅'; // Success feedback
        } else {
            uploadBtnLabel.classList.remove('active');
            uploadBtnLabel.textContent = '📎';
        }
    });

    function appendMessage(content, sender, isImage = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        
        if (isImage) {
            const img = document.createElement('img');
            img.src = content;
            img.style.maxWidth = '250px';
            img.style.borderRadius = '14px';
            img.style.boxShadow = '0 4px 15px rgba(0,0,0,0.05)';
            msgDiv.appendChild(img);
        } else {
            msgDiv.textContent = content;
        }
        
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function appendProductCards(categories) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message agent product-results`;
        
        categories.forEach(cat => {
            const catHeader = document.createElement('div');
            catHeader.className = 'category-header';
            catHeader.textContent = `🔍 Category: ${cat.category}`;
            msgDiv.appendChild(catHeader);
            
            const grid = document.createElement('div');
            grid.className = 'product-grid';
            
            // Limit to top 3 items per category to avoid clutter
            const topItems = cat.options.slice(0, 3);
            
            topItems.forEach(item => {
                const card = document.createElement('div');
                card.className = 'product-card';
                
                // Fallback image if missing or broken
                const imgSrc = item.img_url || 'https://via.placeholder.com/300x200?text=No+Image';
                
                card.innerHTML = `
                    <div class="product-img-wrapper">
                        <img src="${imgSrc}" alt="${item.name}" onerror="this.src='https://via.placeholder.com/300x200?text=Image+Load+Failed'">
                    </div>
                    <div class="product-info">
                        <div class="product-name" title="${item.name}">${item.name}</div>
                        <div class="product-meta">
                            <span class="product-price">$${item.price}</span>
                            <span class="product-match">${Math.round((item.similarity || 0) * 100)}% Match</span>
                        </div>
                        <a href="${item.url}" target="_blank" class="product-link">View Listing 🔗</a>
                    </div>
                `;
                grid.appendChild(card);
            });
            msgDiv.appendChild(grid);
        });
        
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        const file = imageInput.files[0];
        
        if (!text && !file) return;

        // Visual feedback for what was sent
        if (text) appendMessage(text, 'user');
        if (file) {
            const imgUrl = URL.createObjectURL(file);
            appendMessage(imgUrl, 'user', true);
        }

        userInput.value = '';
        imageInput.value = ''; // Reset file input
        uploadBtnLabel.classList.remove('active');
        uploadBtnLabel.textContent = '📎';

        // Show typing indicator
        appendMessage('Thinking...', 'agent');
        const loadingMsg = chatWindow.lastChild;

        try {
            const formData = new FormData();
            if (text) formData.append('prompt', text);
            if (file) formData.append('image', file);

            const response = await fetch('/api/chat', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();
            
            // Remove typing indicator
            loadingMsg.remove();

            if (data.status === "Awaiting human approval" || data.status === "Awaiting human selection") {
                appendMessage(data.message || `Awaiting approval: check server logs`, 'agent');
            } else if (data.reply) {
                appendMessage(data.reply, 'agent');
            } else if (data.status && !data.found_options) {
                appendMessage(`Status: ${data.status}`, 'agent');
            }

            if (data.found_options && data.found_options.length > 0) {
                appendProductCards(data.found_options);
            }

        } catch (error) {
            if (loadingMsg) loadingMsg.remove();
            appendMessage(`Error: ${error.message}`, 'agent');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});