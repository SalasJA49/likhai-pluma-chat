from django.urls import path
from .views import (
    StylesAPI, StyleDetailAPI, ExtractStyleAPI, RewriteAPI, OutputsAPI,
    OutputDownloadAPI,
    ChatStartAPI, ChatMessageAPI, ChatHistoryAPI, ChatStreamAPI,
    ChatUploadAPI, ChatUploadFoundryAPI,
    LocalsAPI,
    ChatModelsAPI, ChatThreadsAPI, ChatRenameAPI, ResearchStreamAPI, ReasoningStreamAPI   # <-- add
)
from .analytics.eda import EDAProcessAPI

urlpatterns = [
    path("styles/", StylesAPI.as_view()),
    path("styles/<int:style_id>/", StyleDetailAPI.as_view()),
    path("extract-style/", ExtractStyleAPI.as_view()),
    path("rewrite/", RewriteAPI.as_view()),
    path("outputs/", OutputsAPI.as_view()),
    path("outputs/<str:output_id>/download/", OutputDownloadAPI.as_view()),
    path("chat/start/", ChatStartAPI.as_view()),
    path("chat/message/", ChatMessageAPI.as_view()),
    path("chat/upload/", ChatUploadAPI.as_view()),
    path("chat/upload-foundry/", ChatUploadFoundryAPI.as_view()),
    path("locals/", LocalsAPI.as_view()),
    path("chat/history/", ChatHistoryAPI.as_view()),
    path("chat/threads/", ChatThreadsAPI.as_view()),
    path("chat/rename/", ChatRenameAPI.as_view()),
    path("chat/stream/", ChatStreamAPI.as_view()),
    path("chat/models/", ChatModelsAPI.as_view()),  # <-- add
    path("research/stream/", ResearchStreamAPI.as_view()),
    path("reasoning/stream/", ReasoningStreamAPI.as_view()),
    path("eda/process/", EDAProcessAPI.as_view()),
]
