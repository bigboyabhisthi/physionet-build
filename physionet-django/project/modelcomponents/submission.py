from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

from project.quota import DemoQuotaManager


class EditLog(models.Model):
    """
    Log for an editor decision. Also saves submission info.
    """
    # Quality assurance fields for data and software
    QUALITY_ASSURANCE_FIELDS = (
        # 0: Database
        ('soundly_produced', 'well_described', 'open_format',
         'data_machine_readable', 'reusable', 'no_phi', 'pn_suitable'),
        # 1: Software
        ('soundly_produced', 'well_described', 'open_format', 'no_phi',
            'reusable', 'pn_suitable'),
        # 2: Challenge
        ('soundly_produced', 'well_described', 'open_format',
         'data_machine_readable', 'reusable', 'no_phi', 'pn_suitable'),
        # 3: Model
        ('soundly_produced', 'well_described', 'open_format',
         'data_machine_readable', 'reusable', 'no_phi', 'pn_suitable'),
    )
    # The editor's free input fields
    EDITOR_FIELDS = ('editor_comments', 'decision', 'auto_doi')

    COMMON_LABELS = {
        'reusable': 'Does the project include everything needed for reuse by the community?',
        'pn_suitable': 'Is the content suitable for PhysioNet?',
        'editor_comments': 'Comments to authors',
        'no_phi': 'Is the project free of protected health information?',
        'data_machine_readable': 'Are all files machine-readable?'
    }

    LABELS = (
        # 0: Database
        {'soundly_produced': 'Has the data been produced in a sound manner?',
         'well_described': 'Is the data adequately described?',
         'open_format': 'Is the data provided in an open format?',
         'data_machine_readable': 'Are the data files machine-readable?'},
        # 1: Software
        {'soundly_produced': 'Does the software follow best practice in development?',
         'well_described': 'Is the software adequately described?',
         'open_format': 'Is the software provided in an open format?'},
        # 2: Challenge
        {'soundly_produced': 'Has the challenge been produced in a sound manner?',
         'well_described': 'Is the challenge adequately described?',
         'open_format': 'Is all content provided in an open format?'},
        # 3: Model
        {'soundly_produced': 'Does the software follow best practice in development?',
         'well_described': 'Is the software adequately described?',
         'open_format': 'Is the software provided in an open format?'},
    )

    HINTS = {
        'no_phi': [
            'No dates in WFDB header files (or anonymized dates only)?',
            'No identifying information of any individual'
            ' (caregivers as well as patients)?',
            'No ages of individuals above 89 years?',
            'No hidden metadata (e.g. EDF headers)?',
            'No internal timestamps, date-based UUIDs or other identifiers?',
        ],
        'open_format': [
            'No compiled binaries or bytecode?',
            'No minified or obfuscated source code?',
        ],
    }

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    project = GenericForeignKey('content_type', 'object_id')

    # When the submitting author submits/resubmits
    submission_datetime = models.DateTimeField(auto_now_add=True)
    is_resubmission = models.BooleanField(default=False)
    author_comments = models.CharField(max_length=20000, default='')
    # Quality assurance fields
    soundly_produced = models.NullBooleanField(null=True)
    well_described = models.NullBooleanField(null=True)
    open_format = models.NullBooleanField(null=True)
    data_machine_readable = models.NullBooleanField(null=True)
    reusable = models.NullBooleanField(null=True)
    no_phi = models.NullBooleanField(null=True)
    pn_suitable = models.NullBooleanField(null=True)
    # Editor decision. 0 1 2 for reject/revise/accept
    decision = models.SmallIntegerField(null=True)
    decision_datetime = models.DateTimeField(null=True)
    # Comments for the decision
    editor_comments = models.CharField(max_length=20000)
    auto_doi = models.BooleanField(default=True)

    def set_quality_assurance_results(self):
        """
        Prepare the string fields for the editor's decisions of the
        quality assurance fields, to be displayed. Does nothing if the
        decision has not been made.
        """
        if not self.decision_datetime:
            return

        resource_type = self.project.resource_type

        # See also YES_NO_UNDETERMINED in console/forms.py
        RESPONSE_LABEL = {True: 'Yes', False: 'No', None: 'Undetermined'}

        # Retrieve their labels and results for our resource type
        quality_assurance_fields = self.__class__.QUALITY_ASSURANCE_FIELDS[resource_type.id]

        # Create the labels dictionary for this resource type
        labels = {**self.__class__.COMMON_LABELS, **self.__class__.LABELS[resource_type.id]}

        self.quality_assurance_results = []
        for f in quality_assurance_fields:
            qa_str = '{} {}'.format(labels[f], RESPONSE_LABEL[getattr(self, f)])
            self.quality_assurance_results.append(qa_str)


