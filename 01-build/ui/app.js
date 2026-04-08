document.addEventListener('DOMContentLoaded', () => {
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
        
        const grid = document.createElement('div');
        grid.className = 'product-grid';
        
        cards.forEach(cardWrapper => {
            const card = cardWrapper.Card;
            if (!card || !card.children) return;
            
            const cardDiv = document.createElement('div');
            cardDiv.className = 'product-card';
            
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
                    let sku = '';
                    if (action && action.context) {
                        const skuCtx = action.context.find(c => c.key === 'sku');
                        if (skuCtx && skuCtx.value && skuCtx.value.literalString) {
                            sku = skuCtx.value.literalString;
                        }
                    }
                    const safeName = name.replace(/"/g, '&quot;');
                    buttonHtml = `<button class="product-link cart-action-btn" style="width: 100%; border: none;" data-sku="${sku}" data-name="${safeName}" data-price="${priceStr}" data-img="${imgSrc}">${child.Button.child.Text.text}</button>`;
                }
            });
            
            cardDiv.innerHTML = `
                ${imgHtml}
                <div class="product-info">
                    ${titleHtml}
                    ${subtitleHtml}
                    ${buttonHtml}
                </div>
            `;
            
            const btn = cardDiv.querySelector('.cart-action-btn');
            if (btn) {
                btn.addEventListener('click', () => {
                    console.log('[DEBUG] Add to Cart clicked');
                    const sku = btn.dataset.sku;
                    const name = btn.dataset.name;
                    const priceStr = btn.dataset.price;
                    const imgSrc = btn.dataset.img;
                    console.log('[DEBUG] Extracted data:', { sku, name, priceStr, imgSrc });
                    window.handleAddToCart(sku, name, priceStr, imgSrc);
                });
            }
            
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
        cart.push({ sku, name, price, imgSrc });
        console.log('[DEBUG] Cart now:', cart);
        updateCartUI();

        // Send message to agent
        userInput.value = `I'll take the item with SKU ${sku}`;
        sendMessage();
    };

    function updateCartUI() {
        if (cartCountSpan) cartCountSpan.textContent = cart.length;
        
        if (!cartItemsContainer) return;
        
        if (cart.length === 0) {
            cartItemsContainer.innerHTML = '<div class="empty-cart-msg">Your cart is empty</div>';
            if (cartTotalSpan) cartTotalSpan.textContent = '0.00';
            return;
        }
        
        cartItemsContainer.innerHTML = '';
        let total = 0;
        
        cart.forEach((item, index) => {
            total += item.price;
            const itemDiv = document.createElement('div');
            itemDiv.className = 'cart-item';
            itemDiv.innerHTML = `
                <img src="${item.imgSrc}" alt="${item.name}" class="cart-item-img" onerror="this.src='https://via.placeholder.com/50x50?text=Failed'">
                <div class="cart-item-info">
                    <div class="cart-item-name">${item.name}</div>
                    <div class="cart-item-price">$${item.price.toFixed(2)}</div>
                </div>
                <button class="remove-item-btn" onclick="window.handleRemoveFromCart(${index})">🗑️</button>
            `;
            cartItemsContainer.appendChild(itemDiv);
        });
        
        if (cartTotalSpan) cartTotalSpan.textContent = total.toFixed(2);
    }

    window.handleRemoveFromCart = function(index) {
        cart.splice(index, 1);
        updateCartUI();
    };

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

            if (data.a2ui_data) {
                renderA2UI(data.a2ui_data);
            } else if (data.found_options && data.found_options.length > 0) {
                appendProductCards(data.found_options);
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
