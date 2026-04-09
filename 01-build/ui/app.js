document.addEventListener('DOMContentLoaded', async () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');

    const imageInput = document.getElementById('image-upload');
    const uploadBtnLabel = document.querySelector('.upload-btn');

    const cartBtn = document.getElementById('cart-btn');
    const cartSidebar = document.getElementById('cart-sidebar');
    const closeCartBtn = document.getElementById('close-cart-btn');
    const cartItemsContainer = document.getElementById('cart-items');
    const cartCountSpan = document.getElementById('cart-count');
    const cartTotalSpan = document.getElementById('cart-total');
    let cart = [];
    let sessionId = Math.random().toString(36).substring(2, 15);

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
                
                // Clear cart
                cart = [];
                updateCartUI();
                
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
        
        if (val === 'adam') {
            userInput.value = "Show my scenarios";
            sendMessage();
        }
    }

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

    if (cartBtn) {
        cartBtn.addEventListener('click', () => {
            cartSidebar.classList.add('open');
        });
    }

    if (closeCartBtn) {
        closeCartBtn.addEventListener('click', () => {
            cartSidebar.classList.remove('open');
        });
    }

    const checkoutBtn = document.querySelector('.checkout-btn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', async () => {
            console.log('[DEBUG] Checkout clicked');
            if (cart.length === 0) {
                alert('Your cart is empty!');
                return;
            }
            
            try {
                const response = await fetch('/api/create-checkout-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(cart),
                });
                
                const data = await response.json();
                console.log('[DEBUG] Checkout session response:', data);
                
                if (data.url) {
                    window.location.href = data.url;
                } else if (data.error) {
                    alert(`Error creating checkout session: ${data.error}`);
                } else {
                    alert('Failed to create checkout session');
                }
            } catch (error) {
                console.error('[DEBUG] Checkout error:', error);
                alert('Error connecting to payment server');
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
        if (!content || !content.Column) return;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `message agent product-results`;
        
        const cards = content.Column.children;
        if (!cards) return;
        
        const surfaceId = a2uiData.beginRendering && a2uiData.beginRendering.surfaceId;
        const grid = document.createElement('div');
        if (surfaceId === 'scenario-options') {
            grid.className = 'scenario-list';
        } else {
            grid.className = 'product-grid';
        }
        
        cards.forEach((cardWrapper, index) => {
            if (cardWrapper.Button) {
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
                        const isInCart = cart.some(item => item.sku === sku);
                        const btnText = isInCart ? 'Remove from Cart' : child.Button.child.Text.text;
                        const btnStyle = isInCart ? 'width: 100%; border: none; background: #dc3545; color: white;' : 'width: 100%; border: none;';
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
            cartBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const sku = btn.dataset.sku;
                    const name = btn.dataset.name;
                    const priceStr = btn.dataset.price;
                    const imgSrc = btn.dataset.img;
                    
                    const isInCart = cart.some(item => item.sku === sku);
                    
                    if (isInCart) {
                        // Remove from cart
                        cart = cart.filter(item => item.sku !== sku);
                        btn.textContent = 'Add to Cart';
                        btn.style.background = '';
                        btn.style.color = '';
                        updateCartUI();
                        
                        sendCartAction('remove', sku);
                    } else {
                        // Add to cart
                        const priceMatch = priceStr.match(/\$(\d+(\.\d+)?)/);
                        const price = priceMatch ? parseFloat(priceMatch[1]) : 0.0;
                        
                        const existingItem = cart.find(item => item.sku === sku);
                        if (existingItem) {
                            existingItem.quantity = (existingItem.quantity || 1) + 1;
                        } else {
                            cart.push({ sku, name, price, imgSrc, quantity: 1 });
                        }
                        
                        btn.textContent = 'Remove from Cart';
                        btn.style.background = '#dc3545';
                        btn.style.color = 'white';
                        updateCartUI();
                        
                        sendCartAction('add', sku);
                    }
                });
            });
            
            const msgBtns = cardDiv.querySelectorAll('.msg-action-btn');
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

    window.handleAddToCart = function(sku, name, priceStr, imgSrc) {
        console.log('[DEBUG] handleAddToCart called with:', { sku, name, priceStr, imgSrc });
        // Parse price number
        const priceMatch = priceStr.match(/\$(\d+(\.\d+)?)/);
        const price = priceMatch ? parseFloat(priceMatch[1]) : 0.0;
        console.log('[DEBUG] Parsed price:', price);

        // Add to local cart
        const existingItem = cart.find(item => item.sku === sku);
        if (existingItem) {
            existingItem.quantity = (existingItem.quantity || 1) + 1;
        } else {
            cart.push({ sku, name, price, imgSrc, quantity: 1 });
        }
        console.log('[DEBUG] Cart now:', cart);
        updateCartUI();

        // Send message to agent
        userInput.value = `I'll take the item with SKU ${sku}`;
        sendMessage();
    };

    function updateCartUI() {
        // Update total count of items
        const totalCount = cart.reduce((sum, item) => sum + (item.quantity || 1), 0);
        if (cartCountSpan) cartCountSpan.textContent = totalCount;
        
        if (!cartItemsContainer) return;
        
        if (cart.length === 0) {
            cartItemsContainer.innerHTML = '<div class="empty-cart-msg">Your cart is empty</div>';
            if (cartTotalSpan) cartTotalSpan.textContent = '0.00';
            return;
        }
        
        cartItemsContainer.innerHTML = '';
        let total = 0;
        
        cart.forEach((item, index) => {
            const quantity = item.quantity || 1;
            total += item.price * quantity;
            const itemDiv = document.createElement('div');
            itemDiv.className = 'cart-item';
            itemDiv.innerHTML = `
                <img src="${item.imgSrc}" alt="${item.name}" class="cart-item-img" onerror="this.src='https://via.placeholder.com/50x50?text=Failed'">
                <div class="cart-item-info">
                    <div class="cart-item-name">${item.name}</div>
                    <div class="cart-item-price">$${item.price.toFixed(2)}</div>
                    <div class="cart-item-quantity">
                        <button class="qty-btn" onclick="window.handleChangeQuantity(${index}, -1)">-</button>
                        <span class="qty-val">${quantity}</span>
                        <button class="qty-btn" onclick="window.handleChangeQuantity(${index}, 1)">+</button>
                    </div>
                </div>
                <button class="remove-item-btn" onclick="window.handleRemoveFromCart(${index})">🗑️</button>
            `;
            cartItemsContainer.appendChild(itemDiv);
        });
        
        if (cartTotalSpan) cartTotalSpan.textContent = total.toFixed(2);
    }

    window.handleChangeQuantity = function(index, delta) {
        if (!cart[index].quantity) cart[index].quantity = 1;
        cart[index].quantity += delta;
        if (cart[index].quantity <= 0) {
            cart.splice(index, 1);
        }
        updateCartUI();
    };

    window.handleRemoveFromCart = function(index) {
        cart.splice(index, 1);
        updateCartUI();
    };

    async function sendCartAction(action, sku) {
        try {
            const formData = new FormData();
            formData.append('action', action);
            formData.append('sku', sku);

            const response = await fetch('/api/cart', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                console.error(`Server returned ${response.status}`);
                return;
            }

            const data = await response.json();
            console.log('[DEBUG] Cart action response:', data);
        } catch (error) {
            console.error('Error sending cart action:', error);
        }
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        const file = imageInput ? imageInput.files[0] : null;
        
        if (!text && !file) return;

        // Visual feedback for what was sent
        if (text) appendMessage(text, 'user');
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

            if (data.a2ui_data) {
                renderA2UI(data.a2ui_data);
            } else if (data.found_options && data.found_options.length > 0) {
                appendProductCards(data.found_options);
            }

            if (data.status === "Awaiting human approval" || data.status === "Awaiting human selection") {
                appendMessage(data.message || `Awaiting approval: check server logs`, 'agent');
            } else if (data.reply) {
                appendMessage(data.reply, 'agent');
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
            cart = [];
            updateCartUI();
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