class CopyeditLog(models.Model):
    """
    Log for an editor copyedit
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    project = GenericForeignKey('content_type', 'object_id')
    # Either the time the project was accepted and moved into copyedit
    # from the edit stage, or the time it was reopened for copyedit from
    # the author approval stage.
    start_datetime = models.DateTimeField(auto_now_add=True)
    # Whether the submission was reopened for copyediting
    is_reedit = models.BooleanField(default=False)
    made_changes = models.NullBooleanField(null=True)
    changelog_summary = models.CharField(default='', max_length=10000, blank=True)
    complete_datetime = models.DateTimeField(null=True)


class SubmissionInfo(models.Model):
    """
    Submission information, inherited by all projects.

    Every project (ActiveProject, PublishedProject, and
    ArchivedProject) inherits from this class as well as Metadata.
    The difference is that the fields of this class contain internal
    information about the publication process; Metadata contains the
    public information that will be shown on the published project
    pages.

    In particular, UnpublishedProject.modified_datetime will be
    updated when any field of Metadata is altered (see
    UnpublishedProject.save), but not when a field of SubmissionInfo
    is modified.

    New fields should be added to this class only if they do not
    affect the content of the project as it will be shown when
    published.
    """

    editor = models.ForeignKey('user.User',
        related_name='editing_%(class)ss', null=True,
        on_delete=models.SET_NULL, blank=True)
    # The very first submission
    submission_datetime = models.DateTimeField(null=True, blank=True)
    author_comments = models.CharField(max_length=20000, default='', blank=True)
    editor_assignment_datetime = models.DateTimeField(null=True, blank=True)
    # The last revision request (if any)
    revision_request_datetime = models.DateTimeField(null=True, blank=True)
    # The last resubmission (if any)
    resubmission_datetime = models.DateTimeField(null=True, blank=True)
    editor_accept_datetime = models.DateTimeField(null=True, blank=True)
    # The last copyedit (if any)
    copyedit_completion_datetime = models.DateTimeField(null=True, blank=True)
    author_approval_datetime = models.DateTimeField(null=True, blank=True)

    # When the submitting project was created
    creation_datetime = models.DateTimeField(auto_now_add=True)

    edit_logs = GenericRelation('project.EditLog')
    copyedit_logs = GenericRelation('project.CopyeditLog')

    # For ordering projects with multiple versions
    version_order = models.PositiveSmallIntegerField(default=0)

    # Anonymous access
    anonymous = GenericRelation('project.AnonymousAccess')

    class Meta:
        abstract = True

    def quota_manager(self):
        """
        Return a QuotaManager for this project.

        This can be used to calculate the project's disk usage
        (represented by the bytes_used and inodes_used properties of
        the QuotaManager object.)
        """
        allowance = self.core_project.storage_allowance
        published = self.core_project.total_published_size
        limit = allowance - published

        # DemoQuotaManager needs to know the project's toplevel
        # directory as well as its creation time (so that files
        # present in multiple versions can be correctly attributed to
        # the version where they first appeared.)
        quota_manager = DemoQuotaManager(
            project_path=self.file_root(),
            creation_time=self.creation_datetime)
        quota_manager.set_limits(bytes_hard=limit, bytes_soft=limit)
        return quota_manager
