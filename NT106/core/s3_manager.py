import boto3
import os
import uuid
from botocore.exceptions import NoCredentialsError
import json
from botocore.exceptions import ClientError
class S3Manager:
    def __init__(self):
        # Lấy cấu hình từ biến môi trường (đã load ở app.py hoặc config)
        self.bucket_name = os.getenv('AWS_BUCKET_NAME')
        self.region = os.getenv('AWS_REGION', 'ap-southeast-1')
        
        # Khởi tạo S3 Client
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=self.region
        )
    def load_history(self, filename="chat_history.json"):
        """Tải lịch sử chat từ S3 về"""
        try:
            print(f"[*] Đang tải database từ S3: {filename}...")
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=filename)
            file_content = obj['Body'].read().decode('utf-8')
            return json.loads(file_content)
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                print("[!] Chưa có lịch sử trên S3. Tạo mới.")
                return [] # Trả về list rỗng nếu chưa có file
            else:
                print(f"[ERROR] Không tải được history: {e}")
                return []
        except Exception as e:
            print(f"[ERROR] Lỗi khác: {e}")
            return []

    def save_history(self, data, filename="chat_history.json"):
        """Lưu (Ghi đè) lịch sử chat lên S3"""
        try:
            print(f"[*] Đang lưu database lên S3...")
            json_str = json.dumps(data, ensure_ascii=False, indent=4)
            
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=json_str.encode('utf-8'),
                ContentType='application/json'
            )
            print("[SUCCESS] Đã đồng bộ Database lên Cloud S3.")
            return True
        except Exception as e:
            print(f"[ERROR] Không lưu được history: {e}")
            return False

    def upload_file(self, file_obj, original_filename):
        """
        Upload file lên S3 và trả về URL công khai.
        :param file_obj: Đối tượng file (từ Flask request.files) hoặc đường dẫn file
        :param original_filename: Tên file gốc (ví dụ: anh_meo.jpg)
        :return: String URL (https://...)
        """
        try:
            # 1. Tạo tên file ngẫu nhiên để tránh trùng lặp trên S3
            # Ví dụ: meo.jpg -> 123e4567-e89b...jpg
            ext = original_filename.split('.')[-1]
            unique_filename = f"{uuid.uuid4()}.{ext}"

            # 2. Định nghĩa Content-Type (Quan trọng để trình duyệt hiển thị ảnh thay vì tải về)
            content_type = 'application/octet-stream'
            if ext.lower() in ['jpg', 'jpeg']: content_type = 'image/jpeg'
            elif ext.lower() == 'png': content_type = 'image/png'
            elif ext.lower() == 'gif': content_type = 'image/gif'

            print(f"[*] Đang upload {original_filename} lên S3...")

            # 3. Thực hiện Upload
            # Dùng upload_fileobj nếu là file từ web form, upload_file nếu là đường dẫn
            self.s3.upload_fileobj(
                file_obj,
                self.bucket_name,
                unique_filename,
                ExtraArgs={'ContentType': content_type} 
            )

            # 4. Tạo URL công khai
            # Format chuẩn: https://{bucket}.s3.{region}.amazonaws.com/{key}
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{unique_filename}"
            
            print(f"[SUCCESS] Upload thành công: {url}")
            return url

        except NoCredentialsError:
            print("[ERROR] Không tìm thấy thông tin đăng nhập AWS.")
            return None
        except Exception as e:
            print(f"[ERROR] S3 Upload lỗi: {e}")
            return None

# --- TEST CODE (Chạy độc lập) ---
if __name__ == "__main__":
    # Để test, bạn cần file .env hoặc set biến môi trường trước
    # Giả lập tạo một file dummy để test
    import io
    
    # Tạo một file giả trong bộ nhớ
    dummy_file = io.BytesIO(b"Hello AWS S3 content")
    
    manager = S3Manager()
    if manager.bucket_name:
        url = manager.upload_file(dummy_file, "test.txt")
        print(f"URL Test: {url}")
    else:
        print("Vui lòng cấu hình .env cho AWS trước khi test.")