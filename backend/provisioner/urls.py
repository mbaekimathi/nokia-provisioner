from django.urls import path

from . import views

urlpatterns = [
    path("auth/signup/", views.signup),
    path("auth/login/", views.login),
    path("employees/", views.employees),
    path("employees/<int:pk>/", views.employee_detail),
    path("routers/", views.routers),
    path("routers/<int:pk>/", views.router_detail),
    path("stats/", views.stats),
    path("scan/", views.scan),
    path("subnets/", views.subnets),
    path("auto/", views.auto),
    path("settings/", views.settings_view),
]
