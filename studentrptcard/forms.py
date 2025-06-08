from django import forms
from .models import Score, ReportCardRemarks, Student, Subject, GradeLevel, AcademicYear, Term
from django.forms import inlineformset_factory

# Form for individual score entry
class ScoreForm(forms.ModelForm):
    class Meta:
        model = Score
        fields = ['student', 'subject', 'term', 'academic_year', 'class_score', 'exam_score']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'class_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
            'exam_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
        }

    def __init__(self, *args, **kwargs):
        # Optional: Filter choices for student, subject, term, academic_year
        # based on the user's role or context if needed.
        # For example, a subject teacher might only see subjects they teach.
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.Textarea)):
                field.widget.attrs['class'] = 'form-control rounded-md p-2 border border-gray-300 focus:ring-blue-500 focus:border-blue-500'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select rounded-md p-2 border border-gray-300 focus:ring-blue-500 focus:border-blue-500'
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-checkbox rounded-md'

# Form for bulk score upload (CSV)
class BulkScoreUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload CSV File",
        help_text="CSV should contain columns: student_id, subject_name, class_score, exam_score",
        widget=forms.FileInput(attrs={'class': 'form-input-file rounded-md p-2 border border-gray-300'})
    )
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        label="Academic Year",
        widget=forms.Select(attrs={'class': 'form-select rounded-md p-2 border border-gray-300'})
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all(),
        label="Term",
        widget=forms.Select(attrs={'class': 'form-select rounded-md p-2 border border-gray-300'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter terms to show only terms for the selected academic year (if applicable)
        if 'academic_year' in self.data:
            try:
                academic_year_id = int(self.data.get('academic_year'))
                self.fields['term'].queryset = Term.objects.filter(academic_year_id=academic_year_id)
            except (ValueError, TypeError):
                pass # Fallback to all terms if academic year is not valid

# Form for Report Card Remarks
class ReportCardRemarksForm(forms.ModelForm):
    class Meta:
        model = ReportCardRemarks
        fields = [
            'attendance_days_present', 'attendance_days_absent',
            'talent_and_interest', 'class_teacher_remarks', 'headteacher_remarks',
            # 'class_teacher_signature', 'headteacher_signature' # These will be set by view logic based on logged-in user
        ]
        widgets = {
            'attendance_days_present': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'attendance_days_absent': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'talent_and_interest': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'class_teacher_remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'headteacher_remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.Textarea)):
                field.widget.attrs['class'] = 'form-control rounded-md p-2 border border-gray-300 focus:ring-blue-500 focus:border-blue-500'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select rounded-md p-2 border border-gray-300 focus:ring-blue-500 focus:border-blue-500'


# Inline formset for a class teacher to update multiple scores at once for their class
# This is useful for a "Class Teacher Score Entry" view
ScoreFormSet = inlineformset_factory(
    Student, Score,
    fields=['subject', 'class_score', 'exam_score', 'term', 'academic_year'],
    extra=0, # No extra blank forms by default
    can_delete=False, # Prevent deleting scores directly from here
    widgets={
        'subject': forms.Select(attrs={'class': 'form-select'}),
        'class_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
        'exam_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
        'term': forms.HiddenInput(), # These will be set by the view context
        'academic_year': forms.HiddenInput(), # These will be set by the view context
    }
)