from django.urls import path

from assistant import views

app_name = "assistant"

urlpatterns = [
    path("", views.AssistantView.as_view(), name="chat"),
]
