from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    # auth
    RegisterView,
    EmailTokenObtainPairView,
    MeView,

    # vitrina
    CategoryListView,
    CourseListView,
    CourseDetailView,
    TariffListView,
    LessonListPublicView,

    # token activate + student
    ActivateTokenView,
    MyCoursesView,
    OpenLessonView,
    HomeworkCreateView,
    MyHomeworksView,
    MyHomeworkUpdateView,

    # teacher lessons + archive
    TeacherLessonListCreateView,
    TeacherLessonDetailView,
    TeacherLessonArchiveView,
    TeacherLessonUnarchiveView,

    # teacher homeworks
    TeacherHomeworksView,
    TeacherHomeworkUpdateView,

    # youtube upload create lesson
    TeacherCreateLessonWithUploadView,

    AnalyticsOverviewView,
    CourseDetailAnalyticsView,
    TopLessonsAnalyticsView,
    CoursesAnalyticsView,
    SettingsSeiteView
)

# Если ты уже вынес OAuth в отдельный файл views_youtube.py — подключай так:
# from .views_youtube import YouTubeProjectAuthStartView, YouTubeProjectAuthCallbackView, YouTubeProjectStatusView
# Если OAuth ты ещё не добавлял — просто убери 3 строки ниже.
from .views_youtube import (
    YouTubeProjectAuthStartView,
    YouTubeProjectAuthCallbackView,
    YouTubeProjectStatusView,
    TeacherRefreshLessonYouTubeStatusView,
    TeacherRefreshYouTubeStatusBatchView
    
)

urlpatterns = [
    # =========================
    # AUTH (JWT)
    # =========================
    path("settings/", SettingsSeiteView.as_view(), name="settings"),

    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", EmailTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),

    # =========================
    # PUBLIC VITRINA
    # =========================
    path("categories/", CategoryListView.as_view(), name="categories-list"),
    path("courses/", CourseListView.as_view(), name="courses-list"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="courses-detail"),
    path("tariffs/", TariffListView.as_view(), name="tariffs-list"),
    path("lessons/", LessonListPublicView.as_view(), name="lessons-public-list"),

    # =========================
    # STUDENT: TOKEN + CABINET
    # =========================
    path("access/activate-token/", ActivateTokenView.as_view(), name="access-activate-token"),
    path("me/courses/", MyCoursesView.as_view(), name="me-courses"),
    path("lessons/open/", OpenLessonView.as_view(), name="lessons-open"),
    path("homeworks/", HomeworkCreateView.as_view(), name="homeworks-create"),
    path("me/homeworks/", MyHomeworksView.as_view(), name="me-homeworks"),
    path("me/homeworks/<int:id>/", MyHomeworkUpdateView.as_view(), name="my-homework-detail",),
    # =========================
    # TEACHER: LESSONS CRUD + ARCHIVE
    # =========================
    path("teacher/lessons/", TeacherLessonListCreateView.as_view(), name="teacher-lessons"),
    path("teacher/lessons/<int:pk>/", TeacherLessonDetailView.as_view(), name="teacher-lesson-detail"),
    path("teacher/lessons/<int:pk>/archive/", TeacherLessonArchiveView.as_view(), name="teacher-lesson-archive"),
    path("teacher/lessons/<int:pk>/unarchive/", TeacherLessonUnarchiveView.as_view(), name="teacher-lesson-unarchive"),

    # =========================
    # TEACHER: HOMEWORK CHECK
    # =========================
    path("teacher/homeworks/", TeacherHomeworksView.as_view(), name="teacher-homeworks"),
    path("teacher/homeworks/<int:pk>/", TeacherHomeworkUpdateView.as_view(), name="teacher-homework-update"),

    # =========================
    # TEACHER: CREATE LESSON + UPLOAD VIDEO
    # =========================
    path("teacher/lessons/create-with-upload/", TeacherCreateLessonWithUploadView.as_view(), name="teacher-lesson-upload"),

    # =========================
    # YOUTUBE PROJECT OAUTH (ADMIN ONLY)
    # =========================
    path("youtube/project/oauth/start/", YouTubeProjectAuthStartView.as_view(), name="yt-project-oauth-start"),
    path("youtube/project/oauth/callback/", YouTubeProjectAuthCallbackView.as_view(), name="yt-project-oauth-callback"),
    path("youtube/project/status/", YouTubeProjectStatusView.as_view(), name="yt-project-status"),
    path("youtube/lessons/<int:pk>/refresh-status/", TeacherRefreshLessonYouTubeStatusView.as_view()),
    path("youtube/lessons/refresh-status-batch/", TeacherRefreshYouTubeStatusBatchView.as_view()),

    path("analystic/overview/", AnalyticsOverviewView.as_view()),
    path("analystic/courses/", CoursesAnalyticsView.as_view()),
    path("analystic/courses/<int:course_id>/", CourseDetailAnalyticsView.as_view()),
    path("analystic/lessons/top/", TopLessonsAnalyticsView.as_view()),
]
