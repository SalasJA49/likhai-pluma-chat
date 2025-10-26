from django.db import models

class Style(models.Model):
    name = models.CharField(max_length=120, unique=True)
    style = models.TextField(blank=True, default="")
    example = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

class Output(models.Model):
    style_name = models.CharField(max_length=120)
    input_text = models.TextField()
    output_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class ChatThread(models.Model):
    title = models.CharField(max_length=200, blank=True, default="")
    user_id = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)  # "system" | "user" | "assistant"
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
