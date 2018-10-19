import pdb

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.contrib.sites.shortcuts import get_current_site
from django.forms import modelformset_factory, Select, Textarea
from django.http import Http404
from django.shortcuts import redirect, render
from django.template import loader
from django.urls import reverse
from django.utils import timezone

from . import forms
import notification.utility as notification
import project.forms as project_forms
from project.models import ActiveProject, ResubmissionLog, StorageRequest, SubmissionLog, Reference, Topic, Publication
from user.models import User


def is_admin(user, *args, **kwargs):
    return user.is_admin


# ------------------------- Views begin ------------------------- #


@login_required
@user_passes_test(is_admin)
def console_home(request):
    return redirect('submitted_projects')


@login_required
@user_passes_test(is_admin)
def submitted_projects(request):
    """
    List of active submissions. Editors are assigned here.
    """
    if request.method == 'POST':
        assign_editor_form = forms.AssignEditorForm(request.POST)
        if assign_editor_form.is_valid():
            # Move this into project method
            project = assign_editor_form.cleaned_data['project']
            project.assign_editor(assign_editor_form.cleaned_data['editor'])
            notification.assign_editor_notify(project)
            messages.success(request, 'The editor has been assigned')

    # Need to filter this by submission datetime
    projects = ActiveProject.objects.filter(submission_status__gt=0).order_by(
        'submission_datetime')

    # Separate projects by submission status
    # Awaiting editor assignment
    assignment_projects = projects.filter(submission_status=10)
    # Awaiting editor decision
    decision_projects = projects.filter(submission_status=20)
    # Awaiting author revisions
    revision_projects = projects.filter(submission_status=30)
    # Awaiting editor copyedit
    copyedit_projects = projects.filter(submission_status=40)
    # Awaiting author approval
    # Awaiting editor publish

    assign_editor_form = forms.AssignEditorForm()

    return render(request, 'console/submitted_projects.html',
        {'projects':projects,
         'assign_editor_form':assign_editor_form,
         'assignment_projects':assignment_projects,
         'decision_projects':decision_projects,
         'revision_projects':revision_projects,
         'copyedit_projects':copyedit_projects,
         })


@login_required
@user_passes_test(is_admin)
def editor_home(request):
    """
    List of submissions the editor is responsible for
    """
    projects = ActiveProject.objects.filter(editor=request.user).order_by(
        'submission_datetime')

    # awaiting editor decision
    decision_projects = projects.filter(submission_status=20)
    # awaiting author revisions
    revision_projects = projects.filter(submission_status=30)
    # awaiting editor copyedit
    copyedit_projects = projects.filter(submission_status=40)
    return render(request, 'console/editor_home.html',
        {'decision_projects':decision_projects,
         'revision_projects':revision_projects,
         'copyedit_projects':copyedit_projects})


@login_required
@user_passes_test(is_admin)
def edit_submission(request, project_slug):
    """
    Page to respond to a particular submission, as an editor
    """
    project = ActiveProject.objects.get(slug=project_slug)
    submission_log = project.submission_log.get()
    # The user must be the editor
    if request.user != project.editor or project.submission_status not in [20, 30]:
        return Http404()

    if request.method == 'POST':
        edit_submission_form = forms.EditSubmissionForm(
            instance=submission_log, data=request.POST)
        if edit_submission_form.is_valid():
            # This processes the resulting decision
            submission_log = edit_submission_form.save()
            # Resubmit with changes
            if submission_log.decision == 0:
                notification.edit_resubmit_notify(request, submission_log)
            # Reject
            elif submission_log.decision == 1:
                notification.edit_reject_notify(request, submission_log)
            # Accept
            else:
                notification.edit_accept_notify(request, submission_log)

            return render(request, 'console/edit_complete.html',
                {'decision':submission_log.decision,
                 'project':project, 'submission_log':submission_log})
        else:
            messages.error(request, 'Invalid response. See form below.')
    else:
        edit_submission_form = forms.EditSubmissionForm(instance=submission_log)

    return render(request, 'console/edit_submission.html',
        {'project':project, 'submission_log':submission_log,
         'edit_submission_form':edit_submission_form})


