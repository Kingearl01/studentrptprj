from django.urls import path
from .views import (
    UserLoginView, user_logout_view, dashboard_view, score_entry_view,
    class_score_entry_bulk, bulk_score_upload_view, add_edit_report_card_remarks,
    generate_class_report_card, generate_individual_report_card,
    student_detail_view, student_list_view, grade_level_list_view,
)


urlpatterns = [
    # Authentication
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', user_logout_view, name='logout'),

    # Dashboard
    path('', dashboard_view, name='dashboard'),

    # Score Management
    path('scores/entry/', score_entry_view, name='score_entry'),
    path('scores/class-bulk/<int:grade_level_id>/', class_score_entry_bulk, name='class_score_entry_bulk'),
    # path('scores/bulk-upload/', bulk_score_upload_view, name='bulk_score_upload'),

    # Report Card Remarks
    # path('remarks/edit/<int:student_id>/', add_edit_report_card_remarks, name='add_edit_report_card_remarks'),

    # Report Card Generation
    # path('report-card/individual/<int:student_id>/<int:academic_year_id>/<int:term_id>/',
    #      generate_individual_report_card, name='generate_individual_report_card'),
    # path('report-card/class/<int:grade_level_id>/<int:academic_year_id>/<int:term_id>/',
    #      generate_class_report_card, name='generate_class_report_card'),

    # Student and Grade Level Listings
    # path('students/', student_list_view, name='student_list'),
    # path('students/<int:student_id>/', student_detail_view, name='student_detail'),
    # path('grade-levels/', grade_level_list_view, name='grade_level_list'),
]
