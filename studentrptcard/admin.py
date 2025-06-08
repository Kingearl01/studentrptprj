from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    School, AcademicYear, Term, GradeLevel, Subject, Student, Teacher, Score, ReportCardRemarks
)

# Register your models here.
# Inline for Teacher to User
class TeacherInline(admin.StackedInline):
    model = Teacher
    can_delete = False
    verbose_name_plural = 'teacher profile'

# Extend User admin to include Teacher profile
class UserAdmin(BaseUserAdmin):
    inlines = (TeacherInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_teacher_profile_exists')

    def is_teacher_profile_exists(self, obj):
        return hasattr(obj, 'teacher_profile')
    is_teacher_profile_exists.boolean = True
    is_teacher_profile_exists.short_description = 'Has Teacher Profile'

# Re-register User model
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    search_fields = ('name',)

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'is_current')
    list_editable = ('is_current',) # Allow direct editing of current status
    search_fields = ('year',)

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'name', 'start_date', 'end_date', 'is_current', 'vacation_date', 'reopening_date')
    list_filter = ('academic_year', 'name', 'is_current')
    list_editable = ('is_current',)
    search_fields = ('academic_year__year', 'name')
    raw_id_fields = ('academic_year',)

@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',)
    search_fields = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('grade_levels',) # For easier ManyToMany selection
    search_fields = ('name',)
    list_filter = ('grade_levels',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'student_id', 'grade_level', 'gender', 'current_academic_year')
    list_filter = ('grade_level', 'gender', 'current_academic_year')
    search_fields = ('first_name', 'last_name', 'student_id')
    raw_id_fields = ('grade_level', 'current_academic_year')
    fieldsets = (
        (None, {
            'fields': ('first_name', 'last_name', 'student_id', 'gender', 'grade_level', 'current_academic_year', 'student_image')
        }),
    )

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user_full_name', 'phone_number', 'class_teacher_of')
    list_filter = ('class_teacher_of', 'subjects_taught')
    search_fields = ('user__first_name', 'user__last_name', 'user__username')
    raw_id_fields = ('user', 'class_teacher_of')
    filter_horizontal = ('subjects_taught',)

    def user_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_full_name.short_description = 'Teacher Name'

@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'term', 'academic_year', 'class_score', 'exam_score', 'total_score', 'grade', 'remarks')
    list_filter = ('academic_year', 'term', 'subject', 'student__grade_level')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id', 'subject__name')
    raw_id_fields = ('student', 'subject', 'term', 'academic_year') # Use raw_id_fields for FKs to improve performance with many records

@admin.register(ReportCardRemarks)
class ReportCardRemarksAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'academic_year', 'attendance_days_present', 'attendance_days_absent', 'class_teacher_signature', 'headteacher_signature')
    list_filter = ('academic_year', 'term', 'student__grade_level')
    search_fields = ('student__first_name', 'student__last_name', 'class_teacher_remarks', 'headteacher_remarks')
    raw_id_fields = ('student', 'term', 'academic_year', 'class_teacher_signature', 'headteacher_signature')