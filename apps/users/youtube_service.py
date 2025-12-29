import json
from typing import Any, Optional

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


# =========================
# OAuth FLOW
# =========================
def build_flow(client_secrets_file: str, scopes: list[str], redirect_uri: str) -> Flow:
    """
    Создаёт OAuth flow (используется в start/callback).
    """
    flow = Flow.from_client_secrets_file(client_secrets_file, scopes=scopes)
    flow.redirect_uri = redirect_uri
    return flow


def creds_to_json(creds: Credentials) -> str:
    """
    Сериализация credentials для хранения в БД.
    Важно: refresh_token должен сохраниться, иначе upload умрёт после истечения access_token.
    """
    return creds.to_json()


def creds_from_json(creds_json: str) -> Credentials:
    """
    Десериализация credentials из БД.
    """
    data = json.loads(creds_json or "{}")
    return Credentials.from_authorized_user_info(data)


# =========================
# YouTube client
# =========================
def build_youtube(creds: Credentials):
    """
    Создаёт клиента YouTube Data API v3.
    """
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)


# =========================
# Upload
# =========================
def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str = "",
    privacy_status: str = "unlisted",
    category_id: str = "27",  # Education
) -> str:
    """
    Загружает видео в YouTube и возвращает video_id.
    Resumable upload: request.next_chunk()
    """

    body = {
        "snippet": {
            "title": title,
            "description": description or "",
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()  # noqa: F841

        video_id = (response or {}).get("id")
        if not video_id:
            raise RuntimeError("YouTube не вернул videoId.")
        return str(video_id)

    except HttpError as e:
        # YouTube часто отдаёт структурированную ошибку JSON внутри e.content
        raise RuntimeError(_format_google_http_error(e)) from e
    except Exception:
        raise


def _format_google_http_error(e: HttpError) -> str:
    try:
        raw = e.content.decode("utf-8") if hasattr(e, "content") and e.content else ""
        data = json.loads(raw) if raw else {}
        err = (data.get("error") or {})
        message = err.get("message") or str(e)
        errors = err.get("errors") or []
        reason = errors[0].get("reason") if errors else ""
        status = err.get("code") or ""
        extra = f" (reason={reason})" if reason else ""
        return f"YouTube API error {status}: {message}{extra}"
    except Exception:
        return str(e)


# =========================
# Optional: Channel ID / Video status
# =========================
def get_my_channel_id(youtube) -> str:
    """
    Возвращает channel_id аккаунта, которым авторизованы.
    """
    data = youtube.channels().list(part="id", mine=True).execute()
    items = data.get("items") or []
    return items[0].get("id", "") if items else ""


def get_video_processing_status(youtube, video_id: str) -> Optional[str]:
    """
    Проверка статуса обработки.
    Возвращает processingDetails.processingStatus:
    - processing
    - succeeded
    - failed
    или None если видео не найдено/нет доступа.
    """
    try:
        data = youtube.videos().list(part="processingDetails,status", id=video_id).execute()
        items = data.get("items") or []
        if not items:
            return None
        processing = (items[0].get("processingDetails") or {}).get("processingStatus")
        return processing
    except HttpError:
        return None


# youtube_service.py
def get_video_status(youtube, video_id: str) -> dict:
    """
    Возвращает:
    {
        exists: bool,
        processing: 'processing' | 'succeeded' | 'failed' | None
    }
    """
    try:
        resp = youtube.videos().list(
            part="status,processingDetails",
            id=video_id,
            maxResults=1,
        ).execute()

        items = resp.get("items", [])
        if not items:
            return {"exists": False, "processing": None}

        item = items[0]

        processing = (
            item
            .get("processingDetails", {})
            .get("processingStatus")
        )

        return {
            "exists": True,
            "processing": processing,
        }

    except Exception:
        # ❗ НИКОГДА не валим тут error
        return {"exists": False, "processing": None}
