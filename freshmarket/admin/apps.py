from django.apps import AppConfig


class AdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin'
    label = 'admin_panel'  # 避免与 django.contrib.admin 的标签冲突
    verbose_name = '管理端'
