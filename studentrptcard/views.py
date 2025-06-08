

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import View, ListView, DetailView
from django.db.models import Avg, F, Q
from django.http import HttpResponse
from django.template.loader import render_to_string
import csv
import io
import decimal # For precise decimal calculations

# Import models and forms
from .models import (
    School, AcademicYear, Term, GradeLevel, Subject, Student, Teacher, Score, ReportCardRemarks
)
from .forms import ScoreForm, BulkScoreUploadForm, ReportCardRemarksForm, ScoreFormSet
from django.contrib.auth.forms import AuthenticationForm # For login form

# --- PDF Generation Library ---
# You'll need to install WeasyPrint:
# pip install WeasyPrint
# Note: WeasyPrint has external dependencies (cairo, pango, gdk-pixbuf).
# On Ubuntu/Debian: sudo apt-get install python3-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libpango1.0-0 libgdk-pixbuf2.0-0 libcairo2
# On macOS: brew install cairo pango gdk-pixbuf libxml2 libxslt
# On Windows: Refer to WeasyPrint documentation for installation guide.
# from weasyprint import HTML, CSS



# --- Helper Functions for Permissions and Roles ---

def is_administrator(user):
    return user.is_superuser or user.groups.filter(name='Administrators').exists()

def is_class_teacher(user):
    return user.groups.filter(name='Class Teachers').exists() and hasattr(user, 'teacher_profile') and user.teacher_profile.class_teacher_of is not None

def is_subject_teacher(user):
    return user.groups.filter(name='Subject Teachers').exists() and hasattr(user, 'teacher_profile') and user.teacher_profile.subjects_taught.exists()

# --- Authentication Views ---