@login_required
@user_passes_test(is_admin)
def copyedit_submission(request, project_slug):
    """
    Page to copyedit the submission
    """
    project = ActiveProject.objects.get(slug=project_slug)
    submission_log = project.submission_log.get()
    # Copyedit statuses: 40 is before the editor allows authors to
    # approve. 50 is when the authors are approving
    if request.user != project.editor or project.submission_status not in [40, 50]:
        return Http404()

    submitting_author, coauthors, author_emails = project.get_author_info(
        separate_submitting=True, include_emails=True)
    # all_authors_approved = (len(authors) == len(authors.filter(approved_publish=True)))

    # Metadata forms and formsets
    ReferenceFormSet = generic_inlineformset_factory(Reference,
        fields=('description',), extra=0,
        max_num=project_forms.ReferenceFormSet.max_forms, can_delete=False,
        formset=project_forms.ReferenceFormSet, validate_max=True)
    TopicFormSet = generic_inlineformset_factory(Topic,
        fields=('description',), extra=0,
        max_num=project_forms.TopicFormSet.max_forms, can_delete=False,
        formset=project_forms.TopicFormSet, validate_max=True)
    PublicationFormSet = generic_inlineformset_factory(Publication,
        fields=('citation', 'url'), extra=0,
        max_num=project_forms.PublicationFormSet.max_forms, can_delete=False,
        formset=project_forms.PublicationFormSet, validate_max=True)

    description_form = project_forms.METADATA_FORMS[project.resource_type](
        instance=project)
    access_form = project_forms.AccessMetadataForm(instance=project)
    reference_formset = ReferenceFormSet(instance=project)
    publication_formset = PublicationFormSet(instance=project)
    topic_formset = TopicFormSet(instance=project)

    complete_copyedit_form = forms.CompleteCopyeditForm()

    if request.method == 'POST':
        if 'edit_metadata' in request.POST:
            description_form = project_forms.METADATA_FORMS[project.resource_type](
                data=request.POST, instance=project)
            access_form = project_forms.AccessMetadataForm(request.POST,
                instance=project)
            reference_formset = ReferenceFormSet(request.POST,
                instance=project)
            publication_formset = PublicationFormSet(request.POST,
                                                 instance=project)
            topic_formset = TopicFormSet(request.POST, instance=project)
            if (description_form.is_valid() and access_form.is_valid()
                                            and reference_formset.is_valid()
                                            and publication_formset.is_valid()
                                            and topic_formset.is_valid()):
                description_form.save()
                access_form.save()
                reference_formset.save()
                publication_formset.save()
                topic_formset.save()
                messages.success(request,
                    'The project metadata has been updated.')

                # Reload formsets
                reference_formset = ReferenceFormSet(instance=project)
                publication_formset = PublicationFormSet(instance=project)
                topic_formset = TopicFormSet(instance=project)
            else:
                messages.error(request,
                    'Invalid submission. See errors below.')
        elif 'edit_files' in request.POST:
            pass
        elif 'complete_copyedit' in request.POST:
            submission_log.status = 50
            submission.copyedit_datetime = timezone.now()
            submission.save()
            notification.copyedit_complete_notify(request, submission)
            return render(request, 'console/copyedit_complete.html',
                {'submission':submission})

    edit_url = reverse('edit_metadata_item', args=[project.slug])

    return render(request, 'console/copyedit_submission.html', {
        'project':project, 'submission_log':submission_log,
        'description_form':description_form,
        'access_form':access_form,
        'reference_formset':reference_formset,
        'publication_formset':publication_formset,
        'topic_formset':topic_formset,
        'complete_copyedit_form':complete_copyedit_form,
        # 'all_authors_approved':all_authors_approved,
        'submitting_author':submitting_author, 'coauthors':coauthors,
        'author_emails':author_emails,
        'add_item_url':edit_url, 'remove_item_url':edit_url})


@login_required
@user_passes_test(is_admin)
def publish_submission(request, submission_id):
    """
    Page to publish the submission
    """
    submission = SubmissionLog.objects.get(id=submission_id)
    if submission.status != 4:
        return Http404()

    project = submission.project

    if request.method == 'POST':
        if project.is_publishable():
            published_project = project.publish()
            notification.publish_notify(request, project, published_project)
            return render(request, 'console/publish_complete.html',
                {'published_project':published_project})

    publishable = project.is_publishable()
    return render(request, 'console/publish_submission.html', {
        'submission':submission, 'publishable':publishable})


def process_storage_response(request, storage_response_formset):
    """
    Implement the response to a storage request.
    Helper function to view: storage_requests.
    """
    storage_request_id = int(request.POST['storage_response'])

    for storage_response_form in storage_response_formset:
        # Only process the response that was submitted
        if storage_response_form.instance.id == storage_request_id:
            if storage_response_form.is_valid() and storage_response_form.instance.is_active:
                storage_request = storage_response_form.instance
                storage_request.responder = request.user
                storage_request.response_datetime = timezone.now()
                storage_request.is_active = False
                storage_request.save()

                if storage_request.response:
                    core_project = storage_request.project.core_project
                    core_project.storage_allowance = storage_request.request_allowance * 1024
                    core_project.save()

                notification.storage_response_notify(storage_request)
                messages.success(request,
                    'The storage request has been {}'.format(notification.RESPONSE_ACTIONS[storage_request.response]))

@login_required
@user_passes_test(is_admin)
def storage_requests(request):
    """
    Page for listing and responding to project storage requests
    """
    StorageResponseFormSet = modelformset_factory(StorageRequest,
        fields=('response', 'response_message'),
        widgets={'response':Select(choices=forms.RESPONSE_CHOICES),
                 'response_message':Textarea()}, extra=0)

    if request.method == 'POST':
        storage_response_formset = StorageResponseFormSet(request.POST)
        process_storage_response(request, storage_response_formset)

    storage_response_formset = StorageResponseFormSet(
        queryset=StorageRequest.objects.filter(is_active=True))

    return render(request, 'console/storage_requests.html',
        {'storage_response_formset':storage_response_formset})


@login_required
@user_passes_test(is_admin)
def unsubmitted_projects(request):
    """
    List of unsubmitted projects
    """
    projects = ActiveProject.objects.filter(submission_status=0)
    # title, submitting author, creation date, published,
    return render(request, 'console/unsubmitted_projects.html',
        {'projects':projects})


@login_required
@user_passes_test(is_admin)
def users(request):
    """
    List of users
    """
    users = User.objects.all()
    return render(request, 'console/users.html', {'users':users})
