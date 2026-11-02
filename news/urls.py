from django.urls import path
from . import views

app_name = "news"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("save/", views.save_summary, name="save_summary"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/delete/", views.delete_summary, name="delete_summary"),
]
