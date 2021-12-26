from django.urls import path, re_path
from .views import *


app_name = 'collection'
urlpatterns = [
    path('mine/', list, name='list'),
    path('create/', create, name='create'),
    path('<int:id>/', retrieve, name='retrieve'),
    path('update/<int:id>/', update, name='update'),
    path('delete/<int:id>/', delete, name='delete'),
    path('follow/<int:id>/', follow, name='follow'),
    path('unfollow/<int:id>/', unfollow, name='unfollow'),
    path('<int:id>/append_item/', append_item, name='append_item'),
    path('<int:id>/delete_item/<int:item_id>', delete_item, name='delete_item'),
    path('<int:id>/move_up_item/<int:item_id>', move_up_item, name='move_up_item'),
    path('<int:id>/move_down_item/<int:item_id>', move_down_item, name='move_down_item'),
    path('with/<str:type>/<int:id>/', list_with, name='list_with'),
    # TODO: tag
]
