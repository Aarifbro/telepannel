<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Bot UI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #3e3e3e;
        }
        .message-panel {
            flex-grow: 1;
            padding: 1rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            background-image: url('https://i.ibb.co/6P0Y9x4/1000079557.jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
        }
        .message-bubble {
            max-width: 80%;
            padding: 10px 15px;
            border-radius: 20px;
            position: relative;
            word-wrap: break-word;
        }
        .bot-message {
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            align-self: flex-start;
            border-bottom-left-radius: 5px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .user-message {
            background-color: rgba(220, 248, 198, 0.9);
            color: #333;
            align-self: flex-end;
            border-bottom-right-radius: 5px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .bot-message .timestamp, .user-message .timestamp {
            font-size: 0.7rem;
            color: #888;
            margin-top: 4px;
            text-align: right;
            display: block;
        }
        .btn-panel {
            padding: 1rem;
            background-color: #1a1a1a;
            border-top: 1px solid #333;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }
        .btn {
            background-color: #333;
            color: #fff;
            padding: 12px 18px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            font-weight: 500;
            transition: background-color 0.2s, transform 0.1s;
        }
        .btn:hover {
            background-color: #444;
            transform: translateY(-1px);
        }
        .btn-full {
            width: 100%;
        }
        .btn-half {
            width: calc(50% - 4px);
        }
        .btn-third {
            width: calc(33.333% - 6px);
        }
        .icon {
            margin-right: 8px;
            font-size: 1.2rem;
        }
        .panel-container {
            min-height: 80vh;
        }

        /* Styles for the new bottom nav panel */
        .bottom-nav-container {
            background-color: #1a1a1a;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            color: #aaa;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            text-align: center;
            transition: color 0.2s;
            flex: 1;
        }
        .nav-item:hover {
            color: #fff;
        }
        .nav-icon {
            font-size: 1.5rem;
            margin-bottom: 4px;
        }
        .nav-cart {
            background-color: #34c759;
            color: #fff;
            padding: 1rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            font-size: 2rem;
            cursor: pointer;
            transition: transform 0.2s;
            transform: translateY(-25%); /* Lift it above the panel */
        }
        .nav-cart:hover {
            transform: translateY(-28%) scale(1.05);
        }
    </style>
</head>
<body class="bg-gray-900 flex items-center justify-center min-h-screen text-gray-100">

    <div class="w-full max-w-sm sm:max-w-md md:max-w-lg lg:max-w-xl mx-4 my-8 bg-[#2d2d2d] shadow-lg rounded-3xl overflow-hidden flex flex-col panel-container">

        <!-- Bot Header -->
        <div class="bg-[#2d2d2d] text-white p-4 flex items-center shadow-md border-b border-[#3e3e3e]">
            <div class="h-10 w-10 bg-purple-500 rounded-full flex items-center justify-center text-xl font-bold mr-3">👻</div>
            <div>
                <h1 class="font-semibold text-lg">Deleted Account</h1>
                <p class="text-sm text-gray-400">Bot</p>
            </div>
        </div>

        <!-- Chat Panel -->
        <div id="message-panel" class="message-panel">
            <!-- Messages will be injected here by JS -->
        </div>

        <!-- Dynamic Button Panel -->
        <div id="dynamic-btn-panel" class="btn-panel">
            <!-- Sub-menu buttons (e.g., crypto options) will be injected here by JS -->
        </div>

        <!-- Fixed Bottom Navigation Bar -->
        <div id="bottom-nav" class="bottom-nav-container">
            <div class="nav-item" data-action="Shop">
                <span class="nav-icon">🛍️</span>
                <span>Shop</span>
            </div>
            <div class="nav-item" data-action="Add money">
                <span class="nav-icon">💰</span>
                <span>Add money</span>
            </div>
            <div class="nav-cart" data-action="Cart">
                <span class="nav-icon">🛒</span>
            </div>
            <div class="nav-item" data-action="FAQ">
                <span class="nav-icon">❓</span>
                <span>FAQ</span>
            </div>
            <div class="nav-item" data-action="Help">
                <span class="nav-icon">🆘</span>
                <span>Help</span>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const messagePanel = document.getElementById('message-panel');
            const dynamicBtnPanel = document.getElementById('dynamic-btn-panel');
            const bottomNav = document.getElementById('bottom-nav');

            // --- UI Rendering Functions ---
            function createMessage(text, type) {
                const messageDiv = document.createElement('div');
                messageDiv.classList.add('message-bubble', type === 'bot' ? 'bot-message' : 'user-message');
                messageDiv.innerHTML = `${text}<span class="timestamp">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>`;
                messagePanel.appendChild(messageDiv);
                messagePanel.scrollTop = messagePanel.scrollHeight;
            }

            function createButton(text, action, icon = '', widthClass = 'btn-half') {
                const button = document.createElement('button');
                button.classList.add('btn', widthClass);
                button.setAttribute('data-action', action);
                button.innerHTML = `${icon ? `<span class="icon">${icon}</span>` : ''}${text}`;
                button.addEventListener('click', handleButtonClick);
                return button;
            }
            
            function clearDynamicPanel() {
                dynamicBtnPanel.innerHTML = '';
                dynamicBtnPanel.style.display = 'none';
            }
            
            function showDynamicPanel() {
                 dynamicBtnPanel.style.display = 'flex';
            }

            function renderTopUpMenu() {
                dynamicBtnPanel.innerHTML = '';
                dynamicBtnPanel.appendChild(createButton('BTC', 'BTC', '₿', 'btn-full'));
                dynamicBtnPanel.appendChild(createButton('LTC', 'LTC', 'Ł', 'btn-full'));
                dynamicBtnPanel.appendChild(createButton('SOL', 'SOL', '◎', 'btn-full'));
                dynamicBtnPanel.appendChild(createButton('ETH', 'ETH', 'Ξ', 'btn-full'));
                dynamicBtnPanel.appendChild(createButton('BNB (Binance Coin)', 'BNB', '', 'btn-full'));
                dynamicBtnPanel.appendChild(createButton('Back', 'Back', '←', 'btn-full'));
                showDynamicPanel();
            }

            function renderCartMenu() {
                dynamicBtnPanel.innerHTML = '';
                const cartSummary = document.createElement('div');
                cartSummary.classList.add('w-full', 'bg-gray-700', 'text-gray-300', 'p-4', 'rounded-xl', 'text-sm', 'leading-tight');
                cartSummary.innerHTML = `
                    <p><span class="font-bold">US</span> Balance: $2K - $10K NON VBV | Total: $70.00 | Qty: 1</p>
                    <p class="mt-2 font-bold">Grand total: 70.00 $</p>
                `;
                dynamicBtnPanel.appendChild(cartSummary);
                dynamicBtnPanel.appendChild(createButton('Confirm', 'Confirm Cart', '✅', 'btn-half'));
                dynamicBtnPanel.appendChild(createButton('Cancel', 'Cancel Cart', '❌', 'btn-half'));
                showDynamicPanel();
            }

            // --- Bot Logic ---
            const botResponses = {
                'start': "Hi, this is the Squirrel store. You can view all product categories by clicking the buttons below.",
                'Shop': "Welcome to the shop! Please select a product category from the list.",
                'Add money': "Choose a top-up method:",
                'FAQ': "You've selected the FAQ. Here are the answers to our most common questions.",
                'Help': "You've selected Help. Please type your question, and a support agent will assist you shortly.",
                'BTC': "You have chosen to top up with BTC. Please send the funds to the provided address.",
                'LTC': "You have chosen to top up with LTC. Please send the funds to the provided address.",
                'SOL': "You have chosen to top up with SOL. Please send the funds to the provided address.",
                'ETH': "You have chosen to top up with ETH. Please send the funds to the provided address.",
                'BNB': "You have chosen to top up with BNB. Please send the funds to the provided address.",
                'Confirm Cart': "Your cart has been confirmed and your purchase is complete. Thank you!",
                'Cancel Cart': "Your cart has been cleared. You can continue shopping.",
            };

            function handleButtonClick(event) {
                const action = event.target.getAttribute('data-action');
                createMessage(action, 'user');
                
                setTimeout(() => {
                    clearDynamicPanel();
                    if (action === "Add money") {
                        createMessage(botResponses[action], 'bot');
                        renderTopUpMenu();
                    } else if (action === "Cart") {
                        createMessage("Checkout cart?", 'bot');
                        renderCartMenu();
                    } else if (botResponses[action]) {
                        createMessage(botResponses[action], 'bot');
                    } else {
                        createMessage("Sorry, I don't have a response for that action yet.", 'bot');
                    }
                }, 1000);
            }

            // Event listener for the bottom navigation bar buttons
            bottomNav.querySelectorAll('.nav-item, .nav-cart').forEach(item => {
                item.addEventListener('click', handleButtonClick);
            });

            // Initial state on page load
            window.onload = () => {
                createMessage("Hi, this is the Squirrel store. You can view all product categories by clicking the buttons below.", 'bot');
                // The main menu is now static at the bottom, so no need to render it dynamically.
            };
        });
    </script>
</body>
</html>
