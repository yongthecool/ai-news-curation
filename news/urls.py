from django.urls import path
from . import views

app_name = "news"

urlpatterns = [
    path("", views.index, name="index"),
    path("save/", views.save_summary, name="save_summary"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/delete/", views.delete_summary, name="delete_summary"),
]