class UserLoginView(View):
    template_name = 'registration/login.html'

    def get(self, request):
        form = AuthenticationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome, {user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
        return render(request, self.template_name, {'form': form})

@login_required
def user_logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

# --- Dashboard View ---

@login_required
def dashboard_view(request):
    context = {}
    user = request.user

    if is_administrator(user):
        context['role'] = 'Administrator'
        context['total_students'] = Student.objects.count()
        context['total_teachers'] = Teacher.objects.count()
        context['total_grade_levels'] = GradeLevel.objects.count()
        context['current_academic_year'] = AcademicYear.objects.filter(is_current=True).first()
        context['current_term'] = Term.objects.filter(is_current=True).first()
        # Add more admin-specific stats
    elif is_class_teacher(user):
        context['role'] = 'Class Teacher'
        teacher_profile = user.teacher_profile
        context['class_taught'] = teacher_profile.class_teacher_of
        if context['class_taught']:
            context['students_in_class'] = Student.objects.filter(grade_level=context['class_taught']).count()
        # Add more class teacher-specific stats
    elif is_subject_teacher(user):
        context['role'] = 'Subject Teacher'
        teacher_profile = user.teacher_profile
        context['subjects_taught'] = teacher_profile.subjects_taught.all()
        # Add more subject teacher-specific stats
    else:
        context['role'] = 'General User' # Or handle as unauthorized
        messages.warning(request, "Your account does not have an assigned role. Please contact an administrator.")
        return redirect('login') # Or a dedicated unauthorized page

    return render(request, 'dashboard.html', context)

# --- Score Management Views ---

@login_required
@permission_required('report_card_app.add_score', raise_exception=True)
def score_entry_view(request):
    user = request.user
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    if not current_academic_year or not current_term:
        messages.error(request, "Current academic year or term not set. Please contact an administrator.")
        return redirect('dashboard')

    students_queryset = Student.objects.all()
    subjects_queryset = Subject.objects.all()

    if is_class_teacher(user):
        class_teacher_grade_level = user.teacher_profile.class_teacher_of
        if not class_teacher_grade_level:
            messages.error(request, "You are not assigned as a class teacher to any grade level.")
            return redirect('dashboard')
        students_queryset = students_queryset.filter(grade_level=class_teacher_grade_level)
        subjects_queryset = subjects_queryset.filter(grade_levels=class_teacher_grade_level)
        template_name = 'score_entry_class_teacher.html'
        # Handle inline formset for class teachers
        if request.method == 'POST':
            # Get the student ID from the form submission to create a base instance for the formset
            # This approach is for a single student's scores. For bulk class entry, see class_score_entry_bulk
            student_id = request.POST.get('student')
            student_instance = get_object_or_404(Student, id=student_id)
            form = ScoreForm(request.POST) # Individual score form
            if form.is_valid():
                score = form.save(commit=False)
                score.academic_year = current_academic_year
                score.term = current_term
                score.save()
                messages.success(request, "Score added/updated successfully!")
                return redirect('score_entry')
            else:
                messages.error(request, "Error saving score. Please check the form.")
        else:
            form = ScoreForm(initial={'academic_year': current_academic_year, 'term': current_term})
            # Filter student and subject choices for the form
            form.fields['student'].queryset = students_queryset
            form.fields['subject'].queryset = subjects_queryset

        context = {
            'form': form,
            'students': students_queryset,
            'subjects': subjects_queryset,
            'current_academic_year': current_academic_year,
            'current_term': current_term,
            'grade_level': class_teacher_grade_level,
        }
        return render(request, template_name, context)

    elif is_subject_teacher(user):
        subject_teacher_subjects = user.teacher_profile.subjects_taught.all()
        if not subject_teacher_subjects.exists():
            messages.error(request, "You are not assigned to teach any subjects.")
            return redirect('dashboard')
        subjects_queryset = subject_teacher_subjects
        template_name = 'score_entry_subject_teacher.html'

        if request.method == 'POST':
            form = ScoreForm(request.POST)
            if form.is_valid():
                score = form.save(commit=False)
                # Ensure the subject being submitted is one the teacher actually teaches
                if score.subject not in subject_teacher_subjects:
                    messages.error(request, "You are not authorized to add scores for this subject.")
                    return redirect('score_entry')
                score.academic_year = current_academic_year
                score.term = current_term
                score.save()
                messages.success(f"Score for {score.student.full_name} in {score.subject.name} added/updated successfully!")
                return redirect('score_entry')
            else:
                messages.error(request, "Error saving score. Please check the form.")
        else:
            form = ScoreForm(initial={'academic_year': current_academic_year, 'term': current_term})
            # Filter subject choices for the form
            form.fields['subject'].queryset = subjects_queryset
            # Allow subject teachers to select any student, but the form will be submitted for a specific subject
            # You might want to further filter students by grade_level if a subject teacher only teaches certain grades
            form.fields['student'].queryset = Student.objects.filter(grade_level__in=subject_teacher_subjects.values_list('grade_levels', flat=True).distinct())

        context = {
            'form': form,
            'students': students_queryset, # All students for selection, but subject will be filtered
            'subjects': subjects_queryset,
            'current_academic_year': current_academic_year,
            'current_term': current_term,
        }
        return render(request, template_name, context)

    elif is_administrator(user):
        template_name = 'score_entry_admin.html'
        if request.method == 'POST':
            form = ScoreForm(request.POST)
            if form.is_valid():
                score = form.save(commit=False)
                score.academic_year = current_academic_year
                score.term = current_term
                score.save()
                messages.success(request, "Score added/updated successfully!")
                return redirect('score_entry')
            else:
                messages.error(request, "Error saving score. Please check the form.")
        else:
            form = ScoreForm(initial={'academic_year': current_academic_year, 'term': current_term})

        context = {
            'form': form,
            'students': students_queryset,
            'subjects': subjects_queryset,
            'current_academic_year': current_academic_year,
            'current_term': current_term,
        }
        return render(request, template_name, context)
    else:
        messages.warning(request, "You do not have permission to access this page.")
        return redirect('dashboard')


@login_required
@permission_required('report_card_app.add_score', raise_exception=True)
@permission_required('report_card_app.change_score', raise_exception=True)
def class_score_entry_bulk(request, grade_level_id):
    user = request.user
    grade_level = get_object_or_404(GradeLevel, id=grade_level_id)
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    if not current_academic_year or not current_term:
        messages.error(request, "Current academic year or term not set. Please contact an administrator.")
        return redirect('dashboard')

    # Permission check: Only class teachers of this grade or administrators
    if not (is_administrator(user) or (is_class_teacher(user) and user.teacher_profile.class_teacher_of == grade_level)):
        messages.warning(request, "You do not have permission to access this page.")
        return redirect('dashboard')

    students_in_class = Student.objects.filter(grade_level=grade_level, current_academic_year=current_academic_year).order_by('last_name', 'first_name')
    subjects_for_grade = Subject.objects.filter(grade_levels=grade_level).order_by('name')

    # Prepare initial data for formset
    initial_data = []
    for student in students_in_class:
        for subject in subjects_for_grade:
            score, created = Score.objects.get_or_create(
                student=student,
                subject=subject,
                term=current_term,
                academic_year=current_academic_year,
                defaults={'class_score': 0, 'exam_score': 0} # Default scores if not exist
            )
            initial_data.append({
                'id': score.id, # Include ID for existing scores
                'student': student.id,
                'subject': subject.id,
                'class_score': score.class_score,
                'exam_score': score.exam_score,
                'term': current_term.id,
                'academic_year': current_academic_year.id,
            })

    # Create a formset for each student-subject combination
    # We need to create a formset for each student, or a custom formset that handles multiple students/subjects
    # For simplicity, we'll create a list of forms that are pre-populated.
    # A more robust solution for inline editing of many scores would involve a custom management form.

    ScoreEntryForm = forms.modelform_factory(
        Score,
        fields=['class_score', 'exam_score'],
        widgets={
            'class_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0, 'max': 50}),
            'exam_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0, 'max': 50}),
        }
    )

    forms_data = []
    if request.method == 'POST':
        for student in students_in_class:
            for subject in subjects_for_grade:
                score_instance = Score.objects.get(
                    student=student,
                    subject=subject,
                    term=current_term,
                    academic_year=current_academic_year
                )
                prefix = f'score_{student.id}_{subject.id}'
                form = ScoreEntryForm(request.POST, instance=score_instance, prefix=prefix)
                if form.is_valid():
                    form.save()
                forms_data.append({'student': student, 'subject': subject, 'form': form})
        messages.success(request, "Scores updated successfully!")
        return redirect('class_score_entry_bulk', grade_level_id=grade_level.id)
    else:
        for student in students_in_class:
            for subject in subjects_for_grade:
                score_instance, created = Score.objects.get_or_create(
                    student=student,
                    subject=subject,
                    term=current_term,
                    academic_year=current_academic_year,
                    defaults={'class_score': 0, 'exam_score': 0}
                )
                prefix = f'score_{student.id}_{subject.id}'
                form = ScoreEntryForm(instance=score_instance, prefix=prefix)
                forms_data.append({'student': student, 'subject': subject, 'form': form, 'score_id': score_instance.id})

    context = {
        'grade_level': grade_level,
        'students_in_class': students_in_class,
        'subjects_for_grade': subjects_for_grade,
        'forms_data': forms_data,
        'current_academic_year': current_academic_year,
        'current_term': current_term,
    }
    return render(request, 'class_score_entry_bulk.html', context)


@login_required
@permission_required('report_card_app.add_reportcardremarks', raise_exception=True)
@permission_required('report_card_app.change_reportcardremarks', raise_exception=True)
def add_edit_report_card_remarks(request, student_id):
    user = request.user
    student = get_object_or_404(Student, id=student_id)
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    if not current_academic_year or not current_term:
        messages.error(request, "Current academic year or term not set. Please contact an administrator.")
        return redirect('dashboard')

    # Permission check: Only class teachers of this student's grade or administrators
    if not (is_administrator(user) or (is_class_teacher(user) and user.teacher_profile.class_teacher_of == student.grade_level)):
        messages.warning(request, "You do not have permission to add/edit remarks for this student.")
        return redirect('dashboard')

    remarks_instance, created = ReportCardRemarks.objects.get_or_create(
        student=student,
        term=current_term,
        academic_year=current_academic_year,
        defaults={}
    )

    if request.method == 'POST':
        form = ReportCardRemarksForm(request.POST, instance=remarks_instance)
        if form.is_valid():
            remarks = form.save(commit=False)
            # Automatically assign class teacher signature if the user is a class teacher
            if is_class_teacher(user):
                remarks.class_teacher_signature = user.teacher_profile
            # Admins can also set headteacher signature
            if is_administrator(user):
                # An admin might be the headteacher or can select one.
                # For simplicity, we'll let admin set headteacher remarks,
                # but a more complex system might have a separate field for headteacher selection.
                # For now, if admin is a teacher, their signature can be used.
                if hasattr(user, 'teacher_profile'):
                    remarks.headteacher_signature = user.teacher_profile

            remarks.save()
            messages.success(request, f"Remarks for {student.full_name} updated successfully!")
            return redirect('student_detail', student_id=student.id) # Redirect to student detail page
        else:
            messages.error(request, "Error saving remarks. Please check the form.")
    else:
        form = ReportCardRemarksForm(instance=remarks_instance)

    context = {
        'form': form,
        'student': student,
        'current_academic_year': current_academic_year,
        'current_term': current_term,
        'is_administrator': is_administrator(user),
        'is_class_teacher': is_class_teacher(user),
    }
    return render(request, 'report_card_remarks_form.html', context)


# --- Bulk Upload View ---

@login_required
@permission_required('report_card_app.add_score', raise_exception=True)
def bulk_score_upload_view(request):
    user = request.user
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    if not current_academic_year or not current_term:
        messages.error(request, "Current academic year or term not set. Please contact an administrator.")
        return redirect('dashboard')

    # Only allow administrators or subject teachers to bulk upload
    if not (is_administrator(user) or is_subject_teacher(user)):
        messages.warning(request, "You do not have permission to perform bulk score upload.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = BulkScoreUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            selected_academic_year = form.cleaned_data['academic_year']
            selected_term = form.cleaned_data['term']

            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file.')
                return redirect('bulk_score_upload')

            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            next(io_string) # Skip header row

            updated_count = 0
            created_count = 0
            errors = []

            for row in csv.reader(io_string, delimiter=','):
                if not row: # Skip empty rows
                    continue
                try:
                    student_id = row[0].strip()
                    subject_name = row[1].strip()
                    class_score = decimal.Decimal(row[2].strip())
                    exam_score = decimal.Decimal(row[3].strip())

                    student = Student.objects.get(student_id=student_id)
                    subject = Subject.objects.get(name__iexact=subject_name) # Case-insensitive subject name

                    # Permission check for subject teacher
                    if is_subject_teacher(user) and subject not in user.teacher_profile.subjects_taught.all():
                        errors.append(f"Skipped: Subject teacher '{user.username}' is not authorized to upload scores for subject '{subject_name}'.")
                        continue

                    score, created = Score.objects.update_or_create(
                        student=student,
                        subject=subject,
                        term=selected_term,
                        academic_year=selected_academic_year,
                        defaults={
                            'class_score': class_score,
                            'exam_score': exam_score
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Student.DoesNotExist:
                    errors.append(f"Student with ID '{student_id}' not found.")
                except Subject.DoesNotExist:
                    errors.append(f"Subject '{subject_name}' not found.")
                except (ValueError, IndexError, decimal.InvalidOperation) as e:
                    errors.append(f"Error processing row '{row}': {e}")
                except Exception as e:
                    errors.append(f"An unexpected error occurred for row '{row}': {e}")

            if errors:
                for error in errors:
                    messages.error(request, error)
            messages.success(request, f"Bulk upload complete. Created: {created_count}, Updated: {updated_count}.")
            return redirect('bulk_score_upload')
        else:
            messages.error(request, "Error in form submission. Please correct the errors.")
    else:
        form = BulkScoreUploadForm(initial={'academic_year': current_academic_year, 'term': current_term})

    context = {
        'form': form,
        'current_academic_year': current_academic_year,
        'current_term': current_term,
    }
    return render(request, 'bulk_score_upload.html', context)


# --- Report Card Generation Logic ---

def calculate_subject_positions(scores_queryset):
    """Calculates position for each student within each subject based on total_score."""
    subject_positions = {} # { (student_id, subject_id): position }
    # Group scores by subject and grade level to calculate positions within each subject
    for subject_id in scores_queryset.values_list('subject', flat=True).distinct():
        subject_scores = scores_queryset.filter(subject__id=subject_id).order_by('-class_score', '-exam_score') # Order by total score implicitly
        ranked_scores = sorted(subject_scores, key=lambda x: x.total_score, reverse=True)

        current_rank = 1
        for i, score_obj in enumerate(ranked_scores):
            if i > 0 and score_obj.total_score < ranked_scores[i-1].total_score:
                current_rank = i + 1
            subject_positions[(score_obj.student.id, score_obj.subject.id)] = current_rank
    return subject_positions

def calculate_class_positions(students_in_class, academic_year, term):
    """Calculates overall class position based on average total score across all subjects."""
    student_averages = {} # { student_id: average_score }
    for student in students_in_class:
        student_scores = Score.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        )
        if student_scores.exists():
            total_scores_sum = sum(s.total_score for s in student_scores)
            average_score = total_scores_sum / student_scores.count()
            student_averages[student.id] = average_score
        else:
            student_averages[student.id] = 0 # Handle students with no scores

    # Sort students by average score to determine rank
    sorted_students_by_avg = sorted(
        student_averages.items(),
        key=lambda item: item[1], # Sort by average score
        reverse=True
    )

    class_positions = {} # { student_id: position }
    current_rank = 1
    for i, (student_id, avg_score) in enumerate(sorted_students_by_avg):
        if i > 0 and avg_score < sorted_students_by_avg[i-1][1]:
            current_rank = i + 1
        class_positions[student_id] = current_rank
    return class_positions


@login_required
def generate_individual_report_card(request, student_id, academic_year_id, term_id):
    user = request.user
    student = get_object_or_404(Student, id=student_id)
    academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
    term = get_object_or_404(Term, id=term_id)

    # Permission check: Admin, Class Teacher for student's grade, or Subject Teacher for student's subjects
    if not (is_administrator(user) or
            (is_class_teacher(user) and user.teacher_profile.class_teacher_of == student.grade_level) or
            (is_subject_teacher(user) and student.scores.filter(term=term, academic_year=academic_year, subject__in=user.teacher_profile.subjects_taught.all()).exists())):
        messages.warning(request, "You do not have permission to generate this report card.")
        return redirect('dashboard')

    school_info = School.objects.first() # Assuming one school for simplicity
    if not school_info:
        messages.error(request, "School information not found. Please add school details in the admin panel.")
        return redirect('dashboard')

    # Get all scores for the student in the given term and academic year
    student_scores = Score.objects.filter(
        student=student,
        academic_year=academic_year,
        term=term
    ).select_related('subject').order_by('subject__name')

    # Get remarks for the student in the given term and academic year
    remarks = ReportCardRemarks.objects.filter(
        student=student,
        academic_year=academic_year,
        term=term
    ).first()

    # Calculate overall average score
    total_scores_sum = sum(s.total_score for s in student_scores)
    learners_average_score = total_scores_sum / student_scores.count() if student_scores.count() > 0 else 0

    # Calculate class position
    students_in_class = Student.objects.filter(grade_level=student.grade_level, current_academic_year=academic_year)
    class_positions = calculate_class_positions(students_in_class, academic_year, term)
    position_in_class = class_positions.get(student.id, 'N/A')

    # Calculate subject positions (for display on report card)
    # This requires looking at all students in the same grade for each subject
    all_scores_in_grade_term = Score.objects.filter(
        academic_year=academic_year,
        term=term,
        student__grade_level=student.grade_level
    )
    subject_positions = calculate_subject_positions(all_scores_in_grade_term)

    # Add subject position to each score object for rendering
    for score_obj in student_scores:
        score_obj.subject_position = subject_positions.get((score_obj.student.id, score_obj.subject.id), 'N/A')

    class_teacher = Teacher.objects.filter(class_teacher_of=student.grade_level).first()
    # Assuming Headteacher is an administrator with a Teacher profile or a specific Teacher instance
    headteacher = Teacher.objects.filter(user__is_superuser=True).first() # Or a specific user/group for headteacher

    context = {
        'school': school_info,
        'student': student,
        'academic_year': academic_year,
        'term': term,
        'student_scores': student_scores,
        'learners_average_score': f"{learners_average_score:.2f}",
        'position_in_class': position_in_class,
        'remarks': remarks,
        'class_teacher': class_teacher,
        'headteacher': headteacher,
        'date_of_vacation': term.vacation_date,
        'date_of_reopening': term.reopening_date,
        # Add more context variables as needed based on your report card design
    }

    # Render HTML to string
    html_string = render_to_string('report_card_individual.html', context)

    # Generate PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_card_{student.student_id}_{academic_year.year}_{term.name}.pdf"'
    # HTML(string=html_string).write_pdf(response)
    return response


@login_required
def generate_class_report_card(request, grade_level_id, academic_year_id, term_id):
    user = request.user
    grade_level = get_object_or_404(GradeLevel, id=grade_level_id)
    academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
    term = get_object_or_404(Term, id=term_id)

    # Permission check: Only class teachers of this grade or administrators
    if not (is_administrator(user) or (is_class_teacher(user) and user.teacher_profile.class_teacher_of == grade_level)):
        messages.warning(request, "You do not have permission to generate class report cards for this grade.")
        return redirect('dashboard')

    school_info = School.objects.first()
    if not school_info:
        messages.error(request, "School information not found. Please add school details in the admin panel.")
        return redirect('dashboard')

    students_in_class = Student.objects.filter(
        grade_level=grade_level,
        current_academic_year=academic_year
    ).order_by('last_name', 'first_name')

    all_scores_in_grade_term = Score.objects.filter(
        academic_year=academic_year,
        term=term,
        student__grade_level=grade_level
    ).select_related('student', 'subject')

    class_positions = calculate_class_positions(students_in_class, academic_year, term)
    subject_positions = calculate_subject_positions(all_scores_in_grade_term)

    report_cards_data = []
    for student in students_in_class:
        student_scores = [s for s in all_scores_in_grade_term if s.student == student]
        for score_obj in student_scores:
            score_obj.subject_position = subject_positions.get((score_obj.student.id, score_obj.subject.id), 'N/A')

        total_scores_sum = sum(s.total_score for s in student_scores)
        learners_average_score = total_scores_sum / len(student_scores) if len(student_scores) > 0 else 0

        remarks = ReportCardRemarks.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()

        report_cards_data.append({
            'student': student,
            'student_scores': student_scores,
            'learners_average_score': f"{learners_average_score:.2f}",
            'position_in_class': class_positions.get(student.id, 'N/A'),
            'remarks': remarks,
        })

    class_teacher = Teacher.objects.filter(class_teacher_of=grade_level).first()
    headteacher = Teacher.objects.filter(user__is_superuser=True).first() # Or specific headteacher

    context = {
        'school': school_info,
        'grade_level': grade_level,
        'academic_year': academic_year,
        'term': term,
        'report_cards_data': report_cards_data,
        'class_teacher': class_teacher,
        'headteacher': headteacher,
        'date_of_vacation': term.vacation_date,
        'date_of_reopening': term.reopening_date,
    }

    html_string = render_to_string('report_card_class.html', context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="class_report_cards_{grade_level.name}_{academic_year.year}_{term.name}.pdf"'
    # HTML(string=html_string).write_pdf(response)
    return response


# --- Student and Teacher Listing Views (for navigation) ---

@login_required
def student_list_view(request):
    user = request.user
    students = Student.objects.select_related('grade_level', 'current_academic_year').all()

    if is_class_teacher(user):
        class_teacher_grade_level = user.teacher_profile.class_teacher_of
        if class_teacher_grade_level:
            students = students.filter(grade_level=class_teacher_grade_level)
        else:
            students = Student.objects.none() # No students if not assigned
            messages.warning(request, "You are not assigned as a class teacher to any grade level.")

    # Subject teachers can view all students, but their editing is restricted by score_entry_view
    # Administrators can view all students

    context = {
        'students': students,
        'is_admin': is_administrator(user),
        'is_class_teacher': is_class_teacher(user),
    }
    return render(request, 'student_list.html', context)

@login_required
def student_detail_view(request, student_id):
    user = request.user
    student = get_object_or_404(Student, id=student_id)
    current_academic_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    # Permission check: Admin, Class Teacher for student's grade, or Subject Teacher for student's subjects
    if not (is_administrator(user) or
            (is_class_teacher(user) and user.teacher_profile.class_teacher_of == student.grade_level) or
            (is_subject_teacher(user) and student.scores.filter(subject__in=user.teacher_profile.subjects_taught.all()).exists())):
        messages.warning(request, "You do not have permission to view this student's details.")
        return redirect('dashboard')


    scores = Score.objects.filter(
        student=student,
        academic_year=current_academic_year,
        term=current_term
    ).select_related('subject').order_by('subject__name')

    remarks = ReportCardRemarks.objects.filter(
        student=student,
        academic_year=current_academic_year,
        term=current_term
    ).first()

    context = {
        'student': student,
        'scores': scores,
        'remarks': remarks,
        'current_academic_year': current_academic_year,
        'current_term': current_term,
        'is_admin': is_administrator(user),
        'is_class_teacher': is_class_teacher(user),
        'is_subject_teacher': is_subject_teacher(user),
    }
    return render(request, 'student_detail.html', context)

@login_required
def grade_level_list_view(request):
    user = request.user
    grade_levels = GradeLevel.objects.all().order_by('order')

    if is_class_teacher(user):
        # Class teachers only see their assigned grade level
        class_teacher_grade_level = user.teacher_profile.class_teacher_of
        if class_teacher_grade_level:
            grade_levels = GradeLevel.objects.filter(id=class_teacher_grade_level.id)
        else:
            grade_levels = GradeLevel.objects.none()
            messages.warning(request, "You are not assigned as a class teacher to any grade level.")

    # Subject teachers and admins see all grade levels
    context = {
        'grade_levels': grade_levels,
        'is_admin': is_administrator(user),
        'is_class_teacher': is_class_teacher(user),
    }
    return render(request, 'grade_level_list.html', context)