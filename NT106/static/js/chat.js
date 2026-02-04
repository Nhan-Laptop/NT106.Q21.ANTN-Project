document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.getElementById("chat-box");
    const sendForm = document.getElementById("send-form");
    const fileInput = document.getElementById("attachment");
    const fileNameDisplay = document.getElementById("file-name-display");
    const currentUser = document.getElementById("current-user").innerText;

    // Hàm format thời gian kiểu "X phút trước", "X giờ trước"
    function formatTimeAgo(timestamp) {
        if (!timestamp) return 'Không rõ';
        
        try {
            const now = new Date();
            const msgDate = new Date(timestamp);
            const diffMs = now - msgDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 1) return 'Vừa xong';
            if (diffMins < 60) return `${diffMins} phút trước`;
            if (diffHours < 24) return `${diffHours} giờ trước`;
            if (diffDays < 7) return `${diffDays} ngày trước`;
            
            // Hiển thị ngày/tháng nếu quá 7 ngày
            return msgDate.toLocaleDateString('vi-VN') + ' ' + msgDate.toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit'});
        } catch (e) {
            console.error('Error parsing timestamp:', timestamp, e);
            return timestamp;
        }
    }

    // Khởi tạo Socket.IO cho real-time messaging
    const socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server via SocketIO');
    });
    
    socket.on('new_message', function(data) {
        console.log('New message received:', data);
        
        // Fetch lại tin nhắn để đảm bảo sync với DB
        // Delay 200ms để tin kịp lưu vào DB
        setTimeout(function() {
            fetchMessages();
        }, 200);
    });

    // Hiển thị tên file khi chọn ảnh
    fileInput.addEventListener("change", function() {
        if (this.files && this.files.length > 0) {
            fileNameDisplay.innerText = "Đã chọn: " + this.files[0].name;
        }
    });

    // 1. Hàm tải tin nhắn (Polling)
    function fetchMessages() {
        fetch('/api/get_messages')
            .then(response => response.json())
            .then(data => {
                chatBox.innerHTML = ""; // Xóa cũ đi render lại
                
                if (data.length === 0) {
                    chatBox.innerHTML = '<div class="loading-msg">Chưa có tin nhắn. Hãy gửi tin đầu tiên!</div>';
                    return;
                }
                
                data.forEach(msg => {
                    const isMe = msg.sender.includes(currentUser); // Kiểm tra xem có phải mình gửi không
                    const div = document.createElement("div");
                    div.className = isMe ? "message my-message" : "message their-message";
                    
                    // Xử lý link ảnh S3 trong nội dung
                    let content = msg.body || '';
                    if (content.includes("https://") && content.includes(".amazonaws.com/")) {
                        // Regex tìm link S3 để biến thành thẻ <img>
                        const urlRegex = /(https:\/\/[^\s]+\.s3\.[^\s]+\.amazonaws\.com\/[^\s]+)/g;
                        content = content.replace(urlRegex, '<br><img src="$1" class="chat-img"><br>');
                    }
                    
                    // Hiển thị badge nếu tin nhắn được mã hóa
                    const encryptBadge = msg.is_encrypted ? '<span style="color: green; font-size: 11px;">🔒 Encrypted</span>' : '';

                    // Format thời gian kiểu "X phút trước", "X giờ trước"
                    const timeAgo = formatTimeAgo(msg.timestamp);

                    div.innerHTML = `
                        <div class="msg-sender">${msg.sender} ${encryptBadge}</div>
                        <div class="msg-content">${content}</div>
                        <div class="msg-time" style="font-size: 11px; color: #999; margin-top: 5px;">${timeAgo}</div>
                    `;
                    chatBox.appendChild(div);
                });
                // Tự động cuộn xuống dưới cùng
                chatBox.scrollTop = chatBox.scrollHeight;
            })
            .catch(err => {
                console.error("Lỗi tải tin nhắn:", err);
                chatBox.innerHTML = '<div class="loading-msg" style="color: red;">Lỗi tải tin nhắn!</div>';
            });
    }

    // Gọi lần đầu và hẹn giờ 10 giây gọi 1 lần (vì có SocketIO rồi nên giảm polling)
    fetchMessages();
    setInterval(fetchMessages, 10000); 

    // 2. Hàm gửi tin nhắn
    sendForm.addEventListener("submit", function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const btnSend = document.getElementById("btn-send");
        
        btnSend.disabled = true;
        btnSend.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; // Hiệu ứng loading

        fetch('/api/send', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById("msg-body").value = ""; // Xóa ô nhập
                fileInput.value = "";
                fileNameDisplay.innerText = "";
                document.getElementById("encrypt-toggle").checked = false;
                fetchMessages(); // Tải lại tin nhắn ngay
            } else {
                alert("Lỗi gửi tin: " + data.message);
            }
        })
        .catch(err => alert("Lỗi kết nối server!"))
        .finally(() => {
            btnSend.disabled = false;
            btnSend.innerHTML = '<i class="fa-solid fa-paper-plane"></i>';
        });
    });
});