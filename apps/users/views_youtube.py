# views_youtube.py
from datetime import timedelta
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProjectYouTubeCredential, Lesson
from .permissions import IsAdminRole, IsTeacher
from .youtube_service import (
    build_flow,
    creds_to_json,
    creds_from_json,
    build_youtube,
    get_my_channel_id,
    get_video_status,
)


YOUTUBE_GRACE_SECONDS = 600  # ⏳ 10 минут — YouTube может тупить


def _get_setting(name: str):
    val = getattr(settings, name, None)
    if not val:
        raise RuntimeError(f"Missing setting: {name}")
    return val


# =========================
# OAUTH START (ADMIN)
# =========================
class YouTubeProjectAuthStartView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        flow = build_flow(
            client_secrets_file=str(_get_setting("YOUTUBE_CLIENT_SECRETS_FILE")),
            scopes=list(_get_setting("YOUTUBE_SCOPES")),
            redirect_uri=str(_get_setting("YOUTUBE_REDIRECT_URI")),
        )

        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        request.session["yt_oauth_state"] = state
        return redirect(auth_url)


# =========================
# OAUTH CALLBACK
# =========================
class YouTubeProjectAuthCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        flow = build_flow(
            client_secrets_file=str(_get_setting("YOUTUBE_CLIENT_SECRETS_FILE")),
            scopes=list(_get_setting("YOUTUBE_SCOPES")),
            redirect_uri=str(_get_setting("YOUTUBE_REDIRECT_URI")),
        )

        try:
            flow.fetch_token(
                authorization_response=request.build_absolute_uri()
            )
        except Exception as e:
            return Response(
                {"detail": "OAuth error", "error": str(e)},
                status=400,
            )

        creds = flow.credentials
        creds_json = creds_to_json(creds)

        try:
            youtube = build_youtube(creds)
            channel_id = get_my_channel_id(youtube) or ""
        except Exception:
            channel_id = ""

        obj, _ = ProjectYouTubeCredential.objects.get_or_create(id=1)
        obj.credentials_json = creds_json
        obj.channel_id = channel_id
        obj.save()

        return Response(
            {"connected": True, "channel_id": channel_id},
            status=200,
        )


# =========================
# STATUS
# =========================
class YouTubeProjectStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        obj = ProjectYouTubeCredential.objects.first()
        if not obj:
            return Response({"connected": False})
        return Response(
            {
                "connected": True,
                "channel_id": obj.channel_id,
                "updated_at": obj.updated_at,
            }
        )


# =========================
# TEACHER: REFRESH ONE
# =========================
class TeacherRefreshLessonYouTubeStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def get(self, request, pk):
        lesson = Lesson.objects.filter(
            pk=pk,
            course__instructor=request.user,
        ).first()

        if not lesson:
            return Response({"detail": "Урок не найден"}, status=404)

        if not lesson.youtube_video_id:
            lesson.youtube_status = "idle"
            lesson.save(update_fields=["youtube_status"])
            return Response({"youtube_status": "idle"})

        proj = ProjectYouTubeCredential.objects.first()
        if not proj:
            return Response({"detail": "YouTube не подключён"}, status=400)

        youtube = build_youtube(creds_from_json(proj.credentials_json))
        info = get_video_status(youtube, lesson.youtube_video_id)

        now = timezone.now()
        uploaded_at = lesson.youtube_uploaded_at or lesson.created_at
        delta = (now - uploaded_at).total_seconds()

        # 🔑 ГЛАВНАЯ ЛОГИКА
        if not info["exists"]:
            if delta < YOUTUBE_GRACE_SECONDS:
                lesson.youtube_status = "processing"
                lesson.youtube_error = ""
            else:
                lesson.youtube_status = "error"
                lesson.youtube_error = "Видео не найдено YouTube API"
        else:
            p = info["processing"]
            if p == "succeeded":
                lesson.youtube_status = "ready"
                lesson.youtube_error = ""
            elif p == "failed":
                lesson.youtube_status = "error"
                lesson.youtube_error = "YouTube processing failed"
            else:
                lesson.youtube_status = "processing"
                lesson.youtube_error = ""

        lesson.save(update_fields=["youtube_status", "youtube_error"])

        return Response(
            {
                "lesson_id": lesson.id,
                "youtube_video_id": lesson.youtube_video_id,
                "youtube_status": lesson.youtube_status,
                "youtube_error": lesson.youtube_error,
            }
        )


# =========================
# TEACHER: REFRESH BATCH
# =========================
class TeacherRefreshYouTubeStatusBatchView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request):
        lesson_ids = request.data.get("lesson_ids", [])
        lessons = Lesson.objects.filter(
            id__in=lesson_ids,
            course__instructor=request.user,
        )

        proj = ProjectYouTubeCredential.objects.first()
        if not proj:
            return Response({"detail": "YouTube не подключён"}, status=400)

        youtube = build_youtube(creds_from_json(proj.credentials_json))
        now = timezone.now()
        items = []

        for lesson in lessons:
            if not lesson.youtube_video_id:
                lesson.youtube_status = "idle"
                lesson.save(update_fields=["youtube_status"])
                items.append({"lesson_id": lesson.id, "youtube_status": "idle"})
                continue

            info = get_video_status(youtube, lesson.youtube_video_id)
            uploaded_at = lesson.youtube_uploaded_at or lesson.created_at
            delta = (now - uploaded_at).total_seconds()

            if not info["exists"]:
                if delta < YOUTUBE_GRACE_SECONDS:
                    status_ = "processing"
                    error = ""
                else:
                    status_ = "error"
                    error = "Видео не найдено YouTube API"
            else:
                p = info["processing"]
                if p == "succeeded":
                    status_ = "ready"
                    error = ""
                elif p == "failed":
                    status_ = "error"
                    error = "YouTube processing failed"
                else:
                    status_ = "processing"
                    error = ""

            lesson.youtube_status = status_
            lesson.youtube_error = error
            lesson.save(update_fields=["youtube_status", "youtube_error"])

            items.append(
                {
                    "lesson_id": lesson.id,
                    "youtube_video_id": lesson.youtube_video_id,
                    "youtube_status": status_,
                    "youtube_error": error,
                }
            )

        return Response({"items": items})
