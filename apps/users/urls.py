from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    # auth
    RegisterView,
    EmailTokenObtainPairView,
    MeView,

    # vitrina
    CategoryListCreateView,
    CategoryDetailView,
    CourseListCreateView,
    CourseDetailView,
    TariffListView,
    LessonListPublicView,

    # student
    ActivateTokenView,
    MyCoursesView,
    OpenLessonView,
    HomeworkCreateView,
    MyHomeworksView,
    MyHomeworkUpdateView,

    # teacher lessons
    TeacherLessonListCreateView,
    TeacherLessonDetailView,
    TeacherLessonArchiveView,
    TeacherLessonUnarchiveView,

    # teacher homeworks
    TeacherHomeworksView,
    TeacherHomeworkUpdateView,

    # youtube upload
    TeacherCreateLessonWithUploadView,

    # analytics
    AnalyticsOverviewView,
    CourseDetailAnalyticsView,
    TopLessonsAnalyticsView,
    CoursesAnalyticsView,

    # settings
    SettingsSeiteView,
)

from .views_youtube import (
    YouTubeProjectAuthStartView,
    YouTubeProjectAuthCallbackView,
    YouTubeProjectStatusView,
    TeacherRefreshLessonYouTubeStatusView,
    TeacherRefreshYouTubeStatusBatchView,
)

urlpatterns = [
    # =========================
    # SETTINGS
    # =========================
    path("settings/", SettingsSeiteView.as_view(), name="settings"),

    # =========================
    # AUTH (JWT)
    # =========================
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", EmailTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),

    # =========================
    # PUBLIC VITRINA
    # =========================
    path("categories/", CategoryListCreateView.as_view(), name="categories-list-create"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="categories-detail"),
    path("courses/", CourseListCreateView.as_view(), name="courses-list-create"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="courses-detail"),
    path("tariffs/", TariffListView.as_view(), name="tariffs-list"),
    path("lessons/", LessonListPublicView.as_view(), name="lessons-public-list"),

    # =========================
    # STUDENT
    # =========================
    path("access/activate-token/", ActivateTokenView.as_view(), name="access-activate-token"),
    path("me/courses/", MyCoursesView.as_view(), name="me-courses"),
    path("lessons/open/", OpenLessonView.as_view(), name="lessons-open"),
    path("homeworks/", HomeworkCreateView.as_view(), name="homeworks-create"),
    path("me/homeworks/", MyHomeworksView.as_view(), name="me-homeworks"),
    path("me/homeworks/<int:id>/", MyHomeworkUpdateView.as_view(), name="me-homework-update"),

    # =========================
    # TEACHER: LESSONS
    # =========================
    path("teacher/lessons/", TeacherLessonListCreateView.as_view(), name="teacher-lessons"),
    path("teacher/lessons/<int:pk>/", TeacherLessonDetailView.as_view(), name="teacher-lesson-detail"),
    path("teacher/lessons/<int:pk>/archive/", TeacherLessonArchiveView.as_view(), name="teacher-lesson-archive"),
    path("teacher/lessons/<int:pk>/unarchive/", TeacherLessonUnarchiveView.as_view(), name="teacher-lesson-unarchive"),

    # =========================
    # TEACHER: HOMEWORKS
    # =========================
    path("teacher/homeworks/", TeacherHomeworksView.as_view(), name="teacher-homeworks"),
    path("teacher/homeworks/<int:pk>/", TeacherHomeworkUpdateView.as_view(), name="teacher-homework-update"),

    # =========================
    # TEACHER: UPLOAD VIDEO
    # =========================
    path(
        "teacher/lessons/create-with-upload/",
        TeacherCreateLessonWithUploadView.as_view(),
        name="teacher-lesson-upload",
    ),

    # =========================
    # YOUTUBE PROJECT (ADMIN / TEACHER)
    # =========================
    path(
        "youtube/project/oauth/start/",
        YouTubeProjectAuthStartView.as_view(),
        name="youtube-project-oauth-start",
    ),
    path(
        "youtube/project/oauth/callback/",
        YouTubeProjectAuthCallbackView.as_view(),
        name="youtube-project-oauth-callback",
    ),
    path(
        "youtube/project/status/",
        YouTubeProjectStatusView.as_view(),
        name="youtube-project-status",
    ),
    path(
        "youtube/lessons/<int:pk>/refresh-status/",
        TeacherRefreshLessonYouTubeStatusView.as_view(),
        name="youtube-lesson-refresh-status",
    ),
    path(
        "youtube/lessons/refresh-status-batch/",
        TeacherRefreshYouTubeStatusBatchView.as_view(),
        name="youtube-lesson-refresh-status-batch",
    ),

    # =========================
    # ANALYTICS (ADMIN)
    # =========================
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("analytics/courses/", CoursesAnalyticsView.as_view(), name="analytics-courses"),
    path(
        "analytics/courses/<int:course_id>/",
        CourseDetailAnalyticsView.as_view(),
        name="analytics-course-detail",
    ),
    path("analytics/lessons/top/", TopLessonsAnalyticsView.as_view(), name="analytics-top-lessons"),
]
