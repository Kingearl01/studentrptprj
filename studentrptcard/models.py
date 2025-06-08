from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.


# --- School Information ---
class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True) # Optional school logo

    class Meta:
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return self.name

# --- Academic Year and Term ---
class AcademicYear(models.Model):
    year = models.CharField(max_length=9, unique=True, help_text="e.g., 2023/2024")
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Academic Year'
        verbose_name_plural = 'Academic Years'
        ordering = ['-year']

    def __str__(self):
        return self.year

class Term(models.Model):
    TERM_CHOICES = [
        ('Term 1', 'Term 1'),
        ('Term 2', 'Term 2'),
        ('Term 3', 'Term 3'),
    ]
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=10, choices=TERM_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    vacation_date = models.DateField(blank=True, null=True)
    reopening_date = models.DateField(blank=True, null=True)
    is_current = models.BooleanField(default=False) # To easily identify the current term

    class Meta:
        verbose_name = 'Term'
        verbose_name_plural = 'Terms'
        unique_together = ('academic_year', 'name')
        ordering = ['academic_year', 'name']

    def __str__(self):
        return f"{self.academic_year.year} - {self.name}"

# --- Grade Levels and Subjects ---
class GradeLevel(models.Model):
    LEVEL_CHOICES = [
        ('KG 1A', 'KG 1A'),
        ('KG 1B', 'KG 1B'), # Added KG1 and KG2
        ('KG 2A', 'KG 2A'),
        ('KG 2B', 'KG 2B'),
        ('Grade 1A', 'Grade 1A'), # Added Grade 1A and Grade 1B
        ('Grade 1B', 'Grade 1B'),
        ('Grade 2A', 'Grade 2A'),
        ('Grade 2B', 'Grade 2B'),
        ('Grade 3A', 'Grade 3A'),
        ('Grade 3B', 'Grade 3B'),
        ('Grade 4A', 'Grade 4A'),
        ('Grade 4A', 'Grade 4A'),
        ('Grade 5A', 'Grade 5A'),
        ('Grade 5B', 'Grade 5B'),
        ('Grade 6', 'Grade 6'),
        ('JHS 1', 'JHS 1'),
        ('JHS 2', 'JHS 2'),
        ('JHS 3', 'JHS 3'),
    ]
    name = models.CharField(max_length=50, unique=True, choices=LEVEL_CHOICES)
    # Potentially add a numerical order for sorting if needed
    order = models.IntegerField(unique=True, default=0)

    class Meta:
        verbose_name = 'Grade Level'
        verbose_name_plural = 'Grade Levels'
        ordering = ['order']

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=100)
    grade_levels = models.ManyToManyField(GradeLevel, related_name='subjects',
                                        help_text="Select grade levels this subject is taught in.")

    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        unique_together = ('name',) # A subject name should be unique overall
        ordering = ['name']

    def __str__(self):
        return self.name

# --- Student Information ---
class Student(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    student_id = models.CharField(max_length=50, unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.PROTECT, related_name='students')
    student_image = models.ImageField(upload_to='student_images/', blank=True, null=True)
    current_academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name='enrolled_students', null=True, blank=True) # To track current enrollment

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['grade_level', 'last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

# --- Teacher Information ---
# We'll link Django's built-in User model to this Teacher profile
from django.contrib.auth.models import User

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    phone_number = models.CharField(max_length=20, blank=True)
    # Digital signature (e.g., uploaded image or just a text field for name on report)
    signature_image = models.ImageField(upload_to='teacher_signatures/', blank=True, null=True)

    # For Class Teachers
    class_teacher_of = models.ForeignKey(GradeLevel, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='class_teachers_assigned',
                                         help_text="If this teacher is a class teacher for a specific grade level.")

    # For Subject Teachers
    subjects_taught = models.ManyToManyField(Subject, blank=True, related_name='teachers_assigned',
                                            help_text="Subjects this teacher teaches.")

    class Meta:
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return self.user.get_full_name() or self.user.username

# --- Scores ---
class Score(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='scores')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='scores')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='scores')

    class_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Score out of 50%"
    )
    exam_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Score out of 50%"
    )

    class Meta:
        verbose_name = 'Score'
        verbose_name_plural = 'Scores'
        unique_together = ('student', 'subject', 'term', 'academic_year') # A student can only have one score per subject per term per academic year
        ordering = ['student', 'subject', 'term']

    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} - {self.term.name}"

    @property
    def total_score(self):
        return self.class_score + self.exam_score

    @property
    def grade(self):
        # Example grading scale (you can customize this)
        score = self.total_score
        if score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'

    @property
    def remarks(self):
        # Example remarks based on grade (you can customize this)
        grade = self.grade
        if grade == 'A':
            return 'Excellent'
        elif grade == 'B':
            return 'Very Good'
        elif grade == 'C':
            return 'Good'
        elif grade == 'D':
            return 'Pass'
        else:
            return 'Fail'

# --- Report Card Remarks (for qualitative aspects) ---
class ReportCardRemarks(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_card_remarks')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='report_card_remarks')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='report_card_remarks')

    attendance_days_present = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    attendance_days_absent = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    talent_and_interest = models.TextField(blank=True)
    class_teacher_remarks = models.TextField(blank=True)
    headteacher_remarks = models.TextField(blank=True)

    class_teacher_signature = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='class_teacher_signed_remarks')
    headteacher_signature = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='headteacher_signed_remarks')


    class Meta:
        verbose_name = 'Report Card Remark'
        verbose_name_plural = 'Report Card Remarks'
        unique_together = ('student', 'term', 'academic_year')

    def __str__(self):
        return f"Remarks for {self.student.full_name} - {self.term.name} ({self.academic_year.year})"
