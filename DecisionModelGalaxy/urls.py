
from django.conf.urls import include, url
from django.urls import path
from DSS import views as dss_views

urlpatterns = [
    path("", dss_views.landing_page, name="landing_page"),

    url(r"^DSS/", include(("DSS.urls", "DSS"), namespace="DSS")),
]
