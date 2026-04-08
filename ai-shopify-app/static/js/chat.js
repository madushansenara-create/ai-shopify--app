// AI Shopify客服系统 - 前端JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // 元素引用
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const messageContainer = document.getElementById('messageContainer');
    const quickButtons = document.querySelectorAll('.quick-btn');
    const hoursSavedElement = document.getElementById('hoursSaved');
    const questionsAnsweredElement = document.getElementById('questionsAnswered');
    
    // 统计数据
    let questionsAnswered = 0;
    let hoursSaved = 0;
    
    // 初始化
    function init() {
        console.log('🤖 AI Shopify客服系统已加载');
        
        // 更新统计数据
        updateStats();
        
        // 设置初始欢迎消息（如果还没有）
        if (messageContainer.children.length <= 1) {
            setTimeout(() => {
                addMessage("Welcome to your store's AI customer service! I'm here to help your customers 24/7 with order tracking, returns, shipping info, and product questions. How can I assist you today?", 'bot');
                questionsAnswered++;
                updateStats();
            }, 1000);
        }
    }
    
    // 发送消息函数
    async function sendMessage(text) {
        if (!text.trim()) return;
        
        // 添加用户消息到界面
        addMessage(text, 'user');
        
        // 清空输入框
        messageInput.value = '';
        
        // 显示正在输入动画
        showTypingIndicator();
        
        try {
            // 发送到后端API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: text
                })
            });
            
            const data = await response.json();
            
            // 移除正在输入动画
            removeTypingIndicator();
            
            if (data.response) {
                // 添加AI回复到界面
                addMessage(data.response, 'bot');
                
                // 更新统计
                questionsAnswered++;
                hoursSaved += 0.1; // 每个问题节省约6分钟
                updateStats();
            } else {
                addMessage('Sorry, I encountered an error. Please try again.', 'bot');
            }
            
        } catch (error) {
            removeTypingIndicator();
            addMessage('Network error. Please check your connection.', 'bot');
            console.error('Error:', error);
        }
    }
    
    // 添加消息到界面的函数
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const avatarIcon = sender === 'bot' ? 'fas fa-robot' : 'fas fa-user';
        
        messageDiv.innerHTML = `
            <div class="avatar">
                <i class="${avatarIcon}"></i>
            </div>
            <div class="content">
                ${formatMessage(text)}
            </div>
        `;
        
        messageContainer.appendChild(messageDiv);
        
        // 滚动到底部
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }
    
    // 格式化消息（处理换行和链接）
    function formatMessage(text) {
        if (!text) return '';
        
        // 替换换行符为<br>
        let formatted = text.replace(/\n/g, '<br>');
        
        // 将URL转换为可点击链接
        formatted = formatted.replace(
            /(https?:\/\/[^\s]+)/g,
            '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: #667eea; text-decoration: underline;">$1</a>'
        );
        
        // 将**粗体**转换为<strong>
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        return formatted;
    }
    
    // 显示正在输入动画
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot';
        typingDiv.id = 'typingIndicator';
        
        typingDiv.innerHTML = `
            <div class="avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="content">
                <div class="typing">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        messageContainer.appendChild(typingDiv);
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }
    
    // 移除正在输入动画
    function removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    // 更新统计数据
    function updateStats() {
        if (hoursSavedElement) {
            hoursSavedElement.textContent = hoursSaved.toFixed(1);
        }
        if (questionsAnsweredElement) {
            questionsAnsweredElement.textContent = questionsAnswered;
        }
    }
    
    // 事件监听器
    
    // 发送按钮点击
    sendButton.addEventListener('click', () => {
        sendMessage(messageInput.value);
    });
    
    // 输入框回车键
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(messageInput.value);
        }
    });
    
    // 快捷按钮点击
    quickButtons.forEach(button => {
        button.addEventListener('click', () => {
            const text = button.getAttribute('data-text');
            messageInput.value = text;
            sendMessage(text);
        });
    });
    
    // 模拟Shopify店主看到的效果
    function simulateCustomerQuestions() {
        // 自动演示一些常见问题
        const demoQuestions = [
            "Where is my order?",
            "How do I return an item?",
            "What's your shipping policy?",
            "Do you ship to the UK?",
            "What size should I get?"
        ];
        
        // 每隔一段时间自动演示一个问题
        let questionIndex = 0;
        const demoInterval = setInterval(() => {
            if (questionIndex < demoQuestions.length && questionsAnswered < 3) {
                setTimeout(() => {
                    sendMessage(demoQuestions[questionIndex]);
                }, 2000);
                questionIndex++;
            } else {
                clearInterval(demoInterval);
            }
        }, 10000); // 每10秒演示一个问题
    }
    
    // 开始自动演示（仅在前几个问题后）
    setTimeout(() => {
        if (questionsAnswered < 2) {
            simulateCustomerQuestions();
        }
    }, 5000);
    
    // 初始化系统
    init();
});
