document.addEventListener('DOMContentLoaded', async () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');

    const imageInput = document.getElementById('image-upload');
    const uploadBtnLabel = document.querySelector('.upload-btn');
    const selectedSkus = new Set();
    let sessionId = Math.random().toString(36).substring(2, 15);
    
    // Clear cart on refresh
    fetch('/api/clear-cart').catch(err => console.error('Error clearing cart:', err));

    const personaSelect = document.getElementById('persona-select');
    const personaDetails = document.getElementById('persona-details');
    
    let previousPersona = personaSelect ? personaSelect.value : 'adam';

    const personas = {
        none: {
            title: "None",
            details: "No specific persona. Standard recommendations."
        },
        lucy: {
            title: "Lucy",
            details: "👩 **Lucy** (Mid 20s)\n- **Style**: Trendy, vibrant, boho-chic\n- **Preferences**: Loves bright colors, flowy fabrics, and statement accessories."
        },
        adam: {
            title: "Adam",
            details: "👨 **Adam** (30s)\n- **Style**: Outdoorsy, minimal, practical\n- **Preferences**: Prefers earth tones, durable materials, and functional gear."
        },
        elena: {
            title: "Elena",
            details: "👩 **Elena** (40s)\n- **Style**: Elegant, classic, professional\n- **Preferences**: Prefers neutral colors, high-quality fabrics, and structured silhouettes."
        }
    };

    if (personaSelect) {
        personaSelect.addEventListener('change', () => {
            const val = personaSelect.value;
            
            const modal = document.getElementById('confirm-modal');
            const okBtn = document.getElementById('modal-ok');
            const cancelBtn = document.getElementById('modal-cancel');
            
            modal.classList.add('open');
            
            okBtn.onclick = () => {
                modal.classList.remove('open');
                
                previousPersona = val;
                const p = personas[val] || personas.none;
                personaDetails.innerHTML = typeof marked !== 'undefined' ? marked.parse(p.details) : p.details;
                
                // Update active class on cards
                const personaCards = document.querySelectorAll('.persona-card');
                personaCards.forEach(c => {
                    const isActive = c.dataset.value === val;
                    c.classList.toggle('active', isActive);
                    if (isActive && personaDetails) {
                        c.appendChild(personaDetails);
                    }
                });
                

                
                // Clear chat and restore welcome message
                const chatWindow = document.getElementById('chat-window');
                if (chatWindow) {
                    chatWindow.innerHTML = '<div class="message agent">👋 Hello! I\'m your Personal Shopper. What would you like to shop for today?</div>';
                }
                
                // Generate new session ID to clear server session
                sessionId = Math.random().toString(36).substring(2, 15);
                
                userInput.value = "Show my scenarios";
                sendMessage();
            };
            
            cancelBtn.onclick = () => {
                modal.classList.remove('open');
                personaSelect.value = previousPersona;
            };
        });
        
        // Initialize with default selected persona
        const val = personaSelect.value;
        const p = personas[val] || personas.none;
        personaDetails.innerHTML = typeof marked !== 'undefined' ? marked.parse(p.details) : p.details;
        
        const activeCard = document.querySelector(`.persona-card[data-value="${val}"]`);
        if (activeCard && personaDetails) {
            activeCard.appendChild(personaDetails);
        }
        
        if (val === 'adam') {
            userInput.value = "Show my scenarios";
            sendMessage();
        }
    }

    // Handle persona card clicks
    const personaCards = document.querySelectorAll('.persona-card');
    personaCards.forEach(card => {
        card.addEventListener('click', () => {
            const val = card.dataset.value;
            if (personaSelect && val !== personaSelect.value) {
                personaSelect.value = val;
                personaSelect.dispatchEvent(new Event('change'));
            }
        });
    });

    if (personaDetails) {
        personaDetails.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (link && link.getAttribute('href').startsWith('scenario:')) {
                e.preventDefault();
                const scenario = decodeURIComponent(link.getAttribute('href').substring(9));
                if (userInput) {
                    userInput.value = scenario;
                    userInput.focus();
                }
            }
        });
    }





    if (imageInput && uploadBtnLabel) {
        imageInput.addEventListener('change', () => {
            if (imageInput.files.length > 0) {
                uploadBtnLabel.classList.add('active');
                uploadBtnLabel.textContent = '✅'; // Success feedback
            } else {
                uploadBtnLabel.classList.remove('active');
                uploadBtnLabel.textContent = '📎';
            }
        });
    }

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
        } else if (sender === 'agent') {
            // Render markdown for agent
            msgDiv.innerHTML = typeof marked !== 'undefined' ? marked.parse(content) : content;
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

    function renderA2UI(a2uiData) {
        if (!a2uiData || !a2uiData.beginRendering) return;
        
        const content = a2uiData.beginRendering.content;
        if (!content || (!content.Column && !content.Row)) return;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `message agent product-results`;
        
        const cards = content.Column?.children || content.Row?.children;
        if (!cards) return;
        
        const surfaceId = a2uiData.beginRendering && a2uiData.beginRendering.surfaceId;
        const grid = document.createElement('div');
        if (surfaceId === 'scenario-options') {
            grid.className = 'scenario-list';
        } else if (surfaceId === 'proposed-plan') {
            grid.className = 'proposed-plan-list';
        } else {
            grid.className = 'product-grid';
        }
        
        cards.forEach((cardWrapper, index) => {
            if (cardWrapper.Card && surfaceId === 'scenario-options') {
                const cardDiv = document.createElement('div');
                cardDiv.className = 'scenario-card';
                cardWrapper.Card.children.forEach(child => {
                    if (child.Image) {
                        const img = document.createElement('img');
                        img.src = child.Image.src;
                        img.alt = child.Image.alt;
                        img.className = 'scenario-img';
                        cardDiv.appendChild(img);
                    } else if (child.Text) {
                        const textDiv = document.createElement('div');
                        textDiv.className = `scenario-text ${child.Text.style || ''}`;
                        textDiv.textContent = child.Text.text;
                        cardDiv.appendChild(textDiv);
                    } else if (child.Button) {
                        const btn = document.createElement('button');
                        btn.className = 'scenario-btn';
                        btn.textContent = child.Button.child.Text.text;
                        btn.onclick = () => {
                            const action = child.Button.action;
                            if (action && action.command === 'send_message') {
                                sendMessage(action.params.message, action.params.display_message);
                            }
                        };
                        cardDiv.appendChild(btn);
                    }
                });
                grid.appendChild(cardDiv);
                return;
            } else if (cardWrapper.Image) {
                const img = document.createElement('img');
                img.src = cardWrapper.Image.src;
                img.alt = cardWrapper.Image.alt;
                img.className = 'scenario-img';
                grid.appendChild(img);
            } else if (cardWrapper.Button) {
                const btn = document.createElement('button');
                btn.className = 'scenario-btn';
                btn.textContent = cardWrapper.Button.child.Text.text;
                
                btn.onclick = () => {
                    const action = cardWrapper.Button.action;
                    if (action && action.command === 'send_message') {
                        userInput.value = action.params.message;
                        sendMessage();
                    }
                };
                grid.appendChild(btn);
                return;
            }
            
            const card = cardWrapper.Card;
            if (!card || !card.children) return;
            
            const cardDiv = document.createElement('div');
            let imgHtml = '';
            let titleHtml = '';
            let subtitleHtml = '';
            let buttonHtml = '';
            
            let name = '';
            let priceStr = '';
            let imgSrc = '';
            
            card.children.forEach(child => {
                if (child.Image) {
                    imgSrc = child.Image.src;
                    imgHtml = `<div class="product-img-wrapper"><img src="${imgSrc}" alt="${child.Image.alt}"></div>`;
                } else if (child.Text) {
                    if (child.Text.style === 'title') {
                        name = child.Text.text;
                        titleHtml = `<div class="product-name">${name}</div>`;
                    } else if (child.Text.style === 'subtitle') {
                        priceStr = child.Text.text;
                        subtitleHtml = `<div class="product-meta"><span class="product-price">${priceStr}</span></div>`;
                    } else {
                        subtitleHtml += `<div class="product-desc">${child.Text.text}</div>`;
                    }
                } else if (child.Button) {
                    const action = child.Button.action;
                    if (action && action.command === 'send_message') {
                        buttonHtml += `<button class="msg-action-btn scenario-btn" style="width: 100%; margin-top: 0.5rem;" data-message="${action.params.message}">${child.Button.child.Text.text}</button>`;
                    } else {
                        let sku = '';
                        if (action && action.context) {
                            const skuCtx = action.context.find(c => c.key === 'sku');
                            if (skuCtx && skuCtx.value && skuCtx.value.literalString) {
                                sku = skuCtx.value.literalString;
                            }
                        }
                        const safeName = name.replace(/"/g, '&quot;');
                        const btnText = child.Button.child.Text.text;
                        const btnStyle = 'width: 100%; border: none;';
                        buttonHtml += `<button class="product-link cart-action-btn" style="${btnStyle}" data-sku="${sku}" data-name="${safeName}" data-price="${priceStr}" data-img="${imgSrc}">${btnText}</button>`;
                    }
                }
            });
            
            let isHeader = !imgSrc && !buttonHtml && surfaceId === 'search-results';
            let isFollowUp = !imgSrc && buttonHtml && surfaceId === 'search-results';
            
            if (isHeader) {
                cardDiv.className = 'category-header';
                cardDiv.style.gridColumn = '1 / -1';
                cardDiv.textContent = name;
            } else {
                if (isFollowUp) {
                    cardDiv.className = 'product-card follow-up-card';
                    cardDiv.style.gridColumn = '1 / -1';
                } else if (index === 0 && surfaceId === 'proposed-plan') {
                    cardDiv.className = 'product-card plan-banner';
                    cardDiv.style.gridColumn = '1 / -1';
                    cardDiv.style.background = '#f8f9fa';
                    cardDiv.style.borderLeft = '4px solid #007bff';
                } else if (surfaceId === 'cart-summary') {
                    if (imgSrc) {
                        cardDiv.className = 'product-card horizontal-card';
                    } else {
                        cardDiv.className = 'product-card summary-card';
                        cardDiv.style.gridColumn = '1 / -1';
                    }
                } else {
                    cardDiv.className = 'product-card';
                }
                
                cardDiv.innerHTML = `
                    ${imgHtml}
                    <div class="product-info">
                        ${titleHtml}
                        ${subtitleHtml}
                        ${buttonHtml}
                    </div>
                `;
            }
            
            const cartBtns = cardDiv.querySelectorAll('.cart-action-btn');
            console.log(`DEBUG: Found ${cartBtns.length} cart buttons in card`, cardDiv);
            cartBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const sku = btn.dataset.sku;
                    const name = btn.dataset.name;
                    const priceStr = btn.dataset.price;
                    console.log('DEBUG: Cart button clicked', {sku, name, priceStr});
                    
                    if (selectedSkus.has(sku)) {
                        selectedSkus.delete(sku);
                        btn.textContent = 'Select';
                        btn.style.background = '';
                        btn.style.color = '';
                        
                        userInput.value = `I want to remove ${name} (SKU: ${sku}) from my order.`;
                    } else {
                        selectedSkus.add(sku);
                        btn.textContent = 'Unselect';
                        btn.style.background = '#dc3545';
                        btn.style.color = 'white';
                        
                        userInput.value = `I want to add ${name} (SKU: ${sku}) to my order.`;
                    }
                    sendMessage();
                });
            });
            
            const msgBtns = cardDiv.querySelectorAll('.msg-action-btn');
            console.log(`DEBUG: Found ${msgBtns.length} msg buttons in card`, cardDiv);
            msgBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    userInput.value = btn.dataset.message;
                    sendMessage();
                });
            });
            
            grid.appendChild(cardDiv);
        });
        
        msgDiv.appendChild(grid);
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }





    async function sendMessage(payload = null, displayText = null) {
        const text = (typeof payload === 'string') ? payload : userInput.value.trim();
        const display = displayText !== null ? displayText : text;
        const file = imageInput ? imageInput.files[0] : null;
        
        if (!text && !file) return;

        // Visual feedback for what was sent
        if (display) appendMessage(display, 'user');
        if (file) {
            const imgUrl = URL.createObjectURL(file);
            appendMessage(imgUrl, 'user', true);
        }

        userInput.value = '';
        if (imageInput) imageInput.value = ''; // Reset file input
        if (uploadBtnLabel) {
            uploadBtnLabel.classList.remove('active');
            uploadBtnLabel.textContent = '📎';
        }

        // Show typing indicator
        let loadingText = 'Creating plan...';
        if (text && text.toLowerCase().includes('yes')) {
            loadingText = 'Dispatching Scouts for search...';
        }
        appendMessage(loadingText, 'agent');
        const loadingMsg = chatWindow.lastChild;
        loadingMsg.classList.add('loading');

        try {
            const formData = new FormData();
            if (text) formData.append('prompt', text);
            if (file) formData.append('image', file);
            if (sessionId) formData.append('session_id', sessionId);
            
            if (personaSelect && personaSelect.value !== 'none') {
                formData.append('persona', personaSelect.value);
            }

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

            const surfaceId = data.a2ui_data?.beginRendering?.surfaceId;

            if (surfaceId === 'cart-summary') {
                // For Order Summary, show reply ABOVE
                if (data.reply) {
                    appendMessage(data.reply, 'agent');
                }
                if (data.a2ui_data) {
                    renderA2UI(data.a2ui_data);
                }
            } else {
                // Default behavior (including planning): show reply BELOW
                if (data.a2ui_data) {
                    renderA2UI(data.a2ui_data);
                } else if (data.found_options && data.found_options.length > 0) {
                    appendProductCards(data.found_options);
                }

                if (data.reply) {
                    appendMessage(data.reply, 'agent');
                }
            }

            if (data.status === "Awaiting human approval" || data.status === "Awaiting human selection") {
                const msg = data.message || '';
                if (msg && !msg.includes('sys_speaker') && !msg.includes('You are an agent')) {
                    appendMessage(msg, 'agent');
                } else {
                    appendMessage("👉 Processed your selection. Ready to proceed?", 'agent');
                }
            }

        } catch (error) {
            if (loadingMsg) loadingMsg.remove();
            appendMessage(`Error: ${error.message}`, 'agent');
        }
    }

        // Check for success or canceled payment
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('success') === 'true') {
        setTimeout(() => {
            // Create and show modal
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal-content">
                    <span class="modal-icon">🎉</span>
                    <div class="modal-title">Payment Successful!</div>
                    <div class="modal-message">Thank you for your purchase. Your order is being processed.</div>
                    <button class="modal-close-btn">Continue Shopping</button>
                </div>
            `;
            document.body.appendChild(overlay);
            
            // Trigger reflow for transition
            overlay.offsetHeight;
            overlay.classList.add('open');
            
            const closeBtn = overlay.querySelector('.modal-close-btn');
            closeBtn.addEventListener('click', () => {
                overlay.classList.remove('open');
                setTimeout(() => overlay.remove(), 300);
            });
            
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    overlay.classList.remove('open');
                    setTimeout(() => overlay.remove(), 300);
                }
            });

            // Clear cart on success!
            fetch('/api/clear-cart').catch(err => console.error('Error clearing cart:', err));
            // Remove the query param from URL to avoid duplicate messages on refresh
            window.history.replaceState({}, document.title, window.location.pathname);
        }, 500);
    } else if (urlParams.get('canceled') === 'true') {
        setTimeout(() => {
            appendMessage('❌ **Payment Canceled.** Your cart is preserved.', 'agent');
            window.history.replaceState({}, document.title, window.location.pathname);
        }, 500);
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});
