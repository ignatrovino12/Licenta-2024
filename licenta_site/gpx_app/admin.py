from django.contrib import admin
from gpx_app.models import Video,Upvote,Comment

admin.site.register(Video)
admin.site.register(Upvote)
admin.site.register(Comment)
admin.site.site_url = "http://localhost:5173/login"