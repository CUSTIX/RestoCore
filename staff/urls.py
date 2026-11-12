from django.urls import path

from staff import views

app_name = "staff"

urlpatterns = [
    path("me/", views.MyWorkView.as_view(), name="me"),
    path("me/clock/", views.ClockView.as_view(), name="clock"),
    path("me/leave/<int:pk>/cancel/", views.LeaveCancelView.as_view(), name="leave_cancel"),
    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),
    path("employees/new/", views.EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="employee_update"),
    path("shifts/", views.ShiftListView.as_view(), name="shift_list"),
    path("shifts/new/", views.ShiftEditView.as_view(), name="shift_create"),
    path("shifts/<int:pk>/edit/", views.ShiftEditView.as_view(), name="shift_update"),
    path("shifts/<int:pk>/delete/", views.ShiftDeleteView.as_view(), name="shift_delete"),
    path("attendance/", views.AttendanceListView.as_view(), name="attendance_list"),
    path(
        "attendance/<int:pk>/close/", views.AttendanceCloseView.as_view(), name="attendance_close"
    ),
    path("leave/", views.LeaveListView.as_view(), name="leave_list"),
    path("leave/<int:pk>/review/", views.LeaveReviewView.as_view(), name="leave_review"),
]
