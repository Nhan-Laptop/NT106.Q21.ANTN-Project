document.addEventListener("DOMContentLoaded", function() {
    const chatBox = document.getElementById("chat-box");
    const sendForm = document.getElementById("send-form");
    const fileInput = document.getElementById("attachment");
    const fileNameDisplay = document.getElementById("file-name-display");
    const currentUser = document.getElementById("current-user").innerText;

    // Khởi tạo Socket.IO cho real-time messaging
    const socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server via SocketIO');
    });
    
    socket.on('new_message', function(data) {
        console.log('New message received:', data);
        fetchMessages(); // Tải lại tin nhắn khi có tin mới
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

                    div.innerHTML = `
                        <div class="msg-sender">${msg.sender} ${encryptBadge}</div>
                        <div class="msg-content">${content}</div>
                        <div class="msg-time" style="font-size: 11px; color: #999; margin-top: 5px;">${new Date(msg.timestamp).toLocaleString()}</div>
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