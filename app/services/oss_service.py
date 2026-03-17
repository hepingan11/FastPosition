from datetime import datetime
from uuid import uuid4
import oss2
from app.config import settings


class OSSService:
    def __init__(self):
        self.enabled = all(
            [
                settings.OSS_ENDPOINT,
                settings.OSS_ACCESS_KEY,
                settings.OSS_SECRET_KEY,
                settings.OSS_BUCKET_NAME,
            ]
        )

    def upload_resume(self, file_name: str, content: bytes, user_id: int) -> str:
        if not self.enabled:
            raise RuntimeError("OSS 未配置完整，无法上传文件")

        auth = oss2.Auth(settings.OSS_ACCESS_KEY, settings.OSS_SECRET_KEY)
        bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)

        ext = ""
        if "." in file_name:
            ext = "." + file_name.rsplit(".", 1)[1].lower()

        object_key = (
            f"resumes/{datetime.now():%Y/%m/%d}/user_{user_id}/"
            f"{uuid4().hex}{ext}"
        )
        bucket.put_object(object_key, content)

        if settings.OSS_DOMAIN:
            return f"{settings.OSS_DOMAIN.rstrip('/')}/{object_key}"

        return f"https://{settings.OSS_BUCKET_NAME}.{settings.OSS_ENDPOINT}/{object_key}"


oss_service = OSSService()
