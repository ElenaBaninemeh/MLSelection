# DSS/urls.py
from django.urls import path
from DSS import views

app_name = "DSS"

urlpatterns = [
    path('view_decision_model/', views.view_decision_model, name='view_decision_model'),  # Add this line
    path('api/evaluate', views.evaluate, name='evaluate'),  # URL pattern for the evaluate view
    path('api/load_features/', views.load_features, name='load_features'),  # load_features view within DSS namespace
  
    path('', views.mcdm_decision_models, name='mcdm_decision_models'),  # Homepage or main entry point
]